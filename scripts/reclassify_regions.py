"""Batch reclassify all facts by region using LLM.

Usage:
    cd backend
    python ../scripts/reclassify_regions.py [--limit N] [--batch-size N]
"""

import sys
import os
import time
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import graph_db
import llm_client


def reclassify_all(limit: int = 5000, batch_size: int = 50):
    """Reclassify all facts with unknown geography."""
    # Count facts to classify
    total_rows = graph_db.run(
        "MATCH (f:Fact) WHERE f.geography IS NULL OR f.geography = '' OR f.geography = 'unknown' "
        "RETURN count(f) AS cnt"
    )
    total = min(total_rows[0]["cnt"], limit) if total_rows else 0
    print(f"Facts to classify: {total}")

    if total == 0:
        print("All facts already classified!")
        return

    classified = 0
    updated = 0
    errors = 0
    start_time = time.time()

    # Process in batches
    offset = 0
    while offset < total:
        batch_limit = min(batch_size, total - offset)
        rows = graph_db.run(
            "MATCH (f:Fact) "
            "WHERE f.geography IS NULL OR f.geography = '' OR f.geography = 'unknown' "
            "RETURN f.subject AS subject, f.predicate AS predicate, "
            "f.object AS object, f.quote AS quote "
            "SKIP $skip LIMIT $lim",
            skip=offset, lim=batch_limit,
        )

        for row in rows:
            text = f"{row.get('subject', '')}. {row.get('predicate', '')}: {row.get('object', '')}"
            if row.get("quote"):
                text += f" ({row['quote'][:200]})"

            try:
                region = llm_client.classify_region(text)
                classified += 1

                if region in ("RU", "world"):
                    graph_db.run(
                        "MATCH (f:Fact {subject: $subj, predicate: $pred, object: $obj}) "
                        "SET f.geography = $geo",
                        subj=row["subject"], pred=row["predicate"],
                        obj=row["object"], geo=region,
                    )
                    updated += 1
            except Exception as e:
                errors += 1
                print(f"Error: {e}")

            # Progress
            done = offset + classified
            if done % 10 == 0 or done == total:
                elapsed = time.time() - start_time
                rate = classified / elapsed if elapsed > 0 else 0
                print(f"  Progress: {done}/{total} ({updated} updated, {errors} errors) - {rate:.1f} facts/sec")

        offset += batch_limit

    elapsed = time.time() - start_time
    print(f"\nDone! Classified: {classified}, Updated: {updated}, Errors: {errors}")
    print(f"Time: {elapsed:.1f}s ({classified/elapsed:.1f} facts/sec)")

    # Show final distribution
    rows = graph_db.run("MATCH (f:Fact) RETURN f.geography AS geo, count(f) AS cnt")
    print("\nFinal geography distribution:")
    for r in rows:
        print(f"  {r['geo']}: {r['cnt']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5000, help="Max facts to process")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size")
    args = parser.parse_args()
    reclassify_all(limit=args.limit, batch_size=args.batch_size)
