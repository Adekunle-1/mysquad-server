"""
Responsibility: Manage database connections and user account data.
Provides connection pooling (up to 20 concurrent connections) for PostgreSQL,
handles tenant creation/retrieval, and manages OAuth token storage.
Uses context managers to ensure proper connection lifecycle.

Schema: msq_tenants (user profiles) + msq_auth (OAuth tokens per platform).
DDL is managed externally via msq_tables.sql — no CREATE TABLE is done here.

Token strategy:
  - Both access_token and refresh_token are Fernet-encrypted before storage.
  - Access tokens expire every 60 minutes (token_expiry = now() + 60 min).
  - On retrieval, token_expiry is checked: if still valid, the stored access
    token is returned as-is; if expired, the refresh token is used to obtain
    a new access token which is then saved with a fresh expiry.
"""

import os
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from app.logger import setup_logger

logger = setup_logger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")

connection_pool = None

# Access tokens expire after 60 minutes
ACCESS_TOKEN_TTL_MINUTES = 60


def init_connection_pool():
    """Initialize database connection pool for performance."""
    global connection_pool
    if connection_pool is None:
        connection_pool = pool.SimpleConnectionPool(
            1, 20,
            DATABASE_URL,
            cursor_factory=RealDictCursor
        )


@contextmanager
def get_db_connection():
    """
    Get a database connection from the pool.
    Automatically returns it when done.
    Validates connection is alive before use.
    """
    if connection_pool is None:
        init_connection_pool()

    conn = connection_pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        yield conn
    except Exception as e:
        logger.error(f"Connection validation failed: {str(e)}")
        try:
            conn.close()
        except Exception:
            pass
        raise RuntimeError(f"Database connection error: {str(e)}")
    finally:
        try:
            if not conn.closed:
                connection_pool.putconn(conn)
        except Exception:
            logger.warning("Could not return connection to pool")


def init_db():
    """
    Validate database connectivity on startup.
    Schema (msq_tenants, msq_auth, etc.) is managed by msq_tables.sql.
    No DDL is executed here.
    """
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            logger.info("Database connection validated successfully")
    except Exception as e:
        logger.critical(f"Failed to connect to database: {str(e)}")
        raise RuntimeError(
            f"Database connection failed. Check DATABASE_URL and PostgreSQL connection. Error: {str(e)}"
        )


def get_tenant(tenant_id: str):
    """
    Fetch an existing tenant from msq_tenants by tenant_id (UUID).
    Returns merged record including encrypted tokens from msq_auth (google platform).

    Returned dict keys:
        tenant_id, phone_no, full_name, username, email,
        last_language_style, onboarding_completed,
        access_token  (Fernet-encrypted BYTEA as memoryview, None if not connected),
        refresh_token (Fernet-encrypted BYTEA as memoryview, None if not connected),
        token_expiry  (timestamptz, None if not connected),
        token_scope, platform_user_id, platform_email,
        google_connected (bool)

    IMPORTANT: caller must convert memoryview to bytes before passing to crypto.decrypt_token().
    Raises RuntimeError if tenant_id is not found.
    """
    with get_db_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT
                t.id                  AS tenant_id,
                t.phone_no,
                t.full_name,
                t.username,
                t.email,
                t.last_language_style,
                t.onboarding_completed,
                a.access_token,
                a.refresh_token,
                a.token_expiry,
                a.token_scope,
                a.platform_user_id,
                a.platform_email,
                a.is_active           AS google_connected
            FROM msq_tenants t
            LEFT JOIN msq_auth a
                   ON a.tenant_id = t.id
                  AND a.platform  = 'google'
                  AND a.is_active = true
            WHERE t.id = %s;
        """, (tenant_id,))

        user = cur.fetchone()
        cur.close()

        if not user:
            raise RuntimeError(f"Tenant not found: {tenant_id}")

        return user


def is_token_expired(token_expiry) -> bool:
    """
    Check whether the stored access token has expired.
    Adds a 30-second buffer to account for clock skew and network latency.

    Args:
        token_expiry: timestamptz value from msq_auth (datetime or None)

    Returns:
        True if expired or missing, False if still valid
    """
    if not token_expiry:
        return True

    # Ensure timezone-aware comparison
    now = datetime.now(timezone.utc)
    buffer = timedelta(seconds=30)

    if isinstance(token_expiry, datetime):
        if token_expiry.tzinfo is None:
            token_expiry = token_expiry.replace(tzinfo=timezone.utc)
        return now >= (token_expiry - buffer)

    return True


def compute_token_expiry() -> datetime:
    """Return a timezone-aware expiry timestamp 60 minutes from now."""
    return datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES)


def save_tokens(
    tenant_id: str,
    encrypted_access: bytes,
    encrypted_refresh: bytes,
    token_expiry: datetime,
    token_scope: str = None,
    platform_user_id: str = None,
    platform_email: str = None
):
    """
    Upsert encrypted Google tokens for a tenant via msq_upsert_oauth stored procedure.

    Args:
        tenant_id:         UUID string of the tenant.
        encrypted_access:  Fernet-encrypted access_token bytes -> BYTEA.
        encrypted_refresh: Fernet-encrypted refresh_token bytes -> BYTEA.
        token_expiry:      Timezone-aware datetime when access_token expires.
        token_scope:       Space-separated OAuth scopes granted (optional).
        platform_user_id:  Google's unique user ID (sub claim) (optional).
        platform_email:    Email on the Google account (optional).
    """
    with get_db_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT msq_upsert_oauth(
                %s, 'google', %s, %s, %s, %s, %s, %s
            );
        """, (
            tenant_id,
            encrypted_access,
            encrypted_refresh,
            token_expiry,
            token_scope,
            platform_user_id,
            platform_email
        ))

        conn.commit()
        cur.close()


def update_access_token(
    tenant_id: str,
    encrypted_access: bytes,
    token_expiry: datetime
):
    """
    Update only the access_token and token_expiry for an existing active record.
    Called when the access token has expired and a new one is generated from
    the refresh token. Refresh token and other fields are left unchanged.

    Args:
        tenant_id:        UUID string of the tenant.
        encrypted_access: Fernet-encrypted new access_token bytes.
        token_expiry:     New expiry datetime for the access token.
    """
    with get_db_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            UPDATE msq_auth
            SET access_token = %s,
                token_expiry = %s,
                updated_at   = now()
            WHERE tenant_id = %s
              AND platform   = 'google'
              AND is_active  = true;
        """, (encrypted_access, token_expiry, tenant_id))

        conn.commit()
        cur.close()


def clear_tokens(tenant_id: str):
    """
    Deactivate the Google OAuth record for a tenant.
    Sets is_active = false to preserve the audit trail.
    Called when the token is revoked or a refresh attempt fails.
    """
    with get_db_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            UPDATE msq_auth
            SET is_active  = false,
                updated_at = now()
            WHERE tenant_id = %s
              AND platform  = 'google';
        """, (tenant_id,))

        conn.commit()
        cur.close()


def close_all_connections():
    """Close connection pool on app shutdown."""
    global connection_pool
    if connection_pool:
        connection_pool.closeall()
        connection_pool = None