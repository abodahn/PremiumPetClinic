"""
db.py — PostgreSQL storage layer for Premium Pet Clinic
Replaces the Excel (openpyxl) backend with a real relational database.

All public functions keep the same signatures as the original Excel helpers
so that app.py requires only minimal changes.

Environment variable:
  DATABASE_URL  — standard Postgres connection string
                  e.g. postgresql://user:pass@host:5432/dbname
                  Render.com injects this automatically when you attach a
                  Postgres database to the service.
"""

import os
import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.extras  # RealDictCursor

logger = logging.getLogger("vetapp.db")

# ---------------------------------------------------------------------------
# Table definitions
# Every table is expressed as an ordered list of (column_name, pg_type) pairs.
# TEXT is used for everything — identical to how the Excel backend stored data.
# This keeps the rest of app.py working without any value-conversion changes.
# ---------------------------------------------------------------------------

TABLE_SCHEMAS = {
    "owners": [
        ("id", "TEXT PRIMARY KEY"),
        ("owner_name", "TEXT"),
        ("phone", "TEXT"),
        ("email", "TEXT"),
        ("address", "TEXT"),
        ("preferred_contact", "TEXT"),
        ("notes", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
    ],
    "pets": [
        ("id", "TEXT PRIMARY KEY"),
        ("pet_name", "TEXT"),
        ("species", "TEXT"),
        ("breed", "TEXT"),
        ("sex", "TEXT"),
        ("dob", "TEXT"),
        ("age_years", "TEXT"),
        ("weight_kg", "TEXT"),
        ("color", "TEXT"),
        ("microchip_id", "TEXT"),
        ("spayed_neutered", "TEXT"),
        ("allergies", "TEXT"),
        ("chronic_conditions", "TEXT"),
        ("vaccinations_summary", "TEXT"),
        ("owner_id", "TEXT"),
        ("notes", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
    ],
    "bookings": [
        ("id", "TEXT PRIMARY KEY"),
        ("appointment_start", "TEXT"),
        ("duration_min", "TEXT"),
        ("appointment_end", "TEXT"),
        ("owner_id", "TEXT"),
        ("pet_id", "TEXT"),
        ("visit_weight_kg", "TEXT"),
        ("visit_temp_c", "TEXT"),
        ("appointment_type", "TEXT"),
        ("priority", "TEXT"),
        ("status", "TEXT"),
        ("channel", "TEXT"),
        ("reason", "TEXT"),
        ("symptoms", "TEXT"),
        ("vet_name", "TEXT"),
        ("room", "TEXT"),
        ("services_json", "TEXT"),
        ("service_name", "TEXT"),
        ("service_fee", "TEXT"),
        ("discount_type", "TEXT"),
        ("discount_value", "TEXT"),
        ("discount", "TEXT"),
        ("paid_amount", "TEXT"),
        ("due_amount", "TEXT"),
        ("fee_amount", "TEXT"),
        ("payment_status", "TEXT"),
        ("payment_method", "TEXT"),
        ("payment_channel", "TEXT"),
        ("invoice_no", "TEXT"),
        ("diagnosis", "TEXT"),
        ("treatment_plan", "TEXT"),
        ("prescription", "TEXT"),
        ("lab_tests", "TEXT"),
        ("vaccines_given", "TEXT"),
        ("followup_datetime", "TEXT"),
        ("reminder_channel", "TEXT"),
        ("reminder_sent", "TEXT"),
        ("reminder_last_opened", "TEXT"),
        ("portal_token", "TEXT"),
        ("owner_confirmed", "TEXT"),
        ("owner_update_message", "TEXT"),
        ("owner_update_datetime", "TEXT"),
        ("ai_last_applied_at", "TEXT"),
        ("notes", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
    ],
    "reminders": [
        ("id", "TEXT PRIMARY KEY"),
        ("booking_id", "TEXT"),
        ("owner_id", "TEXT"),
        ("pet_id", "TEXT"),
        ("reminder_type", "TEXT"),
        ("service_name", "TEXT"),
        ("channel", "TEXT"),
        ("status", "TEXT"),
        ("scheduled_for", "TEXT"),
        ("opened_at", "TEXT"),
        ("sent_at", "TEXT"),
        ("message", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
    ],
    "users": [
        ("id", "TEXT PRIMARY KEY"),
        ("username", "TEXT"),
        ("password", "TEXT"),
        ("role", "TEXT"),
        ("active", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
    ],
    "vets": [
        ("id", "TEXT PRIMARY KEY"),
        ("name", "TEXT"),
        ("active", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
    ],
    "rooms": [
        ("id", "TEXT PRIMARY KEY"),
        ("name", "TEXT"),
        ("active", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
    ],
    "services": [
        ("id", "TEXT PRIMARY KEY"),
        ("name", "TEXT"),
        ("cost", "TEXT"),
        ("fee", "TEXT"),
        ("margin", "TEXT"),
        ("margin_type", "TEXT"),
        ("margin_value", "TEXT"),
        ("active", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
    ],
    "whatsapp_templates": [
        ("id", "TEXT PRIMARY KEY"),
        ("name", "TEXT"),
        ("scenario", "TEXT"),
        ("booking_type", "TEXT"),
        ("template_text", "TEXT"),
        ("active", "TEXT"),
        ("is_default", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
    ],
    "roles_permissions": [
        ("id", "TEXT PRIMARY KEY"),
        ("role", "TEXT"),
        ("permissions", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
    ],
    "audit_log": [
        ("id", "TEXT PRIMARY KEY"),
        ("timestamp", "TEXT"),
        ("username", "TEXT"),
        ("role", "TEXT"),
        ("action", "TEXT"),
        ("entity_type", "TEXT"),
        ("entity_id", "TEXT"),
        ("details", "TEXT"),
        ("ip", "TEXT"),
        ("user_agent", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _get_database_url():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Set it to a valid PostgreSQL connection string, e.g. "
            "postgresql://user:pass@host:5432/dbname"
        )
    # Render (and Heroku) sometimes return 'postgres://' but psycopg2 requires
    # 'postgresql://'
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


@contextmanager
def _get_conn():
    """Yield a psycopg2 connection, committing on success or rolling back on error."""
    conn = psycopg2.connect(_get_database_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema helpers (replaces ensure_headers / ensure_workbook)
# ---------------------------------------------------------------------------

def ensure_headers(table: str, desired_headers: list):
    """
    Non-destructive schema migration — equivalent to the Excel ensure_headers.
    Creates the table if it does not exist, then adds any missing columns.
    """
    # Map column name → type from TABLE_SCHEMAS (default TEXT for dynamic cols)
    schema_map = {col: typ for col, typ in TABLE_SCHEMAS.get(table, [])}

    with _get_conn() as conn:
        cur = conn.cursor()

        # Build CREATE TABLE statement from known schema or pure TEXT columns
        if table in TABLE_SCHEMAS:
            col_defs = ", ".join(
                f'"{col}" {typ}' for col, typ in TABLE_SCHEMAS[table]
            )
        else:
            col_defs = '"id" TEXT PRIMARY KEY, ' + ", ".join(
                f'"{h}" TEXT' for h in desired_headers if h != "id"
            )

        cur.execute(
            f'CREATE TABLE IF NOT EXISTS "{table}" ({col_defs})'
        )

        # Add any columns that exist in desired_headers but not yet in the table
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
            """,
            (table,),
        )
        existing_cols = {row[0] for row in cur.fetchall()}

        for h in desired_headers:
            if h not in existing_cols:
                col_type = schema_map.get(h, "TEXT")
                # Strip PRIMARY KEY from alter-add (can't alter-add PK)
                col_type_clean = col_type.replace(" PRIMARY KEY", "")
                try:
                    cur.execute(
                        f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{h}" {col_type_clean}'
                    )
                    logger.info("Added column %s.%s", table, h)
                except Exception as exc:
                    logger.warning("Could not add column %s.%s: %s", table, h, exc)


def init_tables():
    """Create all application tables. Called once at startup."""
    for table, columns in TABLE_SCHEMAS.items():
        headers = [col for col, _ in columns]
        ensure_headers(table, headers)
    logger.info("All database tables verified / created.")


# ---------------------------------------------------------------------------
# CRUD helpers — same API as the original Excel functions
# ---------------------------------------------------------------------------

def read_all(table: str) -> list:
    """Return all rows of *table* as a list of dicts (ordered by created_at)."""
    try:
        with _get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            # Order by created_at if the column exists, else by id
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'created_at'
                """,
                (table,),
            )
            has_created_at = cur.fetchone() is not None
            order = "created_at" if has_created_at else "id"
            cur.execute(f'SELECT * FROM "{table}" ORDER BY "{order}"')
            rows = cur.fetchall()
            # Convert RealDictRow → plain dict; replace None → ""
            return [
                {k: ("" if v is None else v) for k, v in row.items()}
                for row in rows
            ]
    except psycopg2.errors.UndefinedTable:
        return []
    except Exception as exc:
        logger.error("read_all(%s) failed: %s", table, exc)
        return []


def append_row(table: str, *args):
    """
    Insert a row into *table*.

    Supported call forms (mirrors the original Excel helper):
      append_row(table, row_dict)
      append_row(table, headers, row_dict)
    """
    if len(args) == 1:
        row_dict = args[0]
    elif len(args) == 2:
        _, row_dict = args          # headers arg ignored — schema drives columns
    else:
        raise TypeError("append_row() expects (table, row_dict) or (table, headers, row_dict)")

    if not row_dict:
        return

    cols = list(row_dict.keys())
    vals = [str(row_dict[c]) if row_dict[c] is not None else "" for c in cols]
    placeholders = ", ".join(["%s"] * len(cols))
    col_names = ", ".join(f'"{c}"' for c in cols)

    try:
        with _get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})',
                vals,
            )
    except Exception as exc:
        logger.error("append_row(%s) failed: %s", table, exc)
        raise


def update_row_by_id(table: str, *args) -> bool:
    """
    Update a row identified by id.

    Supported call forms:
      update_row_by_id(table, row_id, updates_dict)
      update_row_by_id(table, headers, row_id, updates_dict)   ← headers ignored
    """
    if len(args) == 2:
        row_id, updates = args
    elif len(args) == 3:
        _, row_id, updates = args   # headers arg ignored
    else:
        raise TypeError(
            "update_row_by_id() expects (table, row_id, updates_dict) "
            "or (table, headers, row_id, updates_dict)"
        )

    if not updates:
        return False

    set_parts = ", ".join(f'"{k}" = %s' for k in updates.keys())
    vals = [str(v) if v is not None else "" for v in updates.values()]
    vals.append(str(row_id))

    try:
        with _get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f'UPDATE "{table}" SET {set_parts} WHERE "id" = %s',
                vals,
            )
            return cur.rowcount > 0
    except Exception as exc:
        logger.error("update_row_by_id(%s, %s) failed: %s", table, row_id, exc)
        return False


def delete_row_by_id(table: str, row_id) -> bool:
    """Delete the row with the given id from *table*."""
    try:
        with _get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f'DELETE FROM "{table}" WHERE "id" = %s', (str(row_id),))
            return cur.rowcount > 0
    except Exception as exc:
        logger.error("delete_row_by_id(%s, %s) failed: %s", table, row_id, exc)
        return False
