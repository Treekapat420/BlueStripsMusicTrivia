from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os

from .utils.config import settings

class Base(DeclarativeBase):
    pass

def _db_url():
    if settings.database_url:
        return settings.database_url
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trivia.sqlite3")
    return f"sqlite:///{db_path}"

engine = create_engine(_db_url(), echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
