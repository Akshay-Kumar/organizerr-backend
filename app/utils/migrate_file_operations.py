from sqlmodel import Session, select, create_engine
from app.models import FileOperation
from datetime import datetime
from app.utils.db import engine

def run_migration():
    with Session(engine) as session:
        print("DB URL:", engine.url)
        ops = session.exec(select(FileOperation)).all()

        for op in ops:
            updated = False

            if not hasattr(op, "updated_at") or op.updated_at is None:
                op.updated_at = op.timestamp or datetime.utcnow()
                updated = True

            if not hasattr(op, "stage"):
                op.stage = None
                updated = True

            if not hasattr(op, "progress"):
                op.progress = None
                updated = True

            if not hasattr(op, "status"):
                op.status = None
                updated = True

            if updated:
                session.add(op)

        session.commit()
        print("✅ Migration completed")

if __name__ == "__main__":
    run_migration()