"""JWT authentication and RBAC for NORNIKEL Knowledge Map.

User storage: Neo4j. Falls back to in-memory if Neo4j is unavailable (DEMO mode).
"""

import hashlib
import hmac
import logging
import os
import secrets
import time
import uuid

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

SECRET_KEY = os.environ.get("AUTH_SECRET_KEY", "nornikel-dev-secret-change-in-prod")
ALGORITHM = "HS256"
TOKEN_EXPIRE_SECONDS = 86400 * 7  # 7 days
_SALT_LENGTH = 32

bearer_scheme = HTTPBearer(auto_error=False)

ROLES = ("researcher", "analyst", "project_manager", "admin", "external_partner")

# In-memory fallback for DEMO mode (no Neo4j)
_users: dict[str, dict] = {}
_use_neo4j = False


# ── Password hashing ────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_hex(_SALT_LENGTH)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}:{h.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        salt, expected_hex = hashed.split(":", 1)
        h = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 100_000)
        return hmac.compare_digest(h.hex(), expected_hex)
    except Exception:
        return False


# ── Neo4j helpers ───────────────────────────────────────────────

def _neo4j_available() -> bool:
    try:
        import graph_db
        graph_db.run("RETURN 1 AS ok")
        return True
    except Exception:
        return False


def init_user_schema():
    """Create constraints for User nodes. Idempotent."""
    global _use_neo4j
    try:
        import graph_db
        graph_db.run("CREATE CONSTRAINT user_username IF NOT EXISTS FOR (u:User) REQUIRE u.username IS UNIQUE")
        graph_db.run("CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE")
        _use_neo4j = True
        logger.info("User schema initialized in Neo4j")
    except Exception as e:
        logger.warning("Neo4j unavailable for users, using in-memory: %s", e)
        _use_neo4j = False


def _neo4j_create_user(user_id: str, username: str, password_hash: str, role: str, display_name: str) -> dict:
    import graph_db
    graph_db.run(
        """
        CREATE (u:User {
            id: $id, username: $username, password_hash: $password_hash,
            role: $role, display_name: $display_name, created_at: $ts
        })
        """,
        id=user_id, username=username, password_hash=password_hash,
        role=role, display_name=display_name, ts=time.time(),
    )
    return {"id": user_id, "username": username, "role": role, "display_name": display_name}


def _neo4j_get_user(username: str) -> dict | None:
    import graph_db
    rows = graph_db.run(
        "MATCH (u:User {username: $u}) RETURN u.id AS id, u.username AS username, "
        "u.password_hash AS password_hash, u.role AS role, u.display_name AS display_name",
        u=username,
    )
    return rows[0] if rows else None


def _neo4j_user_exists(username: str) -> bool:
    import graph_db
    rows = graph_db.run(
        "MATCH (u:User {username: $u}) RETURN u.username AS u LIMIT 1",
        u=username,
    )
    return len(rows) > 0


# ── Public API ──────────────────────────────────────────────────

def create_user(username: str, password: str, role: str = "researcher", display_name: str = "") -> dict:
    if role not in ROLES:
        raise HTTPException(400, f"Недопустимая роль. Допустимые: {', '.join(ROLES)}")

    # Check if user already exists
    if _use_neo4j:
        if _neo4j_user_exists(username):
            raise HTTPException(409, "Пользователь уже существует")
    else:
        if username in _users:
            raise HTTPException(409, "Пользователь уже существует")

    user_id = uuid.uuid4().hex[:12]
    password_hash = hash_password(password)
    display = display_name or username

    if _use_neo4j:
        return _neo4j_create_user(user_id, username, password_hash, role, display)

    _users[username] = {
        "id": user_id, "username": username, "password_hash": password_hash,
        "role": role, "display_name": display, "created_at": time.time(),
    }
    return {"id": user_id, "username": username, "role": role, "display_name": display}


def authenticate_user(username: str, password: str) -> dict | None:
    if _use_neo4j:
        user = _neo4j_get_user(username)
    else:
        user = _users.get(username)

    if not user or not verify_password(password, user["password_hash"]):
        return None
    return {"id": user["id"], "username": user["username"], "role": user["role"], "display_name": user["display_name"]}


def create_token(user_data: dict) -> str:
    payload = {
        "sub": user_data["id"],
        "username": user_data["username"],
        "role": user_data["role"],
        "display_name": user_data.get("display_name", ""),
        "exp": time.time() + TOKEN_EXPIRE_SECONDS,
        "iat": time.time(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except jwt.PyJWTError:
        return None


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict | None:
    if not creds:
        return None
    return decode_token(creds.credentials)


def require_user(user: dict | None = Depends(get_current_user)) -> dict:
    if not user:
        raise HTTPException(401, "Требуется авторизация")
    return user


def require_role(*allowed_roles: str):
    def _check(user: dict = Depends(require_user)) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(403, "Недостаточно прав")
        return user
    return _check


def seed_admin():
    """Create default admin accounts if no users exist."""
    if _use_neo4j:
        import graph_db
        rows = graph_db.run("MATCH (u:User) RETURN count(u) AS cnt")
        count = rows[0]["cnt"] if rows else 0
        if count == 0:
            create_user("admin", "admin", role="admin", display_name="Администратор")
            create_user("researcher", "researcher", role="researcher", display_name="Исследователь")
            create_user("analyst", "analyst", role="analyst", display_name="Аналитик")
            logger.info("Default users created in Neo4j")
    else:
        if not _users:
            create_user("admin", "admin", role="admin", display_name="Администратор")
            create_user("researcher", "researcher", role="researcher", display_name="Исследователь")
            create_user("analyst", "analyst", role="analyst", display_name="Аналитик")
            logger.info("Default users created in memory")
