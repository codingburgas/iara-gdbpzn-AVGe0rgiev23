"""
apply_vessel_columns.py
Run once to add new vessel columns and new tables that are missing from the DB.
Safe to re-run — each operation is wrapped in try/except.
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "iara.db")

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

# ── 1. Add new columns to vessel ─────────────────────────────────────────────
new_cols = [
    ("name_bg",           "VARCHAR(150)"),
    ("name_en",           "VARCHAR(150)"),
    ("port_registration", "VARCHAR(100)"),
    ("registration_date", "DATE"),
    ("status",            "VARCHAR(20) DEFAULT 'Active'"),
    ("gross_tonnage",     "FLOAT"),
    ("owner_egn",         "VARCHAR(20)"),
    ("created_at",        "DATETIME"),
]
for col, col_type in new_cols:
    try:
        cur.execute(f"ALTER TABLE vessel ADD COLUMN {col} {col_type}")
        print(f"  + vessel.{col}")
    except sqlite3.OperationalError as e:
        print(f"  skip vessel.{col}: {e}")

# ── 2. Create vessel_document ────────────────────────────────────────────────
try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vessel_document (
            id             INTEGER PRIMARY KEY,
            vessel_id      INTEGER NOT NULL REFERENCES vessel(id),
            uploaded_by_id INTEGER REFERENCES users(id),
            doc_type       VARCHAR(50) NOT NULL,
            filename       VARCHAR(255) NOT NULL,
            original_name  VARCHAR(255) NOT NULL,
            notes          TEXT,
            uploaded_at    DATETIME
        )
    """)
    print("  + vessel_document created / already exists")
except sqlite3.OperationalError as e:
    print(f"  skip vessel_document: {e}")

# ── 3. Create vessel_photo ───────────────────────────────────────────────────
try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vessel_photo (
            id             INTEGER PRIMARY KEY,
            vessel_id      INTEGER NOT NULL REFERENCES vessel(id),
            uploaded_by_id INTEGER REFERENCES users(id),
            filename       VARCHAR(255) NOT NULL,
            caption        VARCHAR(255),
            is_primary     BOOLEAN DEFAULT 0,
            uploaded_at    DATETIME
        )
    """)
    print("  + vessel_photo created / already exists")
except sqlite3.OperationalError as e:
    print(f"  skip vessel_photo: {e}")

# ── 4. Create vessel_ownership_history ──────────────────────────────────────
try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vessel_ownership_history (
            id             INTEGER PRIMARY KEY,
            vessel_id      INTEGER NOT NULL REFERENCES vessel(id),
            recorded_by_id INTEGER REFERENCES users(id),
            owner_name     VARCHAR(100) NOT NULL,
            owner_egn      VARCHAR(20),
            from_date      DATE NOT NULL,
            to_date        DATE,
            notes          TEXT,
            created_at     DATETIME
        )
    """)
    print("  + vessel_ownership_history created / already exists")
except sqlite3.OperationalError as e:
    print(f"  skip vessel_ownership_history: {e}")

# ── 5. Stamp alembic_version to the new revision ─────────────────────────────
try:
    cur.execute("UPDATE alembic_version SET version_num = '1330580e428d'")
    print("  + alembic_version stamped to 1330580e428d")
except sqlite3.OperationalError as e:
    print(f"  skip alembic stamp: {e}")

conn.commit()
conn.close()
print("\nDone.")
