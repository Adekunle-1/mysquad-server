"""
Responsibility: Manage database connections and user account data.
Provides connection pooling (up to 20 concurrent connections) for PostgreSQL,
handles user creation/retrieval, and manages encrypted token storage.
Uses context managers to ensure proper connection lifecycle.
"""

import os
from contextlib import contextmanager
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from app.logger import setup_logger

logger = setup_logger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")

connection_pool = None


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
        # Test connection is alive
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        yield conn
    except Exception as e:
        logger.error(f"Connection validation failed: {str(e)}")
        try:
            conn.close()
        except:
            pass
        raise RuntimeError(f"Database connection error: {str(e)}")
    finally:
        # Only return connection if it's still open
        try:
            if not conn.closed:
                connection_pool.putconn(conn)
        except:
            logger.warning("Could not return connection to pool")


def init_db():
    """
    Initialize database schema on startup.
    Creates myguy_users table with all required constraints.
    Call after dropping DB to ensure clean schema.
    """
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Create table with all constraints explicitly defined
            cur.execute("""
                CREATE TABLE IF NOT EXISTS myguy_users (
                    user_id TEXT PRIMARY KEY NOT NULL,
                    phone_no TEXT UNIQUE NOT NULL,
                    full_name TEXT,
                    username TEXT,
                    email TEXT UNIQUE,
                    interests TEXT DEFAULT '',
                    help_needs TEXT DEFAULT '',
                    last_language_style TEXT DEFAULT 'en',
                    google_refresh_token BYTEA,
                    zoom_refresh_token BYTEA,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Create indexes for fast lookups
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_myguy_users_phone_no 
                ON myguy_users(phone_no);
            """)
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_myguy_users_email 
                ON myguy_users(email);
            """)
            
            conn.commit()
            cur.close()
            logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.critical(f"Failed to initialize database: {str(e)}")
        raise RuntimeError(f"Database initialization failed. Check DATABASE_URL and PostgreSQL connection. Error: {str(e)}")


def get_or_create_user(phone_no: str):
    """
    Upsert user in database by phone number.
    Returns user record with all fields including google_refresh_token.
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        # Try to insert, if exists do nothing
        cur.execute("""
            INSERT INTO myguy_users (phone_no)
            VALUES (%s)
            ON CONFLICT (phone_no) DO NOTHING;
        """, (phone_no,))
        
        # Fetch the user (either just created or existing)
        cur.execute("""
            SELECT * FROM myguy_users WHERE phone_no = %s;
        """, (phone_no,))
        
        user = cur.fetchone()
        conn.commit()
        cur.close()
        
        return user


def save_refresh_token(phone_no: str, encrypted_token: bytes):
    """
    Save encrypted Google refresh token for user.
    Called after successfully getting refresh token from Google.
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE myguy_users
            SET google_refresh_token = %s,
                updated_at = NOW()
            WHERE phone_no = %s;
        """, (encrypted_token, phone_no))
        
        conn.commit()
        cur.close()


def clear_refresh_token(phone_no: str):
    """
    Clear (revoke) the refresh token for a user.
    Called when token is revoked by user or refresh fails.
    Sets the token to NULL in database.
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE myguy_users
            SET google_refresh_token = NULL,
                updated_at = NOW()
            WHERE phone_no = %s;
        """, (phone_no,))
        
        conn.commit()
        cur.close()


def close_all_connections():
    """Close connection pool on app shutdown."""
    global connection_pool
    if connection_pool:
        connection_pool.closeall()
        connection_pool = None
