from sqlmodel import Session, select
from sqlalchemy import text, inspect
from app.utils.db import engine
from app.models import FileOperation
from datetime import datetime


def column_exists(inspector, table, column):
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def add_column_if_missing(conn, inspector, table, column, ddl):
    if not column_exists(inspector, table, column):
        print(f"➕ Adding column: {column}")
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
    else:
        print(f"✔ Column exists: {column}")


def run_schema_migration():
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print("📦 Tables:", tables)

    if "fileoperation" not in tables:
        print("❌ fileoperation table not found")
        return False

    with engine.connect() as conn:
        # Add columns safely
        add_column_if_missing(conn, inspector, "fileoperation", "torrent_id", "torrent_id INTEGER")
        add_column_if_missing(conn, inspector, "fileoperation", "updated_at", "updated_at TEXT")
        add_column_if_missing(conn, inspector, "fileoperation", "stage", "stage TEXT")
        add_column_if_missing(conn, inspector, "fileoperation", "progress", "progress REAL")
        add_column_if_missing(conn, inspector, "fileoperation", "status", "status TEXT")

        conn.commit()

    return True


def run_data_migration():
    with Session(engine) as session:
        ops = session.exec(select(FileOperation)).all()

        print(f"📊 Migrating {len(ops)} records...")

        for op in ops:
            updated = False

            if not op.updated_at:
                op.updated_at = op.timestamp or datetime.utcnow()
                updated = True

            if op.stage is None:
                op.stage = "completed" if op.success else "processing"
                updated = True

            if op.progress is None:
                op.progress = 100 if op.success else 0
                updated = True

            if op.status is None:
                if op.success is True:
                    op.status = "completed"
                elif op.success is False:
                    op.status = "failed"
                else:
                    op.status = "processing"
                updated = True

            if updated:
                session.add(op)

        session.commit()

        print("✅ Data migration completed")


def main():
    print("🚀 Starting safe migration...")
    print("DB:", engine.url)

    if run_schema_migration():
        run_data_migration()

    print("🎉 Migration finished successfully")


if __name__ == "__main__":
    main()