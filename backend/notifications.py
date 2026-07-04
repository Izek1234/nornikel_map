"""Internal + email notification system for NORNIKEL Knowledge Map.

Stores notifications in Neo4j, sends email digests via SMTP.
"""

import logging
import os
import smtplib
import time
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import graph_db

logger = logging.getLogger(__name__)

# ── SMTP config from env ────────────────────────────────────────
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)
EMAIL_ENABLED = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)

# ── Notification types ──────────────────────────────────────────
NOTIFICATION_TYPES = {
    "new_document": "Новый документ загружен",
    "document_processed": "Документ обработан",
    "new_experiment": "Новый эксперимент",
    "domain_update": "Обновление по домену",
    "system": "Системное уведомление",
}


def init_notification_schema():
    """Create constraints for Notification nodes. Idempotent."""
    statements = [
        "CREATE CONSTRAINT notif_id IF NOT EXISTS FOR (n:Notification) REQUIRE n.id IS UNIQUE",
        "CREATE INDEX notif_user IF NOT EXISTS FOR (n:Notification) ON (n.user_id)",
        "CREATE INDEX notif_ts IF NOT EXISTS FOR (n:Notification) ON (n.created_at)",
        "CREATE INDEX sub_user IF NOT EXISTS FOR (s:Subscription) ON (s.user_id)",
    ]
    for stmt in statements:
        graph_db.run(stmt)


# ── Notifications CRUD ──────────────────────────────────────────

def create_notification(
    user_id: str,
    notif_type: str,
    title: str,
    body: str = "",
    link: str = "",
    meta: dict | None = None,
) -> dict:
    """Create a notification for a user."""
    import json
    notif_id = uuid.uuid4().hex[:16]
    ts = time.time()

    graph_db.run(
        """
        CREATE (n:Notification {
            id: $id, user_id: $uid, type: $type,
            title: $title, body: $body, link: $link,
            meta_json: $meta, read: false, created_at: $ts
        })
        """,
        id=notif_id, uid=user_id, type=notif_type,
        title=title, body=body, link=link,
        meta=json.dumps(meta or {}), ts=ts,
    )

    return {"id": notif_id, "type": notif_type, "title": title, "created_at": ts}


def get_user_notifications(user_id: str, limit: int = 50, unread_only: bool = False) -> list[dict]:
    """Get notifications for a user."""
    import json
    where = "WHERE n.user_id = $uid"
    if unread_only:
        where += " AND n.read = false"

    rows = graph_db.run(
        f"""
        MATCH (n:Notification)
        {where}
        RETURN n.id AS id, n.type AS type, n.title AS title,
               n.body AS body, n.link AS link, n.meta_json AS meta_json,
               n.read AS read, n.created_at AS created_at
        ORDER BY n.created_at DESC
        LIMIT $lim
        """,
        uid=user_id, lim=limit,
    )

    result = []
    for row in rows:
        try:
            meta = json.loads(row.get("meta_json") or "{}")
        except Exception:
            meta = {}
        result.append({
            "id": row["id"],
            "type": row["type"],
            "title": row["title"],
            "body": row.get("body") or "",
            "link": row.get("link") or "",
            "meta": meta,
            "read": bool(row.get("read")),
            "created_at": row["created_at"],
        })
    return result


def get_unread_count(user_id: str) -> int:
    """Get count of unread notifications."""
    rows = graph_db.run(
        "MATCH (n:Notification {user_id: $uid, read: false}) RETURN count(n) AS cnt",
        uid=user_id,
    )
    return rows[0]["cnt"] if rows else 0


def mark_read(user_id: str, notification_id: str | None = None):
    """Mark notification(s) as read. If notification_id is None, mark all."""
    if notification_id:
        graph_db.run(
            "MATCH (n:Notification {user_id: $uid, id: $nid}) SET n.read = true",
            uid=user_id, nid=notification_id,
        )
    else:
        graph_db.run(
            "MATCH (n:Notification {user_id: $uid}) SET n.read = true",
            uid=user_id,
        )


def delete_notification(user_id: str, notification_id: str):
    """Delete a specific notification."""
    graph_db.run(
        "MATCH (n:Notification {user_id: $uid, id: $nid}) DETACH DELETE n",
        uid=user_id, nid=notification_id,
    )


def clear_user_notifications(user_id: str):
    """Delete all notifications for a user."""
    graph_db.run("MATCH (n:Notification {user_id: $uid}) DETACH DELETE n", uid=user_id)


# ── Subscriptions ───────────────────────────────────────────────

def subscribe(user_id: str, domain: str | None = None, keywords: list[str] | None = None, email: str = ""):
    """Subscribe a user to notifications about a domain or keywords."""
    sub_id = uuid.uuid4().hex[:12]
    graph_db.run(
        """
        MERGE (s:Subscription {user_id: $uid, domain: $domain})
        SET s.id = $id, s.keywords = $keywords, s.email = $email, s.created_at = $ts
        """,
        uid=user_id, domain=domain or "all",
        id=sub_id, keywords=keywords or [], email=email, ts=time.time(),
    )
    return {"id": sub_id, "domain": domain, "keywords": keywords}


def get_user_subscriptions(user_id: str) -> list[dict]:
    """Get all subscriptions for a user."""
    rows = graph_db.run(
        """
        MATCH (s:Subscription {user_id: $uid})
        RETURN s.id AS id, s.domain AS domain, s.keywords AS keywords,
               s.email AS email, s.created_at AS created_at
        ORDER BY s.created_at DESC
        """,
        uid=user_id,
    )
    return [
        {"id": r["id"], "domain": r["domain"], "keywords": r.get("keywords") or [],
         "email": r.get("email") or "", "created_at": r["created_at"]}
        for r in rows
    ]


def delete_subscription(user_id: str, sub_id: str):
    """Delete a subscription."""
    graph_db.run(
        "MATCH (s:Subscription {user_id: $uid, id: $sid}) DETACH DELETE s",
        uid=user_id, sid=sub_id,
    )


# ── Dispatch: create notifications + send emails ────────────────

def dispatch(event_type: str, title: str, body: str = "", link: str = "", meta: dict | None = None):
    """Create notifications for all subscribers matching the event.

    Checks domain subscriptions and keyword matches.
    """
    import domains as dom_module

    # Find all subscriptions
    rows = graph_db.run(
        "MATCH (s:Subscription) RETURN s.user_id AS uid, s.domain AS domain, "
        "s.keywords AS keywords, s.email AS email"
    )

    for row in rows:
        uid = row["uid"]
        sub_domain = row.get("domain") or "all"
        sub_keywords = row.get("keywords") or []
        sub_email = row.get("email") or ""

        # Check if event matches subscription
        match = False
        if sub_domain == "all":
            match = True
        elif event_type == "domain_update" and meta:
            event_domain = (meta.get("domain") or "").lower()
            match = event_domain == sub_domain.lower()
        elif event_type in ("new_document", "document_processed"):
            # Check if content matches domain
            text = f"{title} {body}"
            detected = dom_module.classify_text(text, min_matches=1)
            match = sub_domain.lower() in detected
        elif sub_keywords:
            text = f"{title} {body}".lower()
            match = any(kw.lower() in text for kw in sub_keywords)

        if match:
            create_notification(uid, event_type, title, body, link, meta)

            # Send email if enabled and user has email
            if EMAIL_ENABLED and sub_email:
                _send_email(sub_email, title, body)


def _send_email(to: str, subject: str, body: str):
    """Send an email notification via SMTP."""
    if not EMAIL_ENABLED:
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Nornickel Knowledge Map] {subject}"
        msg["From"] = SMTP_FROM
        msg["To"] = to

        html = f"""
        <html><body style="font-family: -apple-system, sans-serif; color: #333; padding: 20px;">
        <h2 style="color: #1a1a2e;">NORNIKEL Knowledge Map</h2>
        <h3>{subject}</h3>
        <p>{body}</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #999;">Система уведомлений карты знаний R&D</p>
        </body></html>
        """

        msg.attach(MIMEText(body, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to], msg.as_string())

        logger.info("Email sent to %s: %s", to, subject)
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to, e)
