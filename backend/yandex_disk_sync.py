"""Startup sync from a public Yandex Disk folder."""

import threading
import time
from pathlib import Path

import httpx

from config import settings
import graph_db
import import_service

PUBLIC_RESOURCES_URL = "https://cloud-api.yandex.net/v1/disk/public/resources"
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md", ".csv"}
SYNC_STATE_NAME = "yandex_disk_public"
_control_lock = threading.Lock()
_cancel_event = threading.Event()
_pause_event = threading.Event()
_sync_thread: threading.Thread | None = None


def is_enabled() -> bool:
    public_url = settings.yandex_disk_public_url.strip()
    if not public_url:
        return False
    flag = settings.sync_on_startup.strip().lower()
    return flag not in {"0", "false", "no", "off"}


def sync_on_startup():
    _cancel_event.clear()
    public_url = settings.yandex_disk_public_url.strip()
    enabled = is_enabled()
    if not enabled:
        graph_db.upsert_sync_state(
            name=SYNC_STATE_NAME,
            enabled=False,
            ok=False,
            source_url=public_url or None,
            status="disabled",
            last_error=None,
        )
        return graph_db.get_sync_state(SYNC_STATE_NAME)

    max_files = settings.sync_max_files_per_run
    counts = {"found": 0, "downloaded": 0, "skipped": 0, "failed": 0}
    last_error = None

    graph_db.upsert_sync_state(
        name=SYNC_STATE_NAME,
        enabled=True,
        ok=True,
        source_url=public_url,
        status="running",
        files_found=0,
        files_downloaded=0,
        files_skipped=0,
        files_failed=0,
        last_error=None,
    )

    try:
        graph_db.init_schema()
        with httpx.Client(timeout=120) as client:
            items = _list_public_files(client, public_url, max_files)
            counts["found"] = len(items)
            for item in items:
                if _cancel_event.is_set():
                    last_error = "Синхронизация отменена пользователем"
                    break
                _wait_if_paused(public_url, counts)
                if not _is_supported(item.get("name", "")):
                    counts["skipped"] += 1
                    continue

                source_external_id = _external_id(item)
                version = {
                    "source_etag": item.get("md5"),
                    "source_modified": item.get("modified"),
                }
                existing = graph_db.get_document_by_source("yandex_disk", source_external_id)
                if existing and existing.get("status") == "completed" and _same_version(existing, version):
                    counts["skipped"] += 1
                    continue

                try:
                    content, mime = _download_file(client, public_url, item)
                    import_service.start_document_import(
                        content=content,
                        filename=item.get("name") or source_external_id,
                        mime=mime or item.get("mime_type") or "application/octet-stream",
                        source_meta={
                            "source_provider": "yandex_disk",
                            "source_external_id": source_external_id,
                            "source_path": item.get("path") or item.get("name"),
                            "source_url": item.get("public_url") or public_url,
                            "source_etag": version["source_etag"],
                            "source_modified": version["source_modified"],
                            "sync_status": "completed",
                            "last_synced_at": None,
                        },
                    )
                    counts["downloaded"] += 1
                    graph_db.upsert_sync_state(
                        name=SYNC_STATE_NAME,
                        enabled=True,
                        ok=True,
                        source_url=public_url,
                        status="running",
                        files_found=counts["found"],
                        files_downloaded=counts["downloaded"],
                        files_skipped=counts["skipped"],
                        files_failed=counts["failed"],
                        last_error=None,
                    )
                except Exception as exc:
                    import traceback
                    traceback.print_exc()
                    print(f"Sync failed for item {item.get('name')}: {exc}", flush=True)
                    counts["failed"] += 1
                    last_error = str(exc)[:500]
    except Exception as exc:
        last_error = str(exc)[:500]

    ok = last_error is None and counts["failed"] == 0
    if _cancel_event.is_set():
        status = "canceled"
        ok = False
    else:
        status = "completed" if ok else ("partial" if counts["downloaded"] > 0 else "failed")
    graph_db.upsert_sync_state(
        name=SYNC_STATE_NAME,
        enabled=True,
        ok=ok,
        source_url=public_url,
        status=status,
        files_found=counts["found"],
        files_downloaded=counts["downloaded"],
        files_skipped=counts["skipped"],
        files_failed=counts["failed"],
        last_error=last_error,
    )
    return graph_db.get_sync_state(SYNC_STATE_NAME)


def get_sync_status():
    return graph_db.get_sync_state(SYNC_STATE_NAME)


def start_background_sync(force: bool = False):
    public_url = settings.yandex_disk_public_url.strip()
    if not public_url:
        graph_db.upsert_sync_state(
            name=SYNC_STATE_NAME,
            enabled=False,
            ok=False,
            source_url=None,
            status="disabled",
            last_error=None,
        )
        return graph_db.get_sync_state(SYNC_STATE_NAME)

    global _sync_thread
    with _control_lock:
        if _sync_thread and _sync_thread.is_alive() and not force:
            return graph_db.get_sync_state(SYNC_STATE_NAME)
        if _sync_thread and _sync_thread.is_alive() and force:
            _cancel_event.set()
            _pause_event.clear()

    if force:
        while _sync_thread and _sync_thread.is_alive():
            time.sleep(0.05)

    with _control_lock:
        _cancel_event.clear()
        _pause_event.clear()
        _sync_thread = threading.Thread(target=sync_on_startup, name="yandex-disk-sync", daemon=True)
        _sync_thread.start()
    return graph_db.get_sync_state(SYNC_STATE_NAME)


def pause_sync():
    public_url = settings.yandex_disk_public_url.strip()
    _pause_event.set()
    graph_db.upsert_sync_state(
        name=SYNC_STATE_NAME,
        enabled=True,
        ok=True,
        source_url=public_url,
        status="paused",
        last_error=None,
    )
    return graph_db.get_sync_state(SYNC_STATE_NAME)


def resume_sync():
    public_url = settings.yandex_disk_public_url.strip()
    _pause_event.clear()
    graph_db.upsert_sync_state(
        name=SYNC_STATE_NAME,
        enabled=True,
        ok=True,
        source_url=public_url,
        status="running",
        last_error=None,
    )
    return start_background_sync(force=False)


def cancel_sync():
    public_url = settings.yandex_disk_public_url.strip()
    _cancel_event.set()
    _pause_event.clear()
    graph_db.upsert_sync_state(
        name=SYNC_STATE_NAME,
        enabled=True,
        ok=False,
        source_url=public_url,
        status="canceled",
        last_error="Синхронизация отменена пользователем",
    )
    return graph_db.get_sync_state(SYNC_STATE_NAME)


def _list_public_files(client: httpx.Client, public_url: str, max_files: int):
    files: list[dict] = []
    _walk_public_resource(client, public_url, "/", max(max_files, 1), files)
    return files[:max_files]


def _walk_public_resource(client: httpx.Client, public_url: str, path: str, max_files: int, files: list[dict]):
    if len(files) >= max_files:
        return
    if _cancel_event.is_set():
        return
    _wait_if_paused(public_url, {"found": len(files), "downloaded": 0, "skipped": 0, "failed": 0})
    resp = client.get(
        PUBLIC_RESOURCES_URL,
        params={"public_key": public_url, "path": path, "limit": 100},
    )
    resp.raise_for_status()
    data = resp.json()
    items = (data.get("_embedded") or {}).get("items") or []
    for item in items:
        if len(files) >= max_files:
            break
        item_type = item.get("type")
        if item_type == "file":
            files.append(item)
        elif item_type == "dir":
            _walk_public_resource(
                client,
                public_url,
                item.get("path") or "/",
                max_files,
                files,
            )


def _wait_if_paused(public_url: str, counts: dict):
    while _pause_event.is_set() and not _cancel_event.is_set():
        graph_db.upsert_sync_state(
            name=SYNC_STATE_NAME,
            enabled=True,
            ok=True,
            source_url=public_url,
            status="paused",
            files_found=counts.get("found", 0),
            files_downloaded=counts.get("downloaded", 0),
            files_skipped=counts.get("skipped", 0),
            files_failed=counts.get("failed", 0),
            last_error=None,
        )
        time.sleep(0.5)


def _download_file(client: httpx.Client, public_url: str, item: dict):
    direct_url = item.get("file")
    for attempt in range(3):
        try:
            if direct_url:
                resp = client.get(direct_url, follow_redirects=True, timeout=30.0)
            else:
                download_resp = client.get(
                    f"{PUBLIC_RESOURCES_URL}/download",
                    params={"public_key": public_url, "path": item.get("path")},
                    timeout=30.0
                )
                download_resp.raise_for_status()
                href = download_resp.json()["href"]
                resp = client.get(href, follow_redirects=True, timeout=30.0)
            resp.raise_for_status()
            return resp.content, resp.headers.get("content-type")
        except httpx.HTTPError as exc:
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))


def _is_supported(filename: str) -> bool:
    return Path(filename.lower()).suffix in SUPPORTED_EXTENSIONS


def _external_id(item: dict) -> str:
    return (
        item.get("resource_id")
        or item.get("sha256")
        or item.get("md5")
        or item.get("path")
        or item.get("name")
        or item.get("file")
        or "unknown"
    )


def _same_version(existing: dict, version: dict) -> bool:
    if version.get("source_etag") and existing.get("source_etag"):
        return existing["source_etag"] == version["source_etag"]
    if version.get("source_modified") and existing.get("source_modified"):
        return existing["source_modified"] == version["source_modified"]
    return False
