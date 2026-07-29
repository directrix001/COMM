"""
ORM models.

SOP            -- one row per named procedure (e.g. "Month-End Variance Reconciliation")
SOPVersion     -- one row per uploaded PDF of that SOP (v1, v2, v3 ...)
ChangeItem     -- one row per detected difference between two consecutive versions
AuditorMark    -- one row per auditor action taken on a ChangeItem (can be several,
                  e.g. a flag followed by a note, but we keep the latest as "current")
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Enum, Boolean
)
from sqlalchemy.orm import relationship

from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class SOP(Base):
    __tablename__ = "sops"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow)

    versions = relationship(
        "SOPVersion", back_populates="sop",
        order_by="SOPVersion.version_number", cascade="all, delete-orphan"
    )


class SOPVersion(Base):
    __tablename__ = "sop_versions"

    id = Column(Integer, primary_key=True)
    sop_id = Column(Integer, ForeignKey("sops.id"), nullable=False)
    version_number = Column(Integer, nullable=False)          # 1, 2, 3 ...
    filename = Column(String(512), nullable=False)
    storage_path = Column(String(1024), nullable=False)       # where the PDF bytes live on disk
    extracted_text = Column(Text, nullable=False)              # raw text pulled from the PDF
    uploaded_at = Column(DateTime, default=utcnow)
    is_baseline = Column(Boolean, default=False)                # True only for version 1

    sop = relationship("SOP", back_populates="versions")

    changes_from_here = relationship(
        "ChangeItem", foreign_keys="ChangeItem.from_version_id",
        back_populates="from_version"
    )
    changes_to_here = relationship(
        "ChangeItem", foreign_keys="ChangeItem.to_version_id",
        back_populates="to_version"
    )


class ChangeType(str, enum.Enum):
    numeric_threshold = "numeric_threshold"   # a number/%/currency/date value changed
    process = "process"                       # a step was added/removed/reordered
    routing_ownership = "routing_ownership"   # who approves / who is notified changed
    wording = "wording"                       # phrasing/formatting only, no operational impact


class Severity(str, enum.Enum):
    critical = "critical"
    moderate = "moderate"
    minor = "minor"


class ChangeItem(Base):
    __tablename__ = "change_items"

    id = Column(Integer, primary_key=True)
    from_version_id = Column(Integer, ForeignKey("sop_versions.id"), nullable=False)
    to_version_id = Column(Integer, ForeignKey("sop_versions.id"), nullable=False)

    section_label = Column(String(255), nullable=True)   # nearest heading/step, if found
    change_type = Column(Enum(ChangeType), nullable=False)
    severity = Column(Enum(Severity), nullable=False)

    old_text = Column(Text, nullable=True)   # null for pure insertions
    new_text = Column(Text, nullable=True)   # null for pure deletions
    explanation = Column(Text, nullable=False)  # plain-language "what changed and why"

    from_version = relationship(
        "SOPVersion", foreign_keys=[from_version_id], back_populates="changes_from_here"
    )
    to_version = relationship(
        "SOPVersion", foreign_keys=[to_version_id], back_populates="changes_to_here"
    )
    marks = relationship(
        "AuditorMark", back_populates="change_item",
        order_by="AuditorMark.created_at", cascade="all, delete-orphan"
    )


class MarkStatus(str, enum.Enum):
    acknowledged = "acknowledged"
    flagged = "flagged"
    note = "note"


class AuditorMark(Base):
    __tablename__ = "auditor_marks"

    id = Column(Integer, primary_key=True)
    change_item_id = Column(Integer, ForeignKey("change_items.id"), nullable=False)
    status = Column(Enum(MarkStatus), nullable=False)
    note = Column(Text, nullable=True)
    marked_by = Column(String(255), nullable=False, default="unknown")
    created_at = Column(DateTime, default=utcnow)

    change_item = relationship("ChangeItem", back_populates="marks")
