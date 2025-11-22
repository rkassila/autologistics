"""Database connection and operations for PostgreSQL."""

import os
import hashlib
from typing import Optional, Dict, Any
from datetime import date, datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Date, JSON, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from contextlib import contextmanager

Base = declarative_base()

# Field names for structured extraction
STRUCTURED_FIELDS = [
    "tracking_number", "shipper_name", "shipper_address", "receiver_name",
    "receiver_address", "shipment_date", "delivery_date", "weight",
    "dimensions", "carrier", "shipping_method", "status", "special_instructions"
]


class LogisticsDocument(Base):
    """SQLAlchemy model for logistics documents with structured columns."""
    __tablename__ = os.getenv("DB_TABLE_NAME", "logistics_documents")

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False, index=True)
    storage_url = Column(String(500))
    extracted_text = Column(Text)
    document_hash = Column(String(64), unique=True, nullable=False, index=True)

    # Structured extracted fields
    tracking_number = Column(String(100), index=True)
    shipper_name = Column(String(255))
    shipper_address = Column(Text)
    receiver_name = Column(String(255))
    receiver_address = Column(Text)
    shipment_date = Column(Date, index=True)
    delivery_date = Column(Date)
    weight = Column(String(50))
    dimensions = Column(String(100))
    carrier = Column(String(100), index=True)
    shipping_method = Column(String(100))
    status = Column(String(50))
    special_instructions = Column(Text)
    additional_data = Column(JSON)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ModelLog(Base):
    """SQLAlchemy model for model quality logging."""
    __tablename__ = os.getenv("MODEL_LOG_TABLE", "model_log")

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


class Database:
    """Database connection manager."""

    def __init__(self):
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "")
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

    def get_document_by_hash(self, document_hash: str) -> Optional[LogisticsDocument]:
        """Retrieve a document by its hash."""
        with self.get_session() as session:
            return session.query(LogisticsDocument).filter(
                LogisticsDocument.document_hash == document_hash
            ).first()

    def _parse_date_field(self, value: Any) -> Optional[date]:
        """Parse date value - handles date objects, date strings, or None."""
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            # Try to parse date string
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%m-%d-%Y"]:
                try:
                    return datetime.strptime(value.strip(), fmt).date()
                except:
                    continue
        return None

    def save_document(self, filename: str, storage_url: Optional[str],
                     extracted_text: str, document_hash: str,
                     structured_fields: Dict[str, Any],
                     additional_data: Optional[Dict[str, Any]] = None) -> LogisticsDocument:
        """Save a new logistics document to the database."""
        # Prepare kwargs from structured_fields
        kwargs = {
            "filename": filename,
            "storage_url": storage_url,
            "extracted_text": extracted_text,
            "document_hash": document_hash,
            "additional_data": additional_data
        }

        # Add structured fields with date parsing
        for field in STRUCTURED_FIELDS:
            value = structured_fields.get(field)
            # Convert date strings to date objects for date fields
            if field in ["shipment_date", "delivery_date"]:
                kwargs[field] = self._parse_date_field(value)
            else:
                kwargs[field] = value

        with self.get_session() as session:
            document = LogisticsDocument(**kwargs)
            session.add(document)
            session.commit()
            session.refresh(document)
            return document


def compute_document_hash(content: bytes) -> str:
    """Compute SHA256 hash of document content for deduplication."""
    return hashlib.sha256(content).hexdigest()


class ModelLogDatabase:
    """Database connection manager for model log database."""

    def __init__(self):
        db_host = os.getenv("MODEL_LOG_DB_HOST", os.getenv("DB_HOST", "localhost"))
        db_port = os.getenv("MODEL_LOG_DB_PORT", os.getenv("DB_PORT", "5432"))
        db_user = os.getenv("MODEL_LOG_DB_USER", os.getenv("DB_USER", "postgres"))
        db_password = os.getenv("MODEL_LOG_DB_PASSWORD", os.getenv("DB_PASSWORD", ""))
        db_name = os.getenv("MODEL_LOG_DB", "logistics_db")

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


db = Database()
model_log_db = ModelLogDatabase()
