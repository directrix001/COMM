"""
SOP Anomaly Detector — backend.

Endpoints
---------
POST   /sops/upload                     upload a SOP PDF (title + file).
                                         First upload for a title -> stored as baseline (v1).
                                         Later uploads -> diffed against the latest stored
                                         version and the differences are returned + persisted.
GET    /sops                            list all SOPs with their version history.
GET    /sops/{sop_id}/versions          version history for one SOP.
GET    /versions/{version_id}/changes   changes detected going INTO this version
                                         (i.e. vs. the version before it).
POST   /changes/{change_id}/mark        auditor marks a change: acknowledge / flag / note.
GET    /changes/{change_id}             single change + its full mark history.

Run:
    uvicorn app.main:app --reload
Docs:
    http://127.0.0.1:8000/docs
"""
import os
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas
from .database import Base, engine, get_db
from .pdf_utils import extract_text_from_pdf
from .diff_engine import diff_texts

Base.metadata.create_all(bind=engine)

STORAGE_DIR = Path(os.getenv("SOP_STORAGE_DIR", "./storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="SOP Anomaly Detector",
    description="Upload SOP PDFs, store versions, and auto-detect + classify changes between them.",
    version="0.1.0",
)

# The frontend (sop-suite-ui.html) is opened as a standalone file / served from
# a different origin than the API, so CORS needs to be open for it to call
# these endpoints from the browser. Tighten this to a specific origin in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/sops/upload", response_model=schemas.UploadResponse)
async def upload_sop(
    title: str = Form(..., description="SOP title — used to match this upload to an existing SOP"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(400, "Please upload a PDF file.")

    file_bytes = await file.read()
    try:
        extracted_text = extract_text_from_pdf(file_bytes)
    except ValueError as e:
        raise HTTPException(422, str(e))

    sop = db.query(models.SOP).filter(models.SOP.title == title).first()
    is_new_sop = sop is None
    if is_new_sop:
        sop = models.SOP(title=title)
        db.add(sop)
        db.flush()  # get sop.id before we need it below

    previous_version = (
        db.query(models.SOPVersion)
        .filter(models.SOPVersion.sop_id == sop.id)
        .order_by(models.SOPVersion.version_number.desc())
        .first()
    )
    next_version_number = 1 if previous_version is None else previous_version.version_number + 1

    # Persist the PDF bytes to disk
    safe_title = "".join(c if c.isalnum() else "_" for c in title)[:60]
    stored_filename = f"{safe_title}_v{next_version_number}_{file.filename}"
    storage_path = STORAGE_DIR / stored_filename
    with open(storage_path, "wb") as f:
        f.write(file_bytes)

    version = models.SOPVersion(
        sop_id=sop.id,
        version_number=next_version_number,
        filename=file.filename,
        storage_path=str(storage_path),
        extracted_text=extracted_text,
        is_baseline=(previous_version is None),
    )
    db.add(version)
    db.flush()

    changes_out = []
    if previous_version is not None:
        detected = diff_texts(previous_version.extracted_text, extracted_text)
        for item in detected:
            change = models.ChangeItem(
                from_version_id=previous_version.id,
                to_version_id=version.id,
                section_label=item["section_label"],
                change_type=item["change_type"],
                severity=item["severity"],
                old_text=item["old_text"],
                new_text=item["new_text"],
                explanation=item["explanation"],
            )
            db.add(change)
            changes_out.append(change)

    db.commit()
    for c in changes_out:
        db.refresh(c)
    db.refresh(version)

    if previous_version is None:
        message = f"Stored as the baseline version (v{version.version_number}) for '{sop.title}'."
    else:
        message = (
            f"Compared against v{previous_version.version_number} — "
            f"found {len(changes_out)} change(s)."
        )

    return schemas.UploadResponse(
        sop_id=sop.id,
        sop_title=sop.title,
        version_id=version.id,
        version_number=version.version_number,
        is_baseline=version.is_baseline,
        message=message,
        changes=changes_out,
    )


@app.get("/sops", response_model=list[schemas.SOPOut])
def list_sops(db: Session = Depends(get_db)):
    return db.query(models.SOP).all()


@app.get("/sops/{sop_id}/versions", response_model=list[schemas.SOPVersionOut])
def list_versions(sop_id: int, db: Session = Depends(get_db)):
    sop = db.query(models.SOP).get(sop_id)
    if not sop:
        raise HTTPException(404, "SOP not found.")
    return sop.versions


@app.get("/versions/{version_id}/changes", response_model=list[schemas.ChangeItemOut])
def get_changes_for_version(version_id: int, db: Session = Depends(get_db)):
    version = db.query(models.SOPVersion).get(version_id)
    if not version:
        raise HTTPException(404, "Version not found.")
    return version.changes_to_here


@app.get("/changes/{change_id}", response_model=schemas.ChangeItemOut)
def get_change(change_id: int, db: Session = Depends(get_db)):
    change = db.query(models.ChangeItem).get(change_id)
    if not change:
        raise HTTPException(404, "Change not found.")
    return change


@app.post("/changes/{change_id}/mark", response_model=schemas.ChangeItemOut)
def mark_change(change_id: int, payload: schemas.MarkRequest, db: Session = Depends(get_db)):
    change = db.query(models.ChangeItem).get(change_id)
    if not change:
        raise HTTPException(404, "Change not found.")
    if payload.status == models.MarkStatus.note and not payload.note:
        raise HTTPException(400, "A note is required when status is 'note'.")

    mark = models.AuditorMark(
        change_item_id=change_id,
        status=payload.status,
        note=payload.note,
        marked_by=payload.marked_by,
    )
    db.add(mark)
    db.commit()
    db.refresh(change)
    return change
