from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

import os

_base = os.environ.get("DATABASE_DIR")
DATA_DIR = Path(_base) if _base else Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DATA_DIR / 'bus_tracker.db'}"

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


def init_db():
    from sqlalchemy import text

    from server import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for stmt in (
            "ALTER TABLE live_status ADD COLUMN level_name VARCHAR(128) DEFAULT ''",
        ):
            try:
                conn.execute(text(stmt))
            except Exception:
                pass
