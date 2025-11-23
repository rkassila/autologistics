"""Database connection and operations for Model Log database."""

import os
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from contextlib import contextmanager

Base = declarative_base()


class ModelLog(Base):
    """SQLAlchemy model for model quality logging."""
    __tablename__ = os.getenv("DB_MODEL_NAME", "model_log")

    id = Column(Integer, primary_key=True, index=True)
    success = Column(Boolean, nullable=False)
    # Foreign key references main table (name from DB_TABLE_NAME env var)
    # Note: Foreign key constraint should be added manually in database if needed
    main_table_name = os.getenv("DB_TABLE_NAME", "logistics_documents")
    document_id = Column(Integer, nullable=True)
    document_hash = Column(String(64), nullable=False, index=True)
    document_link = Column(String(500))
    extraction_result = Column(JSON)
    original_values = Column(JSON)
    corrected_values = Column(JSON)
    corrections_made = Column(JSON)
    failure_reason = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class ModelDatabase:
    """Database connection manager for model log database."""

    def __init__(self):
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "")
        # Use same database as logistics_db (DB_NAME)
        db_name = os.getenv("DB_NAME", "logistics_db")

        if os.getenv("INSTANCE_CONNECTION_NAME"):
            db_url = f"postgresql+psycopg2://{db_user}:{db_password}@/{db_name}?host=/cloudsql/{os.getenv('INSTANCE_CONNECTION_NAME')}"
        else:
            db_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

        self.engine = create_engine(db_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def check_connection(self) -> bool:
        """Check if database connection is working."""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    @contextmanager
    def get_session(self):
        """Get database session with context manager."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# Create model log database instance
model_log_db = ModelDatabase()
