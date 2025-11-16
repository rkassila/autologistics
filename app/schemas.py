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
