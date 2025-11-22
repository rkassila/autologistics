"""Pydantic schemas."""

from typing import Optional, Dict, Any
from pydantic import BaseModel


class DocumentExtractResponse(BaseModel):
    """Extract response."""
    message: str
    is_valid: bool
    validation_message: Optional[str] = None
    document_hash: str
    extracted_text: Optional[str] = None
    structured_fields: Optional[Dict[str, Any]] = None
    storage_url: Optional[str] = None
    already_exists: bool = False


class DocumentSaveRequest(BaseModel):
    """Save request."""
    document_hash: str
    filename: str
    structured_fields: Optional[Dict[str, Any]] = None


class DocumentUploadResponse(BaseModel):
    """Upload response."""
    message: str
    document_id: Optional[int] = None
    is_duplicate: bool = False
    structured_fields: Optional[Dict[str, Any]] = None
    storage_url: Optional[str] = None


class ModelLogRequest(BaseModel):
    """Model log request."""
    success: bool
    document_id: Optional[int] = None
    document_hash: str
    document_link: Optional[str] = None
    extraction_result: Optional[Dict[str, Any]] = None
    original_values: Optional[Dict[str, Any]] = None
    corrected_values: Optional[Dict[str, Any]] = None
    corrections_made: Optional[Dict[str, Any]] = None
    failure_reason: Optional[str] = None


class ModelLogResponse(BaseModel):
    """Model log response."""
    message: str
    log_id: Optional[int] = None
