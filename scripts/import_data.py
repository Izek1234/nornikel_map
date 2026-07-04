#!/usr/bin/env python3
"""Import all downloaded documents into the NORNIKEL Knowledge Graph."""
import os, sys, glob, hashlib, json, time, traceback

# Add backend to path
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "backend"))

import ingestion
import graph_db
import llm_client as llm
import postprocess

DATA_DIR = os.path.join(ROOT_DIR, "data")
SUPPORTED = (".pdf", ".docx", ".txt", ".md", ".csv")

def find_documents(root):
    """Find all documents in data directory."""
    files = []
    for ext in SUPPORTED:
        for f in glob.glob(os.path.join(root, "**", f"*{ext}"), recursive=True):
            files.append(f)
    return files

def main():
    print("=" * 60)
    print("NORNIKEL Knowledge Map - Data Import")
    print("=" * 60)

    # Check Neo4j
    try:
        graph_db.run("RETURN 1 AS ok")
        print("✓ Neo4j connected")
    except Exception as e:
        print(f"✗ Neo4j not available: {e}")
        print("  Make sure NEO4J_URI and NEO4J_PASSWORD are set in .env")
        sys.exit(1)

    llm_health = llm.check_health()
    if not llm_health.get("ok"):
        print(f"✗ LLM not available: {llm_health.get('error', 'unknown error')}")
        sys.exit(1)
    print(f"✓ LLM ready: {llm_health.get('provider', 'unknown')}")

    # Init schema
    graph_db.init_schema()
    print("✓ Neo4j schema initialized")

    # Find documents
    files = find_documents(DATA_DIR)
    print(f"\nFound {len(files)} documents:")
    for f in files:
        rel = os.path.relpath(f, DATA_DIR)
        size = os.path.getsize(f)
        print(f"  {rel} ({size // 1024} KB)")

    # Import each
    for i, filepath in enumerate(files, 1):
        filename = os.path.basename(filepath)
        relpath = os.path.relpath(filepath, DATA_DIR)
        print(f"\n[{i}/{len(files)}] Importing: {relpath}")

        try:
            with open(filepath, "rb") as f:
                content = f.read()

            text = ingestion.parse_file(filename, content)
            if not text.strip():
                print(f"  ⚠ Empty text in {filename}, skipping")
                continue

            chunks = ingestion.chunk_text(text)
            print(f"  → {len(chunks)} chunks ({len(text)} chars)")

            doc_id = hashlib.sha256(filepath.encode()).hexdigest()[:12]
            graph_db.upsert_document(doc_id, relpath, len(content), "application/octet-stream")

            done = 0
            for chunk in chunks:
                if graph_db.chunk_exists(chunk["hash"]):
                    graph_db.upsert_chunk(chunk["hash"], chunk["text"], chunk["index"], doc_id)
                    done += 1
                    continue

                graph_db.upsert_chunk(chunk["hash"], chunk["text"], chunk["index"], doc_id)
                extracted = llm.extract_graph(chunk["text"])

                key_by_name = {}
                for ent in extracted.get("entities", []):
                    name = (ent.get("name") or "").strip()
                    if not name:
                        continue
                    key = postprocess.canonical_key(name)
                    key_by_name[name.lower()] = key
                    graph_db.upsert_entity(key, name, ent.get("type", "Property").strip(),
                                           ent.get("description", "").strip(),
                                           postprocess.collect_aliases(name), chunk["hash"])

                for rel in extracted.get("relations", []):
                    src = key_by_name.get((rel.get("source") or "").strip().lower())
                    dst = key_by_name.get((rel.get("target") or "").strip().lower())
                    rtype = (rel.get("type") or "RELATED").strip()
                    if src and dst and src != dst:
                        graph_db.upsert_relation(src, dst, rtype, chunk["hash"])

                for raw_fact in extracted.get("facts", []):
                    fact = postprocess.build_fact(raw_fact)
                    if not fact:
                        continue
                    skey = key_by_name.get(fact["subject"].lower())
                    if not skey:
                        skey = postprocess.canonical_key(fact["subject"])
                        graph_db.upsert_entity(skey, fact["subject"], "Property",
                                               "", [fact["subject"]], chunk["hash"])
                    graph_db.create_fact(fact, skey, chunk["hash"], doc_id)

                graph_db.mark_chunk_processed(chunk["hash"])
                done += 1

            graph_db.set_document_status(doc_id, "completed")
            print(f"  ✓ Imported ({done}/{len(chunks)} chunks processed)")

        except Exception as e:
            print(f"  ✗ Error: {e}")
            traceback.print_exc()
            continue

    # Stats
    print("\n" + "=" * 60)
    print("Import complete!")
    try:
        stats = graph_db.get_stats()
        print(f"  Entities: {stats.get('entities', 0)}")
        print(f"  Facts:    {stats.get('facts', 0)}")
        print(f"  Docs:     {stats.get('documents', 0)}")
        print(f"  Chunks:   {stats.get('chunks', 0)}")
        print(f"  Relations: {stats.get('relations', 0)}")
    except Exception as e:
        print(f"  Stats error: {e}")

if __name__ == "__main__":
    main()
