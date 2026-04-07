from __future__ import annotations
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

def _db_url() -> str:
    url = os.getenv("DATABASE_PUBLIC_URL", "").strip().strip("\"").strip("\'") or os.getenv("DATABASE_URL_PUBLIC", "").strip().strip("\"").strip("\'") or os.getenv("DATABASE_URL", "").strip().strip("\"").strip("\'")
    # Normalize Railway internal hostname casing
    url = url.replace("Postgres.railway.internal", "postgres.railway.internal")
    if not url:
        return ""
    # Railway sometimes provides postgres:// -> SQLAlchemy prefers postgresql://
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
    # PATCH0100_13: connect_timeout prevents startup from hanging when DB is
    # unreachable (e.g. Railway private-network DNS not yet ready).  Without
    # this, psycopg2 blocks on TCP connect indefinitely, causing uvicorn to
    # never emit "Application startup complete" and Railway to return 502.
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
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE) if ENGINE else None


def _reconcile_files_schema_boot():
    if ENGINE is None:
        return

    try:
        with ENGINE.begin() as conn:
            # Create critical tables first so later reconcile statements never explode
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
                max_uses INTEGER NOT NULL DEFAULT 500,
                used_count INTEGER NOT NULL DEFAULT 0,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at BIGINT NOT NULL,
                created_by VARCHAR
            )
            """))

            stmts = [
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS thread_id VARCHAR",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS uploader_id VARCHAR",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS uploader_name VARCHAR",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS uploader_email VARCHAR",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS org_slug VARCHAR",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS filename VARCHAR",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS original_filename VARCHAR",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS origin VARCHAR",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS scope_thread_id VARCHAR",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS scope_agent_id VARCHAR",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS mime_type VARCHAR",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS size_bytes BIGINT NOT NULL DEFAULT 0",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS content BYTEA",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS extraction_failed BOOLEAN NOT NULL DEFAULT FALSE",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS is_institutional BOOLEAN NOT NULL DEFAULT FALSE",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS created_at BIGINT",
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS origin_thread_id VARCHAR",
                "CREATE INDEX IF NOT EXISTS ix_files_thread_id ON files(thread_id)",
                "CREATE INDEX IF NOT EXISTS ix_files_scope_thread_id ON files(scope_thread_id)",
                "CREATE INDEX IF NOT EXISTS ix_files_scope_agent_id ON files(scope_agent_id)",
                "CREATE INDEX IF NOT EXISTS ix_signup_codes_org ON signup_codes(org_slug)",
            ]
            for stmt in stmts:
                conn.execute(text(stmt))

        print("FILES_SCHEMA_RECONCILE_DB_BOOT_OK")
    except Exception as e:
        print("FILES_SCHEMA_RECONCILE_DB_BOOT_FAILED", str(e))


_reconcile_files_schema_boot()


def get_db():
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
