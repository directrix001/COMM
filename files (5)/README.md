# SOP Anomaly Detector — backend

FastAPI service for the third tab of the SOP suite: upload a SOP PDF, it's
stored; upload the next version of the same SOP, and it's automatically
compared against what's stored, with each difference classified and left
open for an auditor to mark.

## Run it

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Interactive API docs: http://127.0.0.1:8000/docs

Storage: a local SQLite file (`sop.db`) plus a `storage/` folder for the raw
PDFs. Both are created automatically on first run. To point at Postgres
instead, set `DATABASE_URL` before starting the app — nothing else changes.

## How it works

1. **`POST /sops/upload`** — form upload with `title` + `file` (PDF).
   - No SOP with that title yet → stored as the baseline (v1), nothing to compare.
   - SOP already exists → text is extracted from the new PDF and diffed
     against the most recently stored version. Every difference is saved as
     a `ChangeItem` and returned in the response.
2. **Diffing** (`app/diff_engine.py`) — lines are matched with `difflib`,
   then each changed block is classified:
   - **`numeric_threshold`** — a %, $ amount, or plain number changed but the
     surrounding wording stayed close to the same (e.g. "8%" → "12%").
   - **`routing_ownership`** — approval/notification language touched
     (words like *approve, route, notify, cc, sign-off, owner*).
   - **`process`** — a step was added, removed, or substantially rewritten.
   - **`wording`** — phrasing/formatting only.
   Severity (`critical` / `moderate` / `minor`) is scored off the change type
   — numeric changes and deleted steps default to critical since they're the
   ones most likely to silently change what gets escalated.
3. **Explanations** (`app/ai_explain.py`) — rule-based templates by default
   (no external calls, runs offline). Set `OPENAI_API_KEY` in the
   environment and it automatically switches to **gpt-4o-mini** for the
   explanation text, falling back to the rule-based version if the call
   fails for any reason. The same file has an `embed_sections()` stub for
   plugging in `text-embedding-3-small`-based RAG section matching later —
   useful once SOPs start getting reordered or renamed between versions and
   the current position-based matching starts to drift.
4. **Auditor marking** — **`POST /changes/{change_id}/mark`** with
   `{"status": "acknowledged" | "flagged" | "note", "note": "...", "marked_by": "..."}`.
   Marks are additive (kept as a history per change), so you can see who
   flagged something and when, plus any follow-up notes.

## Endpoints

| Method | Path                              | What it does                                   |
|--------|------------------------------------|-------------------------------------------------|
| POST   | `/sops/upload`                    | Upload a PDF; stores baseline or diffs + stores |
| GET    | `/sops`                           | List all SOPs with version history              |
| GET    | `/sops/{sop_id}/versions`         | Version history for one SOP                     |
| GET    | `/versions/{version_id}/changes`  | Changes detected going into that version        |
| GET    | `/changes/{change_id}`            | One change + its full mark history              |
| POST   | `/changes/{change_id}/mark`       | Auditor acknowledges / flags / notes a change    |

## Wiring this to the UI you already have

The upload widget in the Anomaly Detector tab should `POST` to `/sops/upload`
with `multipart/form-data` (`title`, `file`). The response's `changes` array
maps directly onto the change cards — `change_type` → the type tag,
`severity` → the severity chip, `explanation` → the card body, and
`old_text`/`new_text` → the redline view. The auditor buttons should call
`POST /changes/{id}/mark`.

## Known gaps (by design, left for the next pass)

- No auth — add a real user identity instead of the free-text `marked_by` field.
- No OCR — scanned PDFs with no text layer will raise a 422.
- Section matching is position-based (via `difflib`), not embedding-based —
  works well while SOP structure stays stable version to version; swap in
  `embed_sections()` once SOPs start getting restructured.
- No endpoint yet to compare two *arbitrary* versions (only "latest vs new
  upload") — straightforward to add: pull both `extracted_text` values and
  call `diff_texts()` directly.
