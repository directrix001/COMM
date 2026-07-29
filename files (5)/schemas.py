from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict

from .models import ChangeType, Severity, MarkStatus


class SOPVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_number: int
    filename: str
    uploaded_at: datetime
    is_baseline: bool


class SOPOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    versions: List[SOPVersionOut] = []


class AuditorMarkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: MarkStatus
    note: Optional[str] = None
    marked_by: str
    created_at: datetime


class ChangeItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_version_id: int
    to_version_id: int
    section_label: Optional[str] = None
    change_type: ChangeType
    severity: Severity
    old_text: Optional[str] = None
    new_text: Optional[str] = None
    explanation: str
    marks: List[AuditorMarkOut] = []


class UploadResponse(BaseModel):
    sop_id: int
    sop_title: str
    version_id: int
    version_number: int
    is_baseline: bool
    message: str
    changes: List[ChangeItemOut] = []


class MarkRequest(BaseModel):
    status: MarkStatus
    note: Optional[str] = None
    marked_by: str = "unknown"
