from __future__ import annotations

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase


def _db_url() -> str:
    url = (
        os.getenv("DATABASE_PUBLIC_URL", "").strip().strip('"').strip("'")
        or os.getenv("DATABASE_URL_PUBLIC", "").strip().strip('"').strip("'")
        or os.getenv("DATABASE_URL", "").strip().strip('"').strip("'")
    )

    # normaliza hostname interno Railway
    url = url.replace(
        "Postgres.railway.internal",
        "postgres.railway.internal"
    )

    if not url:
        return ""

    # Railway às vezes entrega postgres://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    return url


class Base(DeclarativeBase):
    pass


def make_engine():
    url = _db_url()

    if not url:
        return None

    pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        connect_args={"connect_timeout": connect_timeout},
    )


ENGINE = make_engine()

SessionLocal = (
    sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=ENGINE
    )
    if ENGINE else None
)


# =========================
# CORE AUTH TABLES
# =========================

def _reconcile_core_auth_schema_boot():

    if ENGINE is None:
        return

    try:

        with ENGINE.begin() as conn:

            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR PRIMARY KEY,
                org_slug VARCHAR,
                email VARCHAR UNIQUE NOT NULL,
                full_name VARCHAR,
                password_hash VARCHAR,
                is_active BOOLEAN DEFAULT TRUE,
                created_at BIGINT
            )
            """))

            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS otp_codes (
                id VARCHAR PRIMARY KEY,
                email VARCHAR NOT NULL,
                code_hash VARCHAR NOT NULL,
                expires_at BIGINT,
                used BOOLEAN DEFAULT FALSE,
                created_at BIGINT
            )
            """))

            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR,
                session_token VARCHAR,
                expires_at BIGINT,
                created_at BIGINT
            )
            """))

            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS threads (
                id VARCHAR PRIMARY KEY,
                org_slug VARCHAR,
                created_by VARCHAR,
                created_at BIGINT
            )
            """))

            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id VARCHAR PRIMARY KEY,
                thread_id VARCHAR,
                role VARCHAR,
                content TEXT,
                created_at BIGINT
            )
            """))

        print("CORE_AUTH_SCHEMA_BOOT_OK")

    except Exception as e:
        print("CORE_AUTH_SCHEMA_BOOT_FAILED", str(e))


# =========================
# FILES + SIGNUP CODES
# =========================

def _reconcile_files_schema_boot():

    if ENGINE is None:
        return

    try:

        with ENGINE.begin() as conn:

            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS files (
                id VARCHAR PRIMARY KEY,
                org_slug VARCHAR,
                thread_id VARCHAR,
                uploader_id VARCHAR,
                uploader_name VARCHAR,
                uploader_email VARCHAR,
                filename VARCHAR,
                original_filename VARCHAR,
                origin VARCHAR,
                scope_thread_id VARCHAR,
                scope_agent_id VARCHAR,
                mime_type VARCHAR,
                size_bytes BIGINT DEFAULT 0,
                content BYTEA,
                extraction_failed BOOLEAN DEFAULT FALSE,
                is_institutional BOOLEAN DEFAULT FALSE,
                created_at BIGINT,
                origin_thread_id VARCHAR
            )
            """))

            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS signup_codes (
                id VARCHAR PRIMARY KEY,
                org_slug VARCHAR NOT NULL,
                code_hash VARCHAR NOT NULL,
                label VARCHAR NOT NULL,
                source VARCHAR NOT NULL,
                expires_at BIGINT,
                max_uses INTEGER DEFAULT 500,
                used_count INTEGER DEFAULT 0,
                active BOOLEAN DEFAULT TRUE,
                created_at BIGINT,
                created_by VARCHAR
            )
            """))

        print("FILES_SCHEMA_RECONCILE_DB_BOOT_OK")

    except Exception as e:
        print("FILES_SCHEMA_RECONCILE_DB_BOOT_FAILED", str(e))


# =========================
# EXECUTE BOOTSTRAP
# =========================

_reconcile_core_auth_schema_boot()
_reconcile_files_schema_boot()


# =========================
# DB SESSION DEPENDENCY
# =========================

def get_db():

    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL not configured")

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()
