from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.schema import Column
from sqlalchemy.sql import text
from sqlalchemy.types import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from settings import get_settings


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def connect_to_postgres() -> Engine:
    """
    Connect to a PostgreSQL database using SQLAlchemy.

    Returns:
        SQLAlchemy Engine object for database connection

    Raises:
        ValueError: If neither database_url nor required parameters are provided
    """

    settings = get_settings()
    host = settings.db_host
    port = settings.db_port
    database = settings.postgres_db
    username = settings.postgres_user
    password = settings.postgres_password

    # Check if required parameters are provided
    if not all([database, username, password]):
        raise ValueError(
            "Either provide database_url or all required parameters "
            "(database, username, password)"
        )

    # Construct database URL
    db_url = f"postgresql+psycopg://{username}:{password}@{host}:{port}/{database}"

    print("Connecting to PostgreSQL database at:", db_url)

    engine = create_engine(db_url)

    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("DB connection test:", result.scalar_one())
    except Exception as e:
        print("DB connection FAILED:", e)

    return engine


SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=connect_to_postgres()
)

Base = declarative_base()


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    followers_to_get = Column(JSONB, nullable=True)
