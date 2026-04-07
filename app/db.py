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
    # unreachable (e.g. Railway private-network DNS not yet ready). Without
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


def _reconcile_core_auth_schema_boot():
    if ENGINE is None:
        return

    try:
        with ENGINE.begin() as conn:
            # =========================
            # USERS
            # =========================
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR PRIMARY KEY,
                org_slug VARCHAR,
                email VARCHAR UNIQUE NOT NULL,
                name VARCHAR,
                role VARCHAR DEFAULT 'user',
                salt VARCHAR,
                pw_hash VARCHAR,
                created_at BIGINT,
                approved_at BIGINT,
                signup_code_label VARCHAR,
                signup_source VARCHAR,
                usage_tier VARCHAR,
                terms_accepted_at BIGINT,
                terms_version VARCHAR,
                marketing_consent BOOLEAN DEFAULT FALSE,
                company VARCHAR,
                profile_role VARCHAR,
                user_type VARCHAR,
                intent VARCHAR,
                notes TEXT,
                country VARCHAR,
                language VARCHAR,
                whatsapp VARCHAR,
                onboarding_completed BOOLEAN DEFAULT FALSE,
                full_name VARCHAR,
                password_hash VARCHAR,
                is_active BOOLEAN DEFAULT TRUE
            )
            """))

            stmts = [
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS org_slug VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS email VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS name VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS role VARCHAR DEFAULT 'user'",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS salt VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS pw_hash VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS created_at BIGINT",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS approved_at BIGINT",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS signup_code_label VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS signup_source VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS usage_tier VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS terms_accepted_at BIGINT",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS terms_version VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS marketing_consent BOOLEAN DEFAULT FALSE",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS company VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS profile_role VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS user_type VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS intent VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS notes TEXT",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS country VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS language VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS whatsapp VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT FALSE",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS full_name VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS password_hash VARCHAR",
                "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
                "CREATE INDEX IF NOT EXISTS ix_users_org_slug ON users(org_slug)",
                "CREATE INDEX IF NOT EXISTS ix_users_email ON users(email)",
                "CREATE INDEX IF NOT EXISTS ix_users_role ON users(role)",
                "CREATE INDEX IF NOT EXISTS ix_users_created_at ON users(created_at)",
                "CREATE INDEX IF NOT EXISTS ix_users_org_email ON users(org_slug, email)",
            ]
            for stmt in stmts:
                conn.execute(text(stmt))

            conn.execute(text("""
            UPDATE users
            SET pw_hash = password_hash
            WHERE pw_hash IS NULL
              AND password_hash IS NOT NULL
            """))
            conn.execute(text("""
            UPDATE users
            SET password_hash = pw_hash
            WHERE password_hash IS NULL
              AND pw_hash IS NOT NULL
            """))
            conn.execute(text("""
            UPDATE users
            SET full_name = name
            WHERE full_name IS NULL
              AND name IS NOT NULL
            """))
            conn.execute(text("""
            UPDATE users
            SET name = full_name
            WHERE name IS NULL
              AND full_name IS NOT NULL
            """))
            conn.execute(text("UPDATE users SET role = 'user' WHERE role IS NULL"))
            conn.execute(text("UPDATE users SET is_active = TRUE WHERE is_active IS NULL"))
            conn.execute(text("UPDATE users SET onboarding_completed = FALSE WHERE onboarding_completed IS NULL"))
            conn.execute(text("UPDATE users SET marketing_consent = FALSE WHERE marketing_consent IS NULL"))

            # =========================
            # OTP_CODES
            # =========================
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS otp_codes (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR,
                code_hash VARCHAR NOT NULL,
                expires_at BIGINT,
                attempts INTEGER DEFAULT 0,
                verified BOOLEAN DEFAULT FALSE,
                created_at BIGINT
            )
            """))

            stmts = [
                "ALTER TABLE IF EXISTS otp_codes ADD COLUMN IF NOT EXISTS user_id VARCHAR",
                "ALTER TABLE IF EXISTS otp_codes ADD COLUMN IF NOT EXISTS code_hash VARCHAR",
                "ALTER TABLE IF EXISTS otp_codes ADD COLUMN IF NOT EXISTS expires_at BIGINT",
                "ALTER TABLE IF EXISTS otp_codes ADD COLUMN IF NOT EXISTS attempts INTEGER DEFAULT 0",
                "ALTER TABLE IF EXISTS otp_codes ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE",
                "ALTER TABLE IF EXISTS otp_codes ADD COLUMN IF NOT EXISTS created_at BIGINT",
                "CREATE INDEX IF NOT EXISTS ix_otp_codes_user_id ON otp_codes(user_id)",
                "ALTER TABLE IF EXISTS otp_codes ADD COLUMN IF NOT EXISTS email VARCHAR",
                "ALTER TABLE IF EXISTS otp_codes ADD COLUMN IF NOT EXISTS used BOOLEAN DEFAULT FALSE",
                "CREATE INDEX IF NOT EXISTS ix_otp_codes_email ON otp_codes(email)",
            ]
            for stmt in stmts:
                conn.execute(text(stmt))

            # =========================
            # USER_SESSIONS
            # =========================
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR,
                org_slug VARCHAR,
                login_at BIGINT,
                logout_at BIGINT,
                last_seen_at BIGINT,
                ended_reason VARCHAR,
                duration_seconds INTEGER,
                source_code_label VARCHAR,
                usage_tier VARCHAR,
                ip_address VARCHAR
            )
            """))

            stmts = [
                "ALTER TABLE IF EXISTS user_sessions ADD COLUMN IF NOT EXISTS user_id VARCHAR",
                "ALTER TABLE IF EXISTS user_sessions ADD COLUMN IF NOT EXISTS org_slug VARCHAR",
                "ALTER TABLE IF EXISTS user_sessions ADD COLUMN IF NOT EXISTS login_at BIGINT",
                "ALTER TABLE IF EXISTS user_sessions ADD COLUMN IF NOT EXISTS logout_at BIGINT",
                "ALTER TABLE IF EXISTS user_sessions ADD COLUMN IF NOT EXISTS last_seen_at BIGINT",
                "ALTER TABLE IF EXISTS user_sessions ADD COLUMN IF NOT EXISTS ended_reason VARCHAR",
                "ALTER TABLE IF EXISTS user_sessions ADD COLUMN IF NOT EXISTS duration_seconds INTEGER",
                "ALTER TABLE IF EXISTS user_sessions ADD COLUMN IF NOT EXISTS source_code_label VARCHAR",
                "ALTER TABLE IF EXISTS user_sessions ADD COLUMN IF NOT EXISTS usage_tier VARCHAR",
                "ALTER TABLE IF EXISTS user_sessions ADD COLUMN IF NOT EXISTS ip_address VARCHAR",
                "ALTER TABLE IF EXISTS user_sessions ADD COLUMN IF NOT EXISTS session_token VARCHAR",
                "ALTER TABLE IF EXISTS user_sessions ADD COLUMN IF NOT EXISTS expires_at BIGINT",
                "ALTER TABLE IF EXISTS user_sessions ADD COLUMN IF NOT EXISTS created_at BIGINT",
                "CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id ON user_sessions(user_id)",
                "CREATE INDEX IF NOT EXISTS ix_user_sessions_org_slug ON user_sessions(org_slug)",
            ]
            for stmt in stmts:
                conn.execute(text(stmt))

            # =========================
            # TERMS_ACCEPTANCES
            # =========================
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS terms_acceptances (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                terms_version VARCHAR NOT NULL,
                accepted_at BIGINT NOT NULL,
                ip_address VARCHAR,
                user_agent VARCHAR
            )
            """))

            stmts = [
                "ALTER TABLE IF EXISTS terms_acceptances ADD COLUMN IF NOT EXISTS user_id VARCHAR",
                "ALTER TABLE IF EXISTS terms_acceptances ADD COLUMN IF NOT EXISTS terms_version VARCHAR",
                "ALTER TABLE IF EXISTS terms_acceptances ADD COLUMN IF NOT EXISTS accepted_at BIGINT",
                "ALTER TABLE IF EXISTS terms_acceptances ADD COLUMN IF NOT EXISTS ip_address VARCHAR",
                "ALTER TABLE IF EXISTS terms_acceptances ADD COLUMN IF NOT EXISTS user_agent VARCHAR",
                "CREATE INDEX IF NOT EXISTS ix_terms_acceptances_user_id ON terms_acceptances(user_id)",
            ]
            for stmt in stmts:
                conn.execute(text(stmt))

            # =========================
            # MARKETING_CONSENTS
            # =========================
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS marketing_consents (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR,
                contact_id VARCHAR,
                channel VARCHAR NOT NULL,
                opt_in_date BIGINT,
                opt_out_date BIGINT,
                ip VARCHAR,
                source VARCHAR,
                created_at BIGINT NOT NULL
            )
            """))

            stmts = [
                "ALTER TABLE IF EXISTS marketing_consents ADD COLUMN IF NOT EXISTS user_id VARCHAR",
                "ALTER TABLE IF EXISTS marketing_consents ADD COLUMN IF NOT EXISTS contact_id VARCHAR",
                "ALTER TABLE IF EXISTS marketing_consents ADD COLUMN IF NOT EXISTS channel VARCHAR",
                "ALTER TABLE IF EXISTS marketing_consents ADD COLUMN IF NOT EXISTS opt_in_date BIGINT",
                "ALTER TABLE IF EXISTS marketing_consents ADD COLUMN IF NOT EXISTS opt_out_date BIGINT",
                "ALTER TABLE IF EXISTS marketing_consents ADD COLUMN IF NOT EXISTS ip VARCHAR",
                "ALTER TABLE IF EXISTS marketing_consents ADD COLUMN IF NOT EXISTS source VARCHAR",
                "ALTER TABLE IF EXISTS marketing_consents ADD COLUMN IF NOT EXISTS created_at BIGINT",
                "CREATE INDEX IF NOT EXISTS ix_marketing_consents_user_id ON marketing_consents(user_id)",
            ]
            for stmt in stmts:
                conn.execute(text(stmt))

            # =========================
            # THREADS
            # =========================
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS threads (
                id VARCHAR PRIMARY KEY,
                org_slug VARCHAR,
                title VARCHAR,
                created_by VARCHAR,
                created_at BIGINT
            )
            """))

            stmts = [
                "ALTER TABLE IF EXISTS threads ADD COLUMN IF NOT EXISTS org_slug VARCHAR",
                "ALTER TABLE IF EXISTS threads ADD COLUMN IF NOT EXISTS title VARCHAR",
                "ALTER TABLE IF EXISTS threads ADD COLUMN IF NOT EXISTS created_by VARCHAR",
                "ALTER TABLE IF EXISTS threads ADD COLUMN IF NOT EXISTS created_at BIGINT",
                "CREATE INDEX IF NOT EXISTS ix_threads_org_slug ON threads(org_slug)",
            ]
            for stmt in stmts:
                conn.execute(text(stmt))

            # =========================
            # MESSAGES
            # =========================
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id VARCHAR PRIMARY KEY,
                org_slug VARCHAR,
                thread_id VARCHAR,
                user_id VARCHAR,
                user_name VARCHAR,
                role VARCHAR,
                content TEXT,
                agent_id VARCHAR,
                agent_name VARCHAR,
                client_message_id VARCHAR,
                created_at BIGINT
            )
            """))

            stmts = [
                "ALTER TABLE IF EXISTS messages ADD COLUMN IF NOT EXISTS org_slug VARCHAR",
                "ALTER TABLE IF EXISTS messages ADD COLUMN IF NOT EXISTS thread_id VARCHAR",
                "ALTER TABLE IF EXISTS messages ADD COLUMN IF NOT EXISTS user_id VARCHAR",
                "ALTER TABLE IF EXISTS messages ADD COLUMN IF NOT EXISTS user_name VARCHAR",
                "ALTER TABLE IF EXISTS messages ADD COLUMN IF NOT EXISTS role VARCHAR",
                "ALTER TABLE IF EXISTS messages ADD COLUMN IF NOT EXISTS content TEXT",
                "ALTER TABLE IF EXISTS messages ADD COLUMN IF NOT EXISTS agent_id VARCHAR",
                "ALTER TABLE IF EXISTS messages ADD COLUMN IF NOT EXISTS agent_name VARCHAR",
                "ALTER TABLE IF EXISTS messages ADD COLUMN IF NOT EXISTS client_message_id VARCHAR",
                "ALTER TABLE IF EXISTS messages ADD COLUMN IF NOT EXISTS created_at BIGINT",
                "CREATE INDEX IF NOT EXISTS ix_messages_thread_id ON messages(thread_id)",
                "CREATE INDEX IF NOT EXISTS ix_messages_org_thread ON messages(org_slug, thread_id)",
            ]
            for stmt in stmts:
                conn.execute(text(stmt))

        print("CORE_AUTH_SCHEMA_BOOT_OK")
    except Exception as e:
        print("CORE_AUTH_SCHEMA_BOOT_FAILED", str(e))


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
                origin_thread_id VARCHAR,
                name VARCHAR
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
                "ALTER TABLE IF EXISTS files ADD COLUMN IF NOT EXISTS name VARCHAR",
                "CREATE INDEX IF NOT EXISTS ix_files_thread_id ON files(thread_id)",
                "CREATE INDEX IF NOT EXISTS ix_files_scope_thread_id ON files(scope_thread_id)",
                "CREATE INDEX IF NOT EXISTS ix_files_scope_agent_id ON files(scope_agent_id)",
                "CREATE INDEX IF NOT EXISTS ix_signup_codes_org ON signup_codes(org_slug)",
            ]
            for stmt in stmts:
                conn.execute(text(stmt))

            # compatibilidade com schema legado de files
            conn.execute(text("""
            UPDATE files
            SET name = filename
            WHERE name IS NULL
              AND filename IS NOT NULL
            """))

        print("FILES_SCHEMA_RECONCILE_DB_BOOT_OK")
    except Exception as e:
        print("FILES_SCHEMA_RECONCILE_DB_BOOT_FAILED", str(e))


_reconcile_core_auth_schema_boot()
_reconcile_files_schema_boot()


def get_db():
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
