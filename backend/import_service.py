"""Reusable document import pipeline for manual upload and startup sync."""

import hashlib
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field

from fastapi import BackgroundTasks, HTTPException

import cache
import domains
import graph_db
import ingestion
import llm_client as llm
import ontology
import postprocess
import versioning

MAX_FILE_SIZE = 10000 * 1024 * 1024
MAX_PARALLEL_IMPORTS = max(1, int(os.environ.get("MAX_PARALLEL_IMPORTS", "2")))
_import_semaphore = threading.BoundedSemaphore(MAX_PARALLEL_IMPORTS)


@dataclass
class DocumentJob:
    doc_id: str
    filename: str
    chunks: list[dict]
    done: int = 0
    status: str = "processing"
    error: str | None = None
    cancel_requested: bool = False
    pause_requested: bool = False
    thread: threading.Thread | None = None
    condition: threading.Condition = field(default_factory=threading.Condition)


_jobs: dict[str, DocumentJob] = {}
_jobs_lock = threading.Lock()


def _register_job(job: DocumentJob):
    with _jobs_lock:
        _jobs[job.doc_id] = job


def _get_job(doc_id: str) -> DocumentJob | None:
    with _jobs_lock:
        return _jobs.get(doc_id)


def _start_job(job: DocumentJob):
    worker = threading.Thread(
        target=process_document,
        args=(job,),
        name=f"document-import-{job.doc_id}",
        daemon=True,
    )
    job.thread = worker
    worker.start()


def start_document_import(
    content: bytes,
    filename: str,
    mime: str,
    source_meta: dict | None = None,
    background_tasks: BackgroundTasks | None = None,
):
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "Файл больше 15 МБ")
    try:
        text = ingestion.parse_file(filename or "file.txt", content)
    except ValueError as exc:
        raise HTTPException(415, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, f"Ошибка разбора: {exc}") from exc

    chunks = ingestion.chunk_text(text)
    if not chunks:
        raise HTTPException(422, "Нет текста в файле")

    doc_id = uuid.uuid4().hex[:12]
    graph_db.init_schema()
    graph_db.upsert_document(
        doc_id,
        filename or doc_id,
        len(content),
        mime or "text/plain",
        source_meta=source_meta,
    )
    graph_db.set_document_progress(doc_id, len(chunks), 0)

    job = DocumentJob(doc_id=doc_id, filename=filename or "unknown", chunks=chunks)
    _register_job(job)
    _start_job(job)

    try:
        versioning.log_document_version(
            doc_id=doc_id, doc_name=filename or "unknown",
            change_type="uploaded", author="system",
            new_status="processing",
            chunks_delta=len(chunks),
        )
    except Exception:
        pass

    return {"id": doc_id, "name": filename, "chunks": len(chunks), "status": "processing"}


def pause_document_import(doc_id: str):
    job = _get_job(doc_id)
    if job is None:
        graph_db.set_document_status(doc_id, "paused")
        try:
            versioning.log_document_version(doc_id=doc_id, doc_name="", change_type="paused", old_status="processing", new_status="paused")
        except Exception:
            pass
        return {"ok": True, "id": doc_id, "status": "paused"}
    with job.condition:
        if job.status not in {"processing", "paused"}:
            raise HTTPException(409, "Пауза доступна только во время обработки")
        job.pause_requested = True
        if job.status == "processing":
            job.status = "paused"
            graph_db.set_document_status(doc_id, "paused")
        job.condition.notify_all()
    try:
        versioning.log_document_version(doc_id=doc_id, doc_name=job.filename, change_type="paused", old_status="processing", new_status="paused")
    except Exception:
        pass
    return {"ok": True, "id": doc_id, "status": "paused"}


def resume_document_import(doc_id: str):
    job = _get_job(doc_id)
    if job is None:
        graph_db.set_document_status(doc_id, "processing")
        try:
            versioning.log_document_version(doc_id=doc_id, doc_name="", change_type="resumed", new_status="processing")
        except Exception:
            pass
        return {"ok": True, "id": doc_id, "status": "processing"}
    with job.condition:
        if job.status not in {"paused", "failed", "canceled"}:
            raise HTTPException(409, "Продолжение недоступно для этого статуса")
        job.pause_requested = False
        job.cancel_requested = False
        job.error = None
        graph_db.set_document_status(doc_id, "processing")
        if job.thread and job.thread.is_alive():
            job.status = "processing"
            job.condition.notify_all()
        else:
            job.done = 0
            job.status = "processing"
            graph_db.set_document_progress(doc_id, len(job.chunks), 0)
            _start_job(job)
    try:
        versioning.log_document_version(doc_id=doc_id, doc_name=job.filename, change_type="resumed", old_status="paused", new_status="processing")
    except Exception:
        pass
    return {"ok": True, "id": doc_id, "status": "processing"}


def cancel_document_import(doc_id: str):
    job = _get_job(doc_id)
    if job is None:
        graph_db.set_document_status(doc_id, "canceled", "Отменено пользователем")
        try:
            versioning.log_document_version(doc_id=doc_id, doc_name="", change_type="canceled", new_status="canceled", comment="Отменено пользователем")
        except Exception:
            pass
        return {"ok": True, "id": doc_id, "status": "canceled"}
    with job.condition:
        if job.status in {"completed", "failed", "canceled"}:
            raise HTTPException(409, "Отмена недоступна для этого статуса")
        job.cancel_requested = True
        job.pause_requested = False
        job.status = "canceled"
        graph_db.set_document_status(doc_id, "canceled")
        job.condition.notify_all()
    try:
        versioning.log_document_version(doc_id=doc_id, doc_name=job.filename, change_type="canceled", old_status=job.status, new_status="canceled")
    except Exception:
        pass
    return {"ok": True, "id": doc_id, "status": "canceled"}


def restart_document_import(doc_id: str):
    job = _get_job(doc_id)
    if job is None:
        graph_db.set_document_progress(doc_id, 0, 0)
        graph_db.set_document_status(doc_id, "processing")
        try:
            versioning.log_document_version(doc_id=doc_id, doc_name="", change_type="restarted", new_status="processing")
        except Exception:
            pass
        return {"ok": True, "id": doc_id, "status": "processing"}
    with job.condition:
        if job.thread and job.thread.is_alive():
            job.cancel_requested = True
            job.pause_requested = False
            job.condition.notify_all()
    while job.thread and job.thread.is_alive():
        time.sleep(0.05)
    with job.condition:
        job.done = 0
        job.error = None
        job.cancel_requested = False
        job.pause_requested = False
        job.status = "processing"
        graph_db.set_document_progress(doc_id, len(job.chunks), 0)
        graph_db.set_document_status(doc_id, "processing")
        _start_job(job)
    try:
        versioning.log_document_version(doc_id=doc_id, doc_name=job.filename, change_type="restarted", old_status=job.status, new_status="processing")
    except Exception:
        pass
    return {"ok": True, "id": doc_id, "status": "processing"}


def process_document(job: DocumentJob):
    try:
        with _import_semaphore:
            for chunk in job.chunks:
                with job.condition:
                    while job.pause_requested and not job.cancel_requested:
                        job.status = "paused"
                        graph_db.set_document_status(job.doc_id, "paused")
                        job.condition.wait()
                    if job.cancel_requested:
                        job.status = "canceled"
                        graph_db.set_document_status(job.doc_id, "canceled")
                        return

                if graph_db.chunk_exists(chunk["hash"]):
                    graph_db.upsert_chunk(chunk["hash"], chunk["text"], chunk["index"], job.doc_id)
                    job.done += 1
                    graph_db.set_document_progress(job.doc_id, len(job.chunks), job.done)
                    continue

                graph_db.upsert_chunk(chunk["hash"], chunk["text"], chunk["index"], job.doc_id)
                try:
                    extracted = llm.extract_graph(chunk["text"])
                except llm.LLMError as exc:
                    error_msg = str(exc).lower()
                    if "429" in error_msg or "quota" in error_msg or "too many" in error_msg:
                        time.sleep(5)
                        try:
                            extracted = llm.extract_graph(chunk["text"])
                        except llm.LLMError:
                            job.done += 1
                            graph_db.set_document_progress(job.doc_id, len(job.chunks), job.done)
                            continue
                    else:
                        raise
                key_by_name: dict[str, str] = {}
                type_by_name: dict[str, str] = {}

                for ent in extracted.get("entities", []):
                    name = (ent.get("name") or "").strip()
                    if not name:
                        continue
                    etype = ontology.validate_node_type(ent.get("type", "Property"))
                    canonical = postprocess.canonical_key(name)
                    key = hashlib.sha256(canonical.encode()).hexdigest()[:12]
                    key_by_name[name.lower()] = key
                    type_by_name[name.lower()] = etype

                    aliases = set(postprocess.collect_aliases(name))
                    if isinstance(ent.get("aliases"), list):
                        aliases.update(str(a) for a in ent["aliases"] if a)

                    # Domains from LLM classification
                    raw_domains = ent.get("domains") or []
                    ent_domains = domains.validate_domains(raw_domains) if raw_domains else []

                    graph_db.upsert_entity(
                        key,
                        name,
                        etype,
                        ent.get("description", ""),
                        list(aliases),
                        chunk["hash"],
                        domains=ent_domains,
                    )

                for exp in extracted.get("experiments", []):
                    exp_name = (exp.get("name") or "").strip()
                    if not exp_name:
                        continue
                    exp_key = hashlib.sha256(postprocess.canonical_key(exp_name).encode()).hexdigest()[:12]
                    src_info = {
                        "document_id": job.doc_id,
                        "page": (exp.get("source") or {}).get("page"),
                        "chunk_id": chunk["hash"],
                        "original_text": chunk["text"][:2000],
                        "filename": job.filename,
                    }
                    facts_to_create = []
                    for output in exp.get("produces_output", []) or []:
                        prop_name = (output.get("property") or output.get("name") or "").strip()
                        if not prop_name: continue
                        raw_fact = {
                            "subject": exp_name,
                            "predicate": prop_name,
                            "object": str(output.get("value") or ""),
                            "value_min": output.get("value_min"),
                            "value_max": output.get("value_max"),
                            "unit": output.get("unit"),
                            "geography": output.get("geography"),
                            "time": output.get("time"),
                            "quote": chunk["text"][:300],
                        }
                        fact = postprocess.build_fact(raw_fact)
                        if fact:
                            facts_to_create.append((prop_name, fact))
                            
                    properties = ontology.extract_experiment_properties([f[1] for f in facts_to_create])
                    graph_db.create_experiment(exp_key, exp_name, properties, src_info)
                    key_by_name[exp_name.lower()] = exp_key
                    type_by_name[exp_name.lower()] = "Experiment"

                    for prop_name, fact in facts_to_create:
                        if prop_name.lower() not in ontology.EXPERIMENT_PARAM_PROPERTIES:
                            pk = hashlib.sha256(postprocess.canonical_key(prop_name).encode()).hexdigest()[:12]
                            graph_db.upsert_entity(
                                pk, prop_name, "Property", "",
                                postprocess.collect_aliases(prop_name), chunk["hash"]
                            )
                            key_by_name[prop_name.lower()] = pk
                            type_by_name[prop_name.lower()] = "Property"
                            graph_db.upsert_relation(exp_key, pk, "PRODUCES_OUTPUT", chunk["hash"])
                        
                        graph_db.create_fact(fact, exp_key, chunk["hash"], job.doc_id)

                    for mat in exp.get("uses_materials", []):
                        material = mat.strip()
                        if not material:
                            continue
                        mk = hashlib.sha256(postprocess.canonical_key(material).encode()).hexdigest()[:12]
                        graph_db.upsert_entity(
                            mk, material, "Material", "",
                            postprocess.collect_aliases(material), chunk["hash"]
                        )
                        key_by_name[material.lower()] = mk
                        type_by_name[material.lower()] = "Material"
                        graph_db.upsert_relation(exp_key, mk, "USES_MATERIAL", chunk["hash"])

                    for proc in exp.get("uses_processes", []):
                        process = proc.strip()
                        if not process:
                            continue
                        pk = hashlib.sha256(postprocess.canonical_key(process).encode()).hexdigest()[:12]
                        graph_db.upsert_entity(
                            pk, process, "Process", "",
                            postprocess.collect_aliases(process), chunk["hash"]
                        )
                        key_by_name[process.lower()] = pk
                        type_by_name[process.lower()] = "Process"
                        graph_db.upsert_relation(exp_key, pk, "USES_PROCESS", chunk["hash"])

                    raw_fac = exp.get("performed_at") or ""
                    if isinstance(raw_fac, list):
                        raw_fac = raw_fac[0] if raw_fac else ""
                    facility = str(raw_fac).strip()
                    if facility:
                        fk = hashlib.sha256(postprocess.canonical_key(facility).encode()).hexdigest()[:12]
                        graph_db.upsert_entity(
                            fk, facility, "Facility", "",
                            postprocess.collect_aliases(facility), chunk["hash"]
                        )
                        key_by_name[facility.lower()] = fk
                        type_by_name[facility.lower()] = "Facility"
                        graph_db.upsert_relation(exp_key, fk, "PERFORMED_AT", chunk["hash"])

                for rel in extracted.get("relations", []):
                    src_name = (rel.get("source") or "").strip().lower()
                    dst_name = (rel.get("target") or "").strip().lower()
                    src = key_by_name.get(src_name)
                    dst = key_by_name.get(dst_name)
                    src_type = type_by_name.get(src_name)
                    dst_type = type_by_name.get(dst_name)
                    if not (src and dst and src_type and dst_type):
                        continue
                    rtype = ontology.validate_relation(rel.get("type", ""), src_type, dst_type)
                    if rtype:
                        graph_db.upsert_relation(src, dst, rtype, chunk["hash"])

                graph_db.mark_chunk_processed(chunk["hash"])
                job.done += 1
                graph_db.set_document_progress(job.doc_id, len(job.chunks), job.done)

        cache.invalidate_all()
        job.status = "completed"
        graph_db.set_document_status(job.doc_id, "completed")
        try:
            versioning.log_document_version(
                doc_id=job.doc_id, doc_name=job.filename,
                change_type="completed", new_status="completed",
                chunks_delta=len(job.chunks),
            )
        except Exception:
            pass
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)[:500]
        graph_db.set_document_status(job.doc_id, "failed", job.error)
        try:
            versioning.log_document_version(
                doc_id=job.doc_id, doc_name=job.filename,
                change_type="failed", new_status="failed",
                comment=job.error[:200],
            )
        except Exception:
            pass
        raise


def _build_property_fact(subject: str, predicate: str, raw_value, text: str) -> dict | None:
    value = "" if raw_value is None else str(raw_value)
    unit_match = re.search(r"(мг/дм³|мг/дм3|мг/л|г/л|°C|°С|кА/м2|А/м2|м3/ч|л/мин|%|MPa|МПа|atm|атм|h|ч|min|мин)", value, re.IGNORECASE)
    fact = postprocess.build_fact({
        "subject": subject,
        "predicate": str(predicate).replace("_", " "),
        "object": value,
        "value": value,
        "unit": unit_match.group(1) if unit_match else None,
        "quote": text[:300],
        "geography": "unknown",
    })
    return fact
