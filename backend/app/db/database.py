import os
import re
import json
import uuid
import math
import sqlite3
import bcrypt
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from app.core.config import settings
from app.core.logging_config import SafeLogger

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

class DatabaseManager:
    """Manages SQLite database connections, schemas, migrations, transactions, and seeding."""

    def __init__(self):
        self.db_path = settings.get_database_path()

    def get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def init_db(self) -> None:
        """Initializes tables, indexes, and initial seeds."""
        with self.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    full_name TEXT NOT NULL,
                    hashed_password TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('CUSTOMER', 'OWNER')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS catalogues (
                    id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    name TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    record_count INTEGER NOT NULL DEFAULT 0,
                    valid_count INTEGER NOT NULL DEFAULT 0,
                    invalid_count INTEGER NOT NULL DEFAULT 0,
                    validation_report TEXT,
                    status TEXT NOT NULL CHECK(status IN ('UPLOADED', 'VALIDATED', 'IMPORTED', 'INDEX_BUILDING', 'READY_FOR_ACTIVATION', 'ACTIVE', 'ARCHIVED', 'FAILED')),
                    is_active INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    activated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    catalogue_id TEXT NOT NULL REFERENCES catalogues(id) ON DELETE CASCADE,
                    product_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    price REAL NOT NULL,
                    stock_status TEXT NOT NULL,
                    rating REAL,
                    attributes TEXT,
                    is_archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(catalogue_id, product_id)
                );

                CREATE TABLE IF NOT EXISTS policy_documents (
                    id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sections TEXT,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    customer_email TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,
                    product_id TEXT,
                    conversation_id TEXT,
                    message TEXT NOT NULL,
                    rating INTEGER,
                    status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'UNDER_REVIEW', 'RESOLVED', 'REJECTED')),
                    is_demo INTEGER NOT NULL DEFAULT 0,
                    owner_resolution_note TEXT,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    reviewed_by TEXT
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    actor_id TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    details TEXT,
                    timestamp TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    dataset_name TEXT NOT NULL,
                    total_questions INTEGER NOT NULL,
                    passed_count INTEGER NOT NULL,
                    failed_count INTEGER NOT NULL,
                    citation_validity_rate REAL NOT NULL,
                    unsupported_claim_rate REAL NOT NULL,
                    refusal_accuracy REAL NOT NULL,
                    clarification_accuracy REAL NOT NULL,
                    avg_latency_ms REAL NOT NULL,
                    results_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_products_cat_id ON products(catalogue_id);
                CREATE INDEX IF NOT EXISTS idx_products_prod_id ON products(product_id);
                CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
                CREATE INDEX IF NOT EXISTS idx_products_price ON products(price);
                CREATE INDEX IF NOT EXISTS idx_products_stock ON products(stock_status);
                CREATE INDEX IF NOT EXISTS idx_catalogues_active ON catalogues(is_active);
                CREATE INDEX IF NOT EXISTS idx_feedback_customer ON feedback(customer_id);
                CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback(status);
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);

                CREATE TABLE IF NOT EXISTS dataset_metadata (
                    id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    name TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'PRODUCT_CATALOGUE',
                    owner_id TEXT NOT NULL,
                    record_count INTEGER NOT NULL DEFAULT 0,
                    valid_count INTEGER NOT NULL DEFAULT 0,
                    invalid_count INTEGER NOT NULL DEFAULT 0,
                    schema_mapping TEXT,
                    validation_report TEXT,
                    embedding_status TEXT NOT NULL DEFAULT 'PENDING',
                    embedding_model TEXT,
                    status TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    activated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS dataset_records (
                    id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL REFERENCES dataset_metadata(id) ON DELETE CASCADE,
                    category TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    product_reference TEXT,
                    title TEXT NOT NULL,
                    content_text TEXT,
                    numeric_value REAL,
                    currency TEXT DEFAULT 'INR',
                    rating REAL,
                    date_observed TEXT,
                    raw_json TEXT NOT NULL,
                    normalized_json TEXT NOT NULL,
                    embedding_eligible INTEGER NOT NULL DEFAULT 1,
                    is_archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_dataset_meta_version ON dataset_metadata(version);
                CREATE INDEX IF NOT EXISTS idx_dataset_meta_active ON dataset_metadata(is_active);
                CREATE INDEX IF NOT EXISTS idx_dataset_rec_dataset ON dataset_records(dataset_id);
                CREATE INDEX IF NOT EXISTS idx_dataset_rec_category ON dataset_records(category);
                CREATE INDEX IF NOT EXISTS idx_dataset_rec_prod_ref ON dataset_records(product_reference);
                CREATE INDEX IF NOT EXISTS idx_dataset_rec_title ON dataset_records(title);

                CREATE TABLE IF NOT EXISTS product_relationships (
                    id TEXT PRIMARY KEY,
                    source_record_id TEXT NOT NULL,
                    source_category TEXT NOT NULL,
                    target_product_id TEXT NOT NULL,
                    match_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    match_criteria TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_prod_rel_target ON product_relationships(target_product_id);
                CREATE INDEX IF NOT EXISTS idx_prod_rel_source ON product_relationships(source_record_id);

                CREATE TABLE IF NOT EXISTS activation_jobs (
                    id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL REFERENCES catalogues(id) ON DELETE CASCADE,
                    version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    total_records INTEGER NOT NULL DEFAULT 0,
                    processed_records INTEGER NOT NULL DEFAULT 0,
                    embedded_records INTEGER NOT NULL DEFAULT 0,
                    indexed_records INTEGER NOT NULL DEFAULT 0,
                    failed_records INTEGER NOT NULL DEFAULT 0,
                    skipped_records INTEGER NOT NULL DEFAULT 0,
                    current_batch INTEGER NOT NULL DEFAULT 0,
                    total_batches INTEGER NOT NULL DEFAULT 0,
                    batch_size INTEGER NOT NULL DEFAULT 100,
                    error_message TEXT,
                    error_category TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_activation_jobs_dataset ON activation_jobs(dataset_id);
                CREATE INDEX IF NOT EXISTS idx_activation_jobs_status ON activation_jobs(status);
            """)

            # Deduplicate any identical versions from prior test runs before creating unique index
            dup_versions = conn.execute(
                "SELECT version, COUNT(*) as cnt FROM catalogues GROUP BY version HAVING cnt > 1"
            ).fetchall()
            for r in dup_versions:
                v = r["version"]
                keep = conn.execute(
                    "SELECT id FROM catalogues WHERE version = ? ORDER BY is_active DESC, created_at DESC LIMIT 1",
                    (v,)
                ).fetchone()
                if keep:
                    conn.execute("DELETE FROM catalogues WHERE version = ? AND id != ?", (v, keep["id"]))

            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_catalogues_version ON catalogues(version);")

            # Users table migration for is_demo column
            usr_cols = [c["name"] for c in conn.execute("PRAGMA table_info(users)").fetchall()]
            if "is_demo" not in usr_cols:
                conn.execute("ALTER TABLE users ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0;")

            # Feedback table migration for is_demo column
            fb_cols = [c["name"] for c in conn.execute("PRAGMA table_info(feedback)").fetchall()]
            if "is_demo" not in fb_cols:
                conn.execute("ALTER TABLE feedback ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0;")

            # Deduplicate test feedback duplicates that have identical message & customer_email
            dup_feedbacks = conn.execute(
                "SELECT customer_email, message, COUNT(*) as cnt FROM feedback GROUP BY customer_email, message HAVING cnt > 1"
            ).fetchall()
            for df in dup_feedbacks:
                c_email = df["customer_email"]
                msg = df["message"]
                keep_fb = conn.execute(
                    "SELECT id FROM feedback WHERE customer_email = ? AND message = ? ORDER BY status DESC, created_at DESC LIMIT 1",
                    (c_email, msg)
                ).fetchone()
                if keep_fb:
                    conn.execute(
                        "DELETE FROM feedback WHERE customer_email = ? AND message = ? AND id != ?",
                        (c_email, msg, keep_fb["id"])
                    )
                    if "Customer A" in msg or "box says 10 days" in msg:
                        conn.execute("UPDATE feedback SET is_demo = 1 WHERE id = ?", (keep_fb["id"],))


        self._seed_initial_data()

    def _seed_initial_data(self) -> None:
        """Seeds initial admin owner, demo customer, official catalogue, and policy if not already seeded."""
        now = _now_iso()
        with self.get_connection() as conn:
            # 1. Seed Owner User
            owner = conn.execute("SELECT id FROM users WHERE email = ?", (settings.INITIAL_OWNER_EMAIL,)).fetchone()
            if not owner:
                owner_id = str(uuid.uuid4())
                owner_hash = hash_password(settings.INITIAL_OWNER_PASSWORD)
                conn.execute(
                    "INSERT INTO users (id, email, full_name, hashed_password, role, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (owner_id, settings.INITIAL_OWNER_EMAIL, "TruthCart Store Owner", owner_hash, "OWNER", 0, now, now)
                )
                self.log_audit(
                    actor_id=owner_id,
                    actor_role="SYSTEM",
                    action="SYSTEM_INIT_USER",
                    target_id=owner_id,
                    target_type="USER",
                    details={"email": settings.INITIAL_OWNER_EMAIL, "role": "OWNER"},
                    conn=conn
                )
                SafeLogger.info(f"Initial owner provisioned: {settings.INITIAL_OWNER_EMAIL}")
            else:
                owner_id = owner["id"]

            # 2. Seed Demo Customer User
            cust = conn.execute("SELECT id FROM users WHERE email = ?", (settings.INITIAL_CUSTOMER_EMAIL,)).fetchone()
            if not cust:
                cust_id = str(uuid.uuid4())
                cust_hash = hash_password(settings.INITIAL_CUSTOMER_PASSWORD)
                conn.execute(
                    "INSERT INTO users (id, email, full_name, hashed_password, role, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (cust_id, settings.INITIAL_CUSTOMER_EMAIL, "Priya Sharma (Shopper)", cust_hash, "CUSTOMER", 1, now, now)
                )
                SafeLogger.info(f"Initial demo customer provisioned: {settings.INITIAL_CUSTOMER_EMAIL}")
            else:
                conn.execute("UPDATE users SET is_demo = 1 WHERE email = ?", (settings.INITIAL_CUSTOMER_EMAIL,))

            # 3. Seed Demo Owner User
            demo_owner_email = "demo-owner@truthcart.ai"
            demo_owner = conn.execute("SELECT id FROM users WHERE email = ?", (demo_owner_email,)).fetchone()
            if not demo_owner:
                demo_owner_id = str(uuid.uuid4())
                demo_owner_hash = hash_password(settings.INITIAL_OWNER_PASSWORD)
                conn.execute(
                    "INSERT INTO users (id, email, full_name, hashed_password, role, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (demo_owner_id, demo_owner_email, "TruthCart Store Owner (Demo)", demo_owner_hash, "OWNER", 1, now, now)
                )
                SafeLogger.info(f"Demo owner provisioned: {demo_owner_email}")

            # 3. Seed Official Catalogue if none exists
            cat_count = conn.execute("SELECT COUNT(*) as cnt FROM catalogues").fetchone()["cnt"]
            if cat_count == 0:
                self._seed_official_catalogue(conn, owner_id)

            # 4. Seed Official Policy if none exists
            pol_count = conn.execute("SELECT COUNT(*) as cnt FROM policy_documents").fetchone()["cnt"]
            if pol_count == 0:
                self._seed_official_policy(conn, owner_id)

    def _seed_official_catalogue(self, conn: sqlite3.Connection, owner_id: str) -> None:
        official_cat_path = settings.get_products_path() / "catalogue.json"
        if not official_cat_path.exists():
            SafeLogger.warning("Official catalogue.json not found during database seed.")
            return

        try:
            with open(official_cat_path, "r", encoding="utf-8") as f:
                records = json.load(f)

            now = _now_iso()
            cat_id = str(uuid.uuid4())
            cat_version = "v1.0.0"

            conn.execute(
                """INSERT INTO catalogues 
                   (id, version, name, filename, owner_id, record_count, valid_count, invalid_count, validation_report, status, is_active, created_at, activated_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cat_id,
                    cat_version,
                    "Official Hackathon Catalogue 2026",
                    "catalogue.json",
                    owner_id,
                    len(records),
                    len(records),
                    0,
                    json.dumps({"valid_records": len(records), "errors": []}),
                    "ACTIVE",
                    1,
                    now,
                    now
                )
            )

            for item in records:
                prod_db_id = str(uuid.uuid4())
                pid = str(item.get("product_id", "")).strip()
                title = str(item.get("title", "")).strip()
                desc = str(item.get("description", "")).strip()
                cat = str(item.get("category", "")).strip()
                price = float(item.get("price", 0.0))
                stock = str(item.get("stock_status", "In Stock")).strip()
                rating = float(item["rating"]) if item.get("rating") is not None else None
                attrs = json.dumps(item.get("attributes", {}))

                conn.execute(
                    """INSERT INTO products 
                       (id, catalogue_id, product_id, title, description, category, price, stock_status, rating, attributes, is_archived, created_at, updated_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (prod_db_id, cat_id, pid, title, desc, cat, price, stock, rating, attrs, 0, now, now)
                )

            SafeLogger.info(f"Database seeded with official catalogue {cat_version}: {len(records)} products.")
        except Exception as e:
            SafeLogger.error(f"Error seeding official catalogue: {str(e)}")

    def _seed_official_policy(self, conn: sqlite3.Connection, owner_id: str) -> None:
        policy_path = settings.get_policies_path() / "policy.txt"
        if not policy_path.exists():
            SafeLogger.warning("Official policy.txt not found during database seed.")
            return

        try:
            with open(policy_path, "r", encoding="utf-8") as f:
                content = f.read()

            now = _now_iso()
            pol_id = str(uuid.uuid4())
            pol_version = "v1.0.0"

            # Parse sections
            from app.ingestion.policy_loader import PolicyLoader
            temp_loader = PolicyLoader()
            temp_loader.parse_text(content, is_official=True, is_synthetic=False, source_name="policy.txt")
            sections_dict = {sec_id: sec.to_dict() for sec_id, sec in temp_loader.sections.items()}

            conn.execute(
                """INSERT INTO policy_documents 
                   (id, version, title, content, sections, is_active, created_at, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pol_id,
                    pol_version,
                    "TruthCart Official Store Policies 2026",
                    content,
                    json.dumps(sections_dict),
                    1,
                    now,
                    now
                )
            )
            SafeLogger.info(f"Database seeded with official policy {pol_version} ({len(sections_dict)} sections).")
        except Exception as e:
            SafeLogger.error(f"Error seeding official policy: {str(e)}")

    # ---------------- USER METHODS ----------------
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def create_user(self, email: str, full_name: str, password: str, role: str = "CUSTOMER", is_demo: int = 0) -> Dict[str, Any]:
        """Creates user. Role is strictly enforced by caller."""
        if role not in ("CUSTOMER", "OWNER"):
            raise ValueError(f"Invalid role: {role}")
        now = _now_iso()
        user_id = str(uuid.uuid4())
        hashed = hash_password(password)

        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO users (id, email, full_name, hashed_password, role, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, email.strip().lower(), full_name.strip(), hashed, role, is_demo, now, now)
            )

        self.log_audit(
            actor_id=user_id,
            actor_role=role,
            action="USER_SIGNUP",
            target_id=user_id,
            target_type="USER",
            details={"email": email, "role": role}
        )

        return self.get_user_by_id(user_id) # type: ignore

    def get_demo_user(self, role: str) -> Dict[str, Any]:
        """Retrieves or provisions isolated demo user for the specified role."""
        now = _now_iso()
        with self.get_connection() as conn:
            if role == "OWNER":
                demo_email = "demo-owner@truthcart.ai"
                row = conn.execute("SELECT * FROM users WHERE email = ?", (demo_email,)).fetchone()
                if not row:
                    user_id = str(uuid.uuid4())
                    pwd_hash = hash_password(settings.INITIAL_OWNER_PASSWORD)
                    conn.execute(
                        "INSERT INTO users (id, email, full_name, hashed_password, role, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (user_id, demo_email, "TruthCart Store Owner (Demo)", pwd_hash, "OWNER", 1, now, now)
                    )
                    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                else:
                    conn.execute("UPDATE users SET is_demo = 1 WHERE id = ?", (row["id"],))
                    row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
                return dict(row)
            else:
                demo_email = settings.INITIAL_CUSTOMER_EMAIL
                row = conn.execute("SELECT * FROM users WHERE email = ?", (demo_email,)).fetchone()
                if not row:
                    user_id = str(uuid.uuid4())
                    pwd_hash = hash_password(settings.INITIAL_CUSTOMER_PASSWORD)
                    conn.execute(
                        "INSERT INTO users (id, email, full_name, hashed_password, role, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (user_id, demo_email, "Priya Sharma (Demo Shopper)", pwd_hash, "CUSTOMER", 1, now, now)
                    )
                    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                else:
                    conn.execute("UPDATE users SET is_demo = 1 WHERE id = ?", (row["id"],))
                    row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
                return dict(row)

    # ---------------- CATALOGUE METHODS ----------------
    def get_active_catalogue(self) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT c.*, 
                       COALESCE(m.category, 'PRODUCT_CATALOGUE') as category,
                       COALESCE(m.embedding_status, 'INDEXED') as embedding_status,
                       COALESCE(m.embedding_model, 'local-sparse-tfidf-v1') as embedding_model
                FROM catalogues c
                LEFT JOIN dataset_metadata m ON c.id = m.id
                WHERE c.is_active = 1 LIMIT 1
            """).fetchone()
            return dict(row) if row else None

    def get_all_catalogues(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT c.*, 
                       COALESCE(m.category, 'PRODUCT_CATALOGUE') as category,
                       COALESCE(m.embedding_status, 'INDEXED') as embedding_status,
                       COALESCE(m.embedding_model, 'local-sparse-tfidf-v1') as embedding_model,
                       j.id as active_job_id,
                       j.status as job_status,
                       j.stage as job_stage,
                       j.processed_records,
                       j.total_records,
                       j.error_message as job_error
                FROM catalogues c
                LEFT JOIN dataset_metadata m ON c.id = m.id
                LEFT JOIN (
                    SELECT aj1.*
                    FROM activation_jobs aj1
                    INNER JOIN (
                        SELECT dataset_id, MAX(created_at) as max_created
                        FROM activation_jobs
                        GROUP BY dataset_id
                    ) aj2 ON aj1.dataset_id = aj2.dataset_id AND aj1.created_at = aj2.max_created
                ) j ON c.id = j.dataset_id
                ORDER BY c.created_at DESC
            """).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                tot = d.get("total_records") or d.get("valid_count") or 0
                proc = d.get("processed_records") or 0
                d["progress_percent"] = round((proc / tot) * 100.0, 1) if tot > 0 else (100.0 if d.get("is_active") else 0.0)
                results.append(d)
            return results

    def get_catalogue_by_id(self, cat_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT c.*, 
                       COALESCE(m.category, 'PRODUCT_CATALOGUE') as category,
                       COALESCE(m.embedding_status, 'INDEXED') as embedding_status,
                       COALESCE(m.embedding_model, 'local-sparse-tfidf-v1') as embedding_model
                FROM catalogues c
                LEFT JOIN dataset_metadata m ON c.id = m.id
                WHERE c.id = ?
            """, (cat_id,)).fetchone()
            if not row and cat_id:
                row = conn.execute("""
                    SELECT c.*, 
                           COALESCE(m.category, 'PRODUCT_CATALOGUE') as category,
                           COALESCE(m.embedding_status, 'INDEXED') as embedding_status,
                           COALESCE(m.embedding_model, 'local-sparse-tfidf-v1') as embedding_model
                    FROM catalogues c
                    LEFT JOIN dataset_metadata m ON c.id = m.id
                    WHERE LOWER(c.version) = LOWER(?) LIMIT 1
                """, (str(cat_id).strip(),)).fetchone()
            return dict(row) if row else None

    def get_catalogue_by_version(self, version: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT c.*, 
                       COALESCE(m.category, 'PRODUCT_CATALOGUE') as category,
                       COALESCE(m.embedding_status, 'INDEXED') as embedding_status,
                       COALESCE(m.embedding_model, 'local-sparse-tfidf-v1') as embedding_model
                FROM catalogues c
                LEFT JOIN dataset_metadata m ON c.id = m.id
                WHERE LOWER(c.version) = LOWER(?) LIMIT 1
            """, (version.strip(),)).fetchone()
            return dict(row) if row else None

    def create_catalogue(
        self,
        name: str,
        filename: str,
        version: str,
        owner_id: str,
        records: List[Dict[str, Any]],
        validation_report: Dict[str, Any],
        valid_count: int,
        invalid_count: int,
        status: str = "READY_FOR_ACTIVATION",
        category: str = "PRODUCT_CATALOGUE",
        schema_mapping: Optional[Dict[str, Any]] = None,
        embedding_status: str = "INDEXED"
    ) -> Dict[str, Any]:
        """Persists imported catalogue and its products in database."""
        v_clean = version.strip()
        cat_id = str(uuid.uuid4())
        now = _now_iso()

        with self.get_connection() as conn:
            existing = conn.execute("SELECT id, status FROM catalogues WHERE LOWER(version) = LOWER(?)", (v_clean,)).fetchone()
            if existing:
                raise ValueError(f"Catalogue version '{v_clean}' already exists in database (status: {existing['status']}).")

            conn.execute(
                """INSERT INTO catalogues 
                   (id, version, name, filename, owner_id, record_count, valid_count, invalid_count, validation_report, status, is_active, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cat_id,
                    v_clean,
                    name,
                    filename,
                    owner_id,
                    len(records),
                    valid_count,
                    invalid_count,
                    json.dumps(validation_report),
                    status,
                    0,
                    now
                )
            )

            # Persist dataset_metadata
            conn.execute(
                """INSERT INTO dataset_metadata
                   (id, version, name, filename, category, owner_id, record_count, valid_count, invalid_count, schema_mapping, validation_report, embedding_status, embedding_model, status, is_active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'local-sparse-tfidf-v1', ?, 0, ?)""",
                (
                    cat_id,
                    v_clean,
                    name,
                    filename,
                    category,
                    owner_id,
                    len(records),
                    valid_count,
                    invalid_count,
                    json.dumps(schema_mapping or {}),
                    json.dumps(validation_report),
                    embedding_status,
                    status,
                    now
                )
            )

            # Insert valid products
            for item in records:
                prod_db_id = str(uuid.uuid4())
                if category in ("PRODUCT_CATALOGUE", "MARKETPLACE_LISTINGS", "PRODUCT_SPECIFICATIONS", "GENERIC_DATASET"):
                    pid = str(item.get("product_id") or item.get("record_id") or item.get("listing_id") or f"TC-GEN-{uuid.uuid4().hex[:6]}").strip()
                else:
                    pid = str(item.get("record_id") or item.get("review_id") or item.get("listing_id") or f"{item.get('product_id', 'REC')}-{uuid.uuid4().hex[:6]}").strip()
                title = str(item.get("title", f"Item {pid}")).strip()

                # Build comprehensive attributes dictionary preserving all domain metadata
                attrs_dict = dict(item.get("attributes", {})) if isinstance(item.get("attributes"), dict) else {}
                for meta_k in ("brand", "seller_name", "marketplace", "manufacturer", "warranty", "return_window", "color", "material", "shipping", "weight_kg"):
                    if item.get(meta_k) and meta_k not in attrs_dict:
                        attrs_dict[meta_k] = item[meta_k]
                attrs = json.dumps(attrs_dict)

                desc = str(item.get("description", "")).strip()
                if not desc and attrs_dict:
                    desc = str(attrs_dict.get("details") or attrs_dict.get("specifications") or attrs_dict.get("technical_details") or attrs_dict.get("summary") or "").strip()

                raw_cat = item.get("category")
                if raw_cat and str(raw_cat).strip() not in ("General", category, "MARKETPLACE_LISTINGS", "GENERIC_DATASET"):
                    cat = str(raw_cat).strip()
                elif attrs_dict.get("subcategory"):
                    cat = str(attrs_dict["subcategory"]).strip()
                elif attrs_dict.get("category"):
                    cat = str(attrs_dict["category"]).strip()
                else:
                    cat = str(item.get("category", "General")).strip()

                raw_p = item.get("price")
                try:
                    price = float(raw_p) if raw_p is not None else 0.0
                except (ValueError, TypeError):
                    price = 0.0

                from app.ingestion.data_validator import DataValidator
                raw_stock = item.get("stock_status") or attrs_dict.get("inventory_status") or attrs_dict.get("stock")
                stock = DataValidator.normalize_stock_status(raw_stock)

                raw_r = item.get("rating") or attrs_dict.get("rating") or attrs_dict.get("review_rating")
                try:
                    rating = float(raw_r) if raw_r is not None else None
                except (ValueError, TypeError):
                    rating = None

                conn.execute(
                    """INSERT INTO products 
                       (id, catalogue_id, product_id, title, description, category, price, stock_status, rating, attributes, is_archived, created_at, updated_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (prod_db_id, cat_id, pid, title, desc, cat, price, stock, rating, attrs, 0, now, now)
                )

                # Multi-domain dataset_records entry
                raw_json = json.dumps(item.get("raw_record") or item)
                norm_json = json.dumps(item)
                conn.execute(
                    """INSERT INTO dataset_records
                       (id, dataset_id, category, record_id, product_reference, title, content_text, numeric_value, currency, rating, date_observed, raw_json, normalized_json, embedding_eligible, is_archived, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                    (
                        str(uuid.uuid4()),
                        cat_id,
                        category,
                        pid,
                        str(item.get("product_id") or pid),
                        title,
                        desc or str(item.get("review_text") or item.get("policy_content") or ""),
                        price,
                        str(item.get("currency", "INR")),
                        rating,
                        str(item.get("observation_date") or item.get("review_date") or item.get("effective_date") or ""),
                        raw_json,
                        norm_json,
                        1,
                        now,
                        now
                    )
                )

            # Resolve and record cross-dataset relationships only for supplementary domains (reviews, competitor pricing)
            if category in ("CUSTOMER_REVIEWS", "COMPETITOR_PRICING") and records:
                try:
                    from app.retrieval.identity_resolver import identity_resolver, RelationshipType
                    existing_prods = conn.execute("SELECT product_id, title, category, price, attributes FROM products WHERE is_archived = 0 LIMIT 500").fetchall()
                    cand_products = []
                    for ep in existing_prods:
                        ep_dict = dict(ep)
                        if ep_dict.get("attributes") and isinstance(ep_dict["attributes"], str):
                            try:
                                ep_dict["attributes"] = json.loads(ep_dict["attributes"])
                            except Exception:
                                ep_dict["attributes"] = {}
                        cand_products.append(ep_dict)

                    if cand_products:
                        for item in records:
                            rel_type, target_pid, conf, crit = identity_resolver.resolve_relationship(item, cand_products)
                            if target_pid and rel_type != RelationshipType.UNLINKED:
                                rel_id = str(uuid.uuid4())
                                rec_id = str(item.get("product_id") or item.get("record_id") or item.get("review_id") or item.get("listing_id") or uuid.uuid4().hex[:8])
                                conn.execute(
                                    """INSERT INTO product_relationships
                                       (id, source_record_id, source_category, target_product_id, match_type, confidence, match_criteria, created_at)
                                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                                    (rel_id, rec_id, category, target_pid, rel_type.value, conf, crit, now)
                                )
                except Exception as e:
                    SafeLogger.warning(f"Could not persist product relationships: {str(e)}")

        self.log_audit(
            actor_id=owner_id,
            actor_role="OWNER",
            action="CATALOGUE_UPLOADED",
            target_id=cat_id,
            target_type="CATALOGUE",
            details={
                "name": name,
                "version": version,
                "filename": filename,
                "category": category,
                "valid_count": valid_count,
                "invalid_count": invalid_count
            }
        )

        return self.get_catalogue_by_id(cat_id) # type: ignore

    def activate_catalogue(self, cat_id: str, actor_id: str) -> Dict[str, Any]:
        """Atomically deactivates existing active catalogue and activates target catalogue."""
        now = _now_iso()
        with self.get_connection() as conn:
            # Check target exists by id or version
            target = conn.execute("SELECT * FROM catalogues WHERE id = ?", (cat_id,)).fetchone()
            if not target and cat_id:
                target = conn.execute("SELECT * FROM catalogues WHERE LOWER(version) = LOWER(?) LIMIT 1", (str(cat_id).strip(),)).fetchone()
            if not target:
                raise ValueError(f"Catalogue with ID {cat_id} not found.")

            target_id = target["id"]
            target_meta = conn.execute("SELECT category FROM dataset_metadata WHERE id = ?", (target_id,)).fetchone()
            target_category = target_meta["category"] if target_meta else "PRODUCT_CATALOGUE"

            is_product_cat = target_category in ("PRODUCT_CATALOGUE", "MARKETPLACE_LISTINGS", "PRODUCT_SPECIFICATIONS", "GENERIC_DATASET")

            # Deactivate prior active catalogue if target is a product catalogue
            if is_product_cat:
                conn.execute("UPDATE catalogues SET is_active = 0, status = CASE WHEN status = 'ACTIVE' THEN 'ARCHIVED' ELSE status END WHERE is_active = 1")
                conn.execute("UPDATE catalogues SET is_active = 1, status = 'ACTIVE', activated_at = ? WHERE id = ?", (now, target_id))
            else:
                conn.execute("UPDATE catalogues SET status = 'ACTIVE', activated_at = ? WHERE id = ?", (now, target_id))

            # Deactivate prior dataset metadata of the SAME category to preserve cross-domain datasets
            conn.execute("UPDATE dataset_metadata SET is_active = 0, status = CASE WHEN status = 'ACTIVE' THEN 'ARCHIVED' ELSE status END WHERE is_active = 1 AND category = ?", (target_category,))
            conn.execute("UPDATE dataset_metadata SET is_active = 1, status = 'ACTIVE', activated_at = ? WHERE id = ?", (now, target_id))

        self.log_audit(
            actor_id=actor_id,
            actor_role="OWNER",
            action="CATALOGUE_ACTIVATED",
            target_id=target_id,
            target_type="CATALOGUE",
            details={"version": target["version"], "name": target["name"], "category": target_category}
        )

        return self.get_catalogue_by_id(target_id) # type: ignore

    def update_dataset_embedding_status(self, dataset_id: str, embedding_status: str, error_details: Optional[str] = None) -> None:
        """Updates embedding status and error details for a dataset."""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE dataset_metadata SET embedding_status = ? WHERE id = ?",
                (embedding_status, dataset_id)
            )

    # ---------------- ACTIVATION JOBS METHODS ----------------
    def create_activation_job(
        self,
        dataset_id: str,
        version: str,
        total_records: int,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """Creates a new tracked activation job record."""
        job_id = str(uuid.uuid4())
        now = _now_iso()
        total_batches = max(1, math.ceil(total_records / max(1, batch_size)))

        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO activation_jobs 
                   (id, dataset_id, version, status, stage, total_records, processed_records, embedded_records, indexed_records, failed_records, skipped_records, current_batch, total_batches, batch_size, retry_count, created_at, updated_at)
                   VALUES (?, ?, ?, 'ACTIVATING', 'VALIDATING', ?, 0, 0, 0, 0, 0, 0, ?, ?, 0, ?, ?)""",
                (job_id, dataset_id, version, total_records, total_batches, batch_size, now, now)
            )
        return self.get_activation_job(job_id) # type: ignore

    def get_activation_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves activation job by ID with computed progress metrics."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM activation_jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            tot = d.get("total_records", 0)
            proc = d.get("processed_records", 0)
            d["progress_percent"] = round((proc / tot) * 100.0, 1) if tot > 0 else (100.0 if d.get("status") == "ACTIVE" else 0.0)
            d["is_active"] = (d.get("status") == "ACTIVE")
            return d

    def get_latest_activation_job_for_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the most recent activation job for a dataset."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM activation_jobs WHERE dataset_id = ? ORDER BY created_at DESC LIMIT 1",
                (dataset_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            tot = d.get("total_records", 0)
            proc = d.get("processed_records", 0)
            d["progress_percent"] = round((proc / tot) * 100.0, 1) if tot > 0 else (100.0 if d.get("status") == "ACTIVE" else 0.0)
            d["is_active"] = (d.get("status") == "ACTIVE")
            return d

    def update_activation_job_progress(
        self,
        job_id: str,
        processed_records: int,
        embedded_records: int,
        current_batch: int,
        stage: str = "BATCHING_EMBEDDINGS",
        status: str = "ACTIVATING",
        failed_records: int = 0
    ) -> None:
        """Updates real-time batch processing and embedding progress."""
        now = _now_iso()
        with self.get_connection() as conn:
            conn.execute(
                """UPDATE activation_jobs 
                   SET processed_records = ?, embedded_records = ?, current_batch = ?, stage = ?, status = ?, failed_records = ?, updated_at = ?
                   WHERE id = ?""",
                (processed_records, embedded_records, current_batch, stage, status, failed_records, now, job_id)
            )

    def complete_activation_job(
        self,
        job_id: str,
        status: str = "ACTIVE",
        stage: str = "COMPLETED",
        indexed_records: Optional[int] = None,
        error_message: Optional[str] = None,
        error_category: Optional[str] = None
    ) -> None:
        """Marks activation job as finished (either ACTIVE or FAILED)."""
        now = _now_iso()
        with self.get_connection() as conn:
            job = conn.execute("SELECT total_records FROM activation_jobs WHERE id = ?", (job_id,)).fetchone()
            tot = job["total_records"] if job else 0
            idx_recs = indexed_records if indexed_records is not None else (tot if status == "ACTIVE" else 0)
            conn.execute(
                """UPDATE activation_jobs 
                   SET status = ?, stage = ?, indexed_records = ?, error_message = ?, error_category = ?, updated_at = ?, completed_at = ?
                   WHERE id = ?""",
                (status, stage, idx_recs, error_message, error_category, now, now if status in ("ACTIVE", "FAILED") else None, job_id)
            )

    def get_dataset_records_paginated(self, catalogue_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieves paginated records for a catalogue version from the products table."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM products WHERE catalogue_id = ? ORDER BY id LIMIT ? OFFSET ?",
                (catalogue_id, limit, offset)
            ).fetchall()
            result = []
            for r in rows:
                p = dict(r)
                if p.get("attributes") and isinstance(p["attributes"], str):
                    try:
                        p["attributes"] = json.loads(p["attributes"])
                    except Exception:
                        p["attributes"] = {}
                result.append(p)
            return result

    # ---------------- PRODUCT METHODS ----------------
    def _build_active_products_filter(
        self,
        cat_id: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        in_stock_only: bool = False,
        search_query: Optional[str] = None
    ) -> Tuple[str, List[Any]]:
        where_clauses = ["catalogue_id = ?", "is_archived = 0"]
        params: List[Any] = [cat_id]

        if category and str(category).strip():
            clean_cat = str(category).strip().lower()
            if clean_cat in ("clothing", "apparel"):
                where_clauses.append("(LOWER(category) LIKE '%clothing%' OR LOWER(category) LIKE '%apparel%')")
            else:
                where_clauses.append("(LOWER(category) = ? OR LOWER(category) LIKE ? || ' >> %' OR LOWER(category) LIKE '% >> ' || ? || ' >> %' OR LOWER(category) LIKE '% >> ' || ? OR LOWER(category) LIKE '%' || ? || '%')")
                params.extend([clean_cat, clean_cat, clean_cat, clean_cat, clean_cat])

        if min_price is not None:
            try:
                where_clauses.append("price >= ?")
                params.append(float(min_price))
            except (ValueError, TypeError):
                pass

        if max_price is not None:
            try:
                where_clauses.append("price <= ?")
                params.append(float(max_price))
            except (ValueError, TypeError):
                pass

        if in_stock_only:
            where_clauses.append("(LOWER(stock_status) = 'in stock' OR LOWER(stock_status) = 'instock' OR LOWER(stock_status) LIKE 'in%stock%' OR stock_status = '1')")

        if search_query and str(search_query).strip():
            raw_q = str(search_query).strip()
            raw_lower = raw_q.lower()
            clean_alnum = re.sub(r'[^a-zA-Z0-9]', '', raw_lower)

            id_parts = [
                "LOWER(product_id) = ?",
                "LOWER(product_id) LIKE ?",
                "LOWER(attributes) LIKE ?"
            ]
            id_params = [raw_lower, f"%{raw_lower}%", f"%{raw_lower}%"]
            if clean_alnum and clean_alnum != raw_lower:
                id_parts.append("REPLACE(LOWER(product_id), '-', '') LIKE ?")
                id_params.append(f"%{clean_alnum}%")

            id_clause = "(" + " OR ".join(id_parts) + ")"

            search_stop_words = {"the", "and", "for", "with", "in", "on", "at", "to", "a", "an", "of", "is", "by"}
            raw_tokens = [t.lower() for t in re.findall(r'\b[a-zA-Z0-9]+\b', raw_q)]
            tokens = [t for t in raw_tokens if t not in search_stop_words]
            if not tokens and raw_tokens:
                tokens = raw_tokens

            if tokens:
                token_clauses = []
                token_params = []
                for t in tokens:
                    t_pat = f"%{t}%"
                    token_clauses.append("(LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(product_id) LIKE ? OR LOWER(category) LIKE ? OR LOWER(attributes) LIKE ?)")
                    token_params.extend([t_pat, t_pat, t_pat, t_pat, t_pat])
                combined_clause = f"({id_clause} OR ({' AND '.join(token_clauses)}))"
                where_clauses.append(combined_clause)
                params.extend(id_params)
                params.extend(token_params)
            else:
                where_clauses.append(id_clause)
                params.extend(id_params)

        where_sql = " WHERE " + " AND ".join(where_clauses)
        return where_sql, params

    def count_active_products(
        self,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        in_stock_only: bool = False,
        search_query: Optional[str] = None
    ) -> int:
        """Fast O(1) count of active catalogue products matching filters."""
        with self.get_connection() as conn:
            active_cat = conn.execute("SELECT id FROM catalogues WHERE is_active = 1 ORDER BY activated_at DESC, created_at DESC LIMIT 1").fetchone()
            if not active_cat:
                return 0

            where_sql, params = self._build_active_products_filter(
                cat_id=active_cat["id"],
                category=category,
                min_price=min_price,
                max_price=max_price,
                in_stock_only=in_stock_only,
                search_query=search_query
            )
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM products {where_sql}", params).fetchone()
            return int(row["cnt"]) if row else 0

    def get_active_products(
        self,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        in_stock_only: bool = False,
        search_query: Optional[str] = None,
        sort_by: Optional[str] = "title_asc",
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Retrieves products from the currently active catalogue with deterministic sorting and stable pagination."""
        with self.get_connection() as conn:
            active_cat = conn.execute("SELECT id FROM catalogues WHERE is_active = 1 ORDER BY activated_at DESC, created_at DESC LIMIT 1").fetchone()
            if not active_cat:
                return []

            where_sql, params = self._build_active_products_filter(
                cat_id=active_cat["id"],
                category=category,
                min_price=min_price,
                max_price=max_price,
                in_stock_only=in_stock_only,
                search_query=search_query
            )

            query = f"SELECT * FROM products {where_sql}"
            order_params: List[Any] = []

            # Deterministic ordering with unique tie-breaker (product_id ASC, id ASC)
            if sort_by == "price_asc":
                query += " ORDER BY price ASC, title ASC, product_id ASC, id ASC"
            elif sort_by == "price_desc":
                query += " ORDER BY price DESC, title ASC, product_id ASC, id ASC"
            elif sort_by == "rating_desc":
                query += " ORDER BY CASE WHEN rating IS NULL THEN 1 ELSE 0 END, rating DESC, title ASC, product_id ASC, id ASC"
            elif sort_by == "title_desc":
                query += " ORDER BY title DESC, product_id ASC, id ASC"
            elif sort_by == "newest":
                query += " ORDER BY created_at DESC, product_id ASC, id ASC"
            else:
                if search_query and str(search_query).strip():
                    raw_lower = str(search_query).strip().lower()
                    query += """ ORDER BY 
                        CASE 
                            WHEN LOWER(product_id) = ? THEN 0
                            WHEN LOWER(title) = ? THEN 1
                            WHEN LOWER(product_id) LIKE ? THEN 2
                            WHEN LOWER(title) LIKE ? THEN 3
                            ELSE 4
                        END ASC, title ASC, product_id ASC, id ASC"""
                    order_params.extend([raw_lower, raw_lower, f"%{raw_lower}%", f"%{raw_lower}%"])
                else:
                    query += " ORDER BY title ASC, product_id ASC, id ASC"

            params.extend(order_params)

            # Safe pagination
            if limit is not None and limit > 0:
                query += " LIMIT ?"
                params.append(limit)
                if offset is not None and offset > 0:
                    query += " OFFSET ?"
                    params.append(offset)

            rows = conn.execute(query, params).fetchall()

            result = []
            for r in rows:
                p = dict(r)
                if p.get("attributes") and isinstance(p["attributes"], str):
                    try:
                        p["attributes"] = json.loads(p["attributes"])
                    except Exception:
                        p["attributes"] = {}
                result.append(p)
            return result

    def get_catalogue_diagnostics(self) -> Dict[str, Any]:
        """Provides full health and parity diagnostics between DB, in-memory loader, and vector index."""
        with self.get_connection() as conn:
            active_cat = conn.execute("""
                SELECT c.*, 
                       COALESCE(m.category, 'PRODUCT_CATALOGUE') as category,
                       COALESCE(m.embedding_status, 'INDEXED') as embedding_status
                FROM catalogues c
                LEFT JOIN dataset_metadata m ON c.id = m.id
                WHERE c.is_active = 1
                ORDER BY c.activated_at DESC, c.created_at DESC
                LIMIT 1
            """).fetchone()

            if not active_cat:
                return {
                    "has_active_catalogue": False,
                    "status": "NO_ACTIVE_CATALOGUE",
                    "active_catalogue": None,
                    "total_db_products": 0,
                    "total_eligible_products": 0,
                    "total_archived_products": 0,
                    "total_loader_products": 0,
                    "total_indexed_documents": 0,
                    "is_indexed": False,
                    "parity_status": "EMPTY"
                }

            cat_id = active_cat["id"]
            total_db = conn.execute("SELECT COUNT(*) as cnt FROM products WHERE catalogue_id = ?", (cat_id,)).fetchone()["cnt"]
            total_eligible = conn.execute("SELECT COUNT(*) as cnt FROM products WHERE catalogue_id = ? AND is_archived = 0", (cat_id,)).fetchone()["cnt"]
            total_archived = conn.execute("SELECT COUNT(*) as cnt FROM products WHERE catalogue_id = ? AND is_archived = 1", (cat_id,)).fetchone()["cnt"]

            sample_first = conn.execute("SELECT product_id, title, price, category FROM products WHERE catalogue_id = ? AND is_archived = 0 ORDER BY product_id ASC LIMIT 1", (cat_id,)).fetchone()
            sample_last = conn.execute("SELECT product_id, title, price, category FROM products WHERE catalogue_id = ? AND is_archived = 0 ORDER BY product_id DESC LIMIT 1", (cat_id,)).fetchone()

            from app.ingestion.catalogue_loader import catalogue_loader
            from app.retrieval.semantic_search import local_vector_index

            loader_count = len(catalogue_loader.products)
            indexed_count = len(local_vector_index.doc_ids) if local_vector_index.is_indexed else 0

            is_healthy = (total_eligible > 0 and loader_count == total_eligible)

            return {
                "has_active_catalogue": True,
                "status": "HEALTHY" if is_healthy else "NEEDS_SYNC",
                "active_catalogue": {
                    "id": cat_id,
                    "name": active_cat["name"],
                    "version": active_cat["version"],
                    "category": active_cat["category"],
                    "filename": active_cat["filename"],
                    "activated_at": active_cat["activated_at"]
                },
                "total_db_products": total_db,
                "total_eligible_products": total_eligible,
                "total_archived_products": total_archived,
                "total_loader_products": loader_count,
                "total_indexed_documents": indexed_count,
                "is_indexed": local_vector_index.is_indexed,
                "missing_from_loader_count": max(0, total_eligible - loader_count),
                "sample_first": dict(sample_first) if sample_first else None,
                "sample_last": dict(sample_last) if sample_last else None
            }

    # ---------------- MULTI-DOMAIN DATASET RECORDS ----------------
    def get_active_dataset_records(
        self,
        category: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieves multi-domain dataset records (reviews, competitor prices, specs, etc.) from active datasets."""
        with self.get_connection() as conn:
            active_meta = conn.execute("SELECT id FROM dataset_metadata WHERE is_active = 1").fetchall()
            if not active_meta:
                return []
            dataset_ids = [m["id"] for m in active_meta]
            placeholders = ",".join(["?"] * len(dataset_ids))
            query = f"SELECT * FROM dataset_records WHERE dataset_id IN ({placeholders}) AND is_archived = 0"
            params: List[Any] = list(dataset_ids)

            if category:
                query += " AND category = ?"
                params.append(category)

            if search_query:
                q = f"%{search_query.strip().lower()}%"
                query += " AND (LOWER(title) LIKE ? OR LOWER(content_text) LIKE ? OR LOWER(product_reference) LIKE ? OR LOWER(normalized_json) LIKE ?)"
                params.extend([q, q, q, q])

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                rec = dict(r)
                if rec.get("normalized_json"):
                    try:
                        rec["data"] = json.loads(rec["normalized_json"])
                    except Exception:
                        rec["data"] = {}
                results.append(rec)
            return results

    def get_active_categories(self) -> List[str]:
        """Returns all distinct non-empty categories from the currently active catalogue."""
        with self.get_connection() as conn:
            active_cat = conn.execute("SELECT id FROM catalogues WHERE is_active = 1 LIMIT 1").fetchone()
            if not active_cat:
                return []
            rows = conn.execute(
                "SELECT DISTINCT category FROM products WHERE catalogue_id = ? AND is_archived = 0 AND category IS NOT NULL AND category != '' ORDER BY category ASC",
                (active_cat["id"],)
            ).fetchall()
            return [r["category"] for r in rows if r["category"]]

    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            active_cat = conn.execute("SELECT id FROM catalogues WHERE is_active = 1 LIMIT 1").fetchone()
            pid_clean = product_id.strip()
            if not active_cat:
                # Fallback to any active catalogue match (case-insensitive)
                row = conn.execute(
                    "SELECT * FROM products WHERE (product_id = ? OR UPPER(product_id) = UPPER(?)) AND is_archived = 0 LIMIT 1",
                    (pid_clean, pid_clean)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM products WHERE catalogue_id = ? AND (product_id = ? OR UPPER(product_id) = UPPER(?)) AND is_archived = 0 LIMIT 1",
                    (active_cat["id"], pid_clean, pid_clean)
                ).fetchone()

            if not row:
                return None
            p = dict(row)
            if p.get("attributes") and isinstance(p["attributes"], str):
                try:
                    p["attributes"] = json.loads(p["attributes"])
                except Exception:
                    p["attributes"] = {}
            return p

    def create_single_product(self, product_data: Dict[str, Any], actor_id: str) -> Dict[str, Any]:
        """Creates a single product entry in the active catalogue for the store owner."""
        now = _now_iso()
        with self.get_connection() as conn:
            active_cat = conn.execute("SELECT id FROM catalogues WHERE is_active = 1 LIMIT 1").fetchone()
            if not active_cat:
                raise ValueError("No active catalogue configured to add product to.")
            cat_id = active_cat["id"]
            prod_db_id = str(uuid.uuid4())
            pid = str(product_data.get("product_id", "")).strip()
            title = str(product_data.get("title", "")).strip()
            desc = str(product_data.get("description", "")).strip()
            cat = str(product_data.get("category", "General")).strip()
            price = float(product_data.get("price", 0.0))
            stock = str(product_data.get("stock_status", "In Stock")).strip()
            rating = float(product_data.get("rating", 4.5))
            attrs = json.dumps(product_data.get("attributes", {}))
            conn.execute(
                """INSERT INTO products 
                   (id, catalogue_id, product_id, title, description, category, price, stock_status, rating, attributes, is_archived, created_at, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                (prod_db_id, cat_id, pid, title, desc, cat, price, stock, rating, attrs, now, now)
            )
            conn.execute(
                "UPDATE catalogues SET record_count = record_count + 1, valid_count = valid_count + 1 WHERE id = ?",
                (cat_id,)
            )

        self.log_audit(
            actor_id=actor_id,
            actor_role="OWNER",
            action="PRODUCT_CREATED",
            target_id=pid,
            target_type="PRODUCT",
            details={"title": title, "category": cat, "price": price}
        )
        return self.get_product_by_id(pid)

    def update_product(self, product_id: str, updates: Dict[str, Any], actor_id: str) -> Dict[str, Any]:
        """Verified update on official product by store owner."""
        now = _now_iso()
        with self.get_connection() as conn:
            active_cat = conn.execute("SELECT id FROM catalogues WHERE is_active = 1 LIMIT 1").fetchone()
            if not active_cat:
                raise ValueError("No active catalogue configured to update product in.")

            existing = conn.execute(
                "SELECT * FROM products WHERE catalogue_id = ? AND product_id = ? LIMIT 1",
                (active_cat["id"], product_id.strip())
            ).fetchone()

            if not existing:
                raise ValueError(f"Product {product_id} not found in active catalogue.")

            before_values = dict(existing)
            field_updates = []
            params = []

            for field in ("title", "description", "category", "price", "stock_status", "rating"):
                if field in updates and updates[field] is not None:
                    field_updates.append(f"{field} = ?")
                    params.append(updates[field])

            if "attributes" in updates and isinstance(updates["attributes"], dict):
                field_updates.append("attributes = ?")
                params.append(json.dumps(updates["attributes"]))

            if not field_updates:
                return self.get_product_by_id(product_id) # type: ignore

            field_updates.append("updated_at = ?")
            params.append(now)
            params.extend([active_cat["id"], product_id.strip()])

            query = f"UPDATE products SET {', '.join(field_updates)} WHERE catalogue_id = ? AND product_id = ?"
            conn.execute(query, params)

        self.log_audit(
            actor_id=actor_id,
            actor_role="OWNER",
            action="PRODUCT_UPDATED",
            target_id=product_id,
            target_type="PRODUCT",
            details={
                "before": {k: before_values.get(k) for k in updates.keys()},
                "after": updates
            }
        )

        return self.get_product_by_id(product_id) # type: ignore

    def archive_product(self, product_id: str, actor_id: str) -> bool:
        """Deactivates/archives product in active catalogue."""
        now = _now_iso()
        with self.get_connection() as conn:
            active_cat = conn.execute("SELECT id FROM catalogues WHERE is_active = 1 LIMIT 1").fetchone()
            if not active_cat:
                return False

            conn.execute(
                "UPDATE products SET is_archived = 1, updated_at = ? WHERE catalogue_id = ? AND product_id = ?",
                (now, active_cat["id"], product_id.strip())
            )

        self.log_audit(
            actor_id=actor_id,
            actor_role="OWNER",
            action="PRODUCT_ARCHIVED",
            target_id=product_id,
            target_type="PRODUCT",
            details={"product_id": product_id}
        )
        return True

    # ---------------- POLICY METHODS ----------------
    def get_active_policy(self) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM policy_documents WHERE is_active = 1 LIMIT 1").fetchone()
            if not row:
                return None
            p = dict(row)
            if p.get("sections") and isinstance(p["sections"], str):
                try:
                    p["sections"] = json.loads(p["sections"])
                except Exception:
                    p["sections"] = {}
            return p

    def save_policy(
        self,
        title: str,
        content: str,
        version: str,
        sections: Dict[str, Any],
        actor_id: str
    ) -> Dict[str, Any]:
        """Saves a new policy document version and activates it."""
        now = _now_iso()
        pol_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            # Deactivate prior
            conn.execute("UPDATE policy_documents SET is_active = 0 WHERE is_active = 1")
            # Insert active
            conn.execute(
                """INSERT INTO policy_documents 
                   (id, version, title, content, sections, is_active, created_at, updated_at) 
                   VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                (pol_id, version, title, content, json.dumps(sections), now, now)
            )

        self.log_audit(
            actor_id=actor_id,
            actor_role="OWNER",
            action="POLICY_UPDATED",
            target_id=pol_id,
            target_type="POLICY",
            details={"version": version, "title": title, "sections_count": len(sections)}
        )

        return self.get_active_policy() # type: ignore

    # ---------------- FEEDBACK METHODS ----------------
    def create_feedback(
        self,
        customer_id: str,
        customer_email: str,
        feedback_type: str,
        message: str,
        product_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        rating: Optional[int] = None,
        is_demo: bool = False
    ) -> Dict[str, Any]:
        """Submits customer feedback. CRITICAL: NEVER automatically updates official products."""
        fb_id = str(uuid.uuid4())
        now = _now_iso()

        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO feedback 
                   (id, customer_id, customer_email, feedback_type, product_id, conversation_id, message, rating, status, is_demo, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)""",
                (
                    fb_id,
                    customer_id,
                    customer_email,
                    feedback_type,
                    product_id.strip() if product_id else None,
                    conversation_id.strip() if conversation_id else None,
                    message.strip(),
                    rating,
                    1 if is_demo else 0,
                    now
                )
            )

        self.log_audit(
            actor_id=customer_id,
            actor_role="CUSTOMER",
            action="FEEDBACK_SUBMITTED",
            target_id=fb_id,
            target_type="FEEDBACK",
            details={"type": feedback_type, "product_id": product_id, "is_demo": is_demo}
        )

        return self.get_feedback_by_id(fb_id) # type: ignore

    def get_feedback_by_id(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM feedback WHERE id = ?", (feedback_id,)).fetchone()
            return dict(row) if row else None

    def get_feedback_for_customer(self, customer_id: str) -> List[Dict[str, Any]]:
        """Privacy enforcement: Customer sees ONLY their own feedback."""
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM feedback WHERE customer_id = ? ORDER BY created_at DESC", (customer_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_all_feedback_for_owner(
        self,
        status: Optional[str] = None,
        feedback_type: Optional[str] = None,
        product_id: Optional[str] = None,
        is_demo: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """Owner feedback review interface."""
        query = "SELECT * FROM feedback WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.upper())

        if feedback_type:
            query += " AND feedback_type = ?"
            params.append(feedback_type)

        if product_id:
            query += " AND product_id = ?"
            params.append(product_id.strip())

        if is_demo is not None:
            query += " AND is_demo = ?"
            params.append(1 if is_demo else 0)

        query += " ORDER BY created_at DESC"

        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def update_feedback_status(
        self,
        feedback_id: str,
        status: str,
        owner_id: str,
        resolution_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """Owner reviews feedback and updates status (UNDER_REVIEW, RESOLVED, REJECTED)."""
        valid_statuses = ("PENDING", "UNDER_REVIEW", "RESOLVED", "REJECTED")
        st = status.upper()
        if st not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

        now = _now_iso()
        resolved_at = now if st in ("RESOLVED", "REJECTED") else None

        with self.get_connection() as conn:
            conn.execute(
                """UPDATE feedback 
                   SET status = ?, owner_resolution_note = ?, reviewed_by = ?, resolved_at = ? 
                   WHERE id = ?""",
                (st, resolution_note, owner_id, resolved_at, feedback_id)
            )

        self.log_audit(
            actor_id=owner_id,
            actor_role="OWNER",
            action=f"FEEDBACK_{st}",
            target_id=feedback_id,
            target_type="FEEDBACK",
            details={"status": st, "resolution_note": resolution_note}
        )

        return self.get_feedback_by_id(feedback_id) # type: ignore

    # ---------------- AUDIT LOG METHODS ----------------
    def log_audit(
        self,
        actor_id: str,
        actor_role: str,
        action: str,
        target_id: str,
        target_type: str,
        details: Optional[Dict[str, Any]] = None,
        conn: Optional[sqlite3.Connection] = None
    ) -> None:
        log_id = str(uuid.uuid4())
        now = _now_iso()
        details_str = json.dumps(details) if details else "{}"

        try:
            if conn:
                conn.execute(
                    """INSERT INTO audit_logs 
                       (id, actor_id, actor_role, action, target_id, target_type, details, timestamp) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (log_id, actor_id, actor_role, action, target_id, target_type, details_str, now)
                )
            else:
                with self.get_connection() as c:
                    c.execute(
                        """INSERT INTO audit_logs 
                           (id, actor_id, actor_role, action, target_id, target_type, details, timestamp) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (log_id, actor_id, actor_role, action, target_id, target_type, details_str, now)
                    )
        except Exception as e:
            SafeLogger.error(f"Failed to record audit log: {str(e)}")

    def get_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
            result = []
            for r in rows:
                item = dict(r)
                if item.get("details") and isinstance(item["details"], str):
                    try:
                        item["details"] = json.loads(item["details"])
                    except Exception:
                        pass
                result.append(item)
            return result

    # ---------------- EVALUATION METHODS ----------------
    def save_evaluation_run(self, report_dict: Dict[str, Any]) -> None:
        run_id = report_dict.get("report_id", str(uuid.uuid4()))
        now = report_dict.get("timestamp", _now_iso())

        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO evaluation_runs 
                   (id, timestamp, dataset_name, total_questions, passed_count, failed_count, 
                    citation_validity_rate, unsupported_claim_rate, refusal_accuracy, clarification_accuracy, 
                    avg_latency_ms, results_json) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    now,
                    report_dict.get("dataset_name", "Unknown"),
                    report_dict.get("total_questions_tested", 0),
                    report_dict.get("successfully_evaluated", 0),
                    report_dict.get("total_questions_tested", 0) - report_dict.get("successfully_evaluated", 0),
                    report_dict.get("citation_validity_rate", 0.0),
                    report_dict.get("unsupported_claim_rate", 0.0),
                    report_dict.get("refusal_accuracy", 0.0),
                    report_dict.get("clarification_accuracy", 0.0),
                    report_dict.get("avg_latency_ms", 0.0),
                    json.dumps(report_dict.get("details", []))
                )
            )

    def get_latest_evaluation_run(self) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM evaluation_runs ORDER BY timestamp DESC LIMIT 1").fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get("results_json"):
                try:
                    res["details"] = json.loads(res["results_json"])
                except Exception:
                    res["details"] = []
            return res

    # ---------------- SYSTEM STATS & HEALTH ----------------
    def get_system_stats(self) -> Dict[str, Any]:
        """Calculates real dashboard metrics from persistent database records."""
        with self.get_connection() as conn:
            active_cat = conn.execute("SELECT * FROM catalogues WHERE is_active = 1 LIMIT 1").fetchone()
            active_pol = conn.execute("SELECT * FROM policy_documents WHERE is_active = 1 LIMIT 1").fetchone()

            total_products = 0
            if active_cat:
                total_products = conn.execute(
                    "SELECT COUNT(*) as cnt FROM products WHERE catalogue_id = ? AND is_archived = 0",
                    (active_cat["id"],)
                ).fetchone()["cnt"]

            fb_pending = conn.execute("SELECT COUNT(*) as cnt FROM feedback WHERE status = 'PENDING'").fetchone()["cnt"]
            fb_under_review = conn.execute("SELECT COUNT(*) as cnt FROM feedback WHERE status = 'UNDER_REVIEW'").fetchone()["cnt"]
            fb_resolved = conn.execute("SELECT COUNT(*) as cnt FROM feedback WHERE status = 'RESOLVED'").fetchone()["cnt"]
            fb_rejected = conn.execute("SELECT COUNT(*) as cnt FROM feedback WHERE status = 'REJECTED'").fetchone()["cnt"]
            total_feedback = fb_pending + fb_under_review + fb_resolved + fb_rejected

            last_eval = conn.execute(
                "SELECT timestamp, total_questions, passed_count, citation_validity_rate FROM evaluation_runs ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()

            recent_audits = conn.execute(
                "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 5"
            ).fetchall()

            return {
                "active_catalogue": dict(active_cat) if active_cat else None,
                "active_policy": dict(active_pol) if active_pol else None,
                "total_valid_products": total_products,
                "feedback": {
                    "total": total_feedback,
                    "pending": fb_pending,
                    "under_review": fb_under_review,
                    "resolved": fb_resolved,
                    "rejected": fb_rejected
                },
                "last_evaluation": dict(last_eval) if last_eval else None,
                "recent_audits": [dict(a) for a in recent_audits]
            }

db = DatabaseManager()
