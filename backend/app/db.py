import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# DATABASE_PATH lets a deployment point SQLite at a persistent disk mount
# (e.g. Render's disk feature) instead of the ephemeral app directory -
# without it, data is lost on every redeploy/restart in most cloud hosts.
DB_PATH = Path(os.environ.get("DATABASE_PATH", str(Path(__file__).resolve().parent.parent / "data.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
