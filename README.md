# SAGE-Review

SAGE-Review is a local React and FastAPI application for thesis-section,
manuscript, revision, and labeled-dataset analysis.

## Setup

From the repository root in PowerShell:

```powershell
..\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

For development and tests, install `backend/requirements-dev.txt` instead.

Install frontend dependencies once:

```powershell
cd frontend
npm install
```

## Run

For normal local development, the frontend command starts both Vite and the
FastAPI backend:

```powershell
cd C:\1All_Project\thesis_score\SAGE-Review\frontend
npm run dev
```

The backend can still be run separately when needed:

```powershell
cd C:\1All_Project\thesis_score\SAGE-Review
..\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8001
```

Open <http://127.0.0.1:5174/>. API documentation is available at
<http://127.0.0.1:8001/docs>.

## Optional Gemini feedback

Copy `backend/.env.example` to `backend/.env`, set `GEMINI_API_KEY`, and change
`LLM_FEEDBACK_ENABLED` to `true`. Manuscript excerpts are sent to Gemini only
when this option is enabled. Do not enable external LLM feedback for sensitive
documents unless the user has consented to that processing.

## Tests

```powershell
..\.venv\Scripts\python.exe -m pytest -q
```
