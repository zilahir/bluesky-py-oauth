from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.schema import Column
from sqlalchemy.sql import text
from sqlalchemy.types import DateTime, Integer, String, Text
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


class OAuthAuthRequest(Base):
    __tablename__ = "oauth_auth_request"

    id = Column(Integer, primary_key=True)
    state = Column(String(255), nullable=False, unique=True)
    authserver_iss = Column(String(255), nullable=False)
    did = Column(String(255), nullable=True)
    handle = Column(String(255), nullable=True)
    pds_url = Column(String(255), nullable=True)
    pkce_verifier = Column(String(255), nullable=False)
    scope = Column(String(255), nullable=True)
    dpop_authserver_nonce = Column(String(255), nullable=True)
    dpop_private_jwk = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class OAuthSession(Base):
    __tablename__ = "oauth_session"

    id = Column(Integer, primary_key=True)
    did = Column(String(255), nullable=False)
    handle = Column(String(255), nullable=False)
    pds_url = Column(String(512), nullable=False)
    authserver_iss = Column(String(512), nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    dpop_authserver_nonce = Column(String(512), nullable=True)
    dpop_private_jwk = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
