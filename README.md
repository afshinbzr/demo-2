# Financial Statement AI Review — Data Governance Demo

Upload a PDF financial statement; a Claude-based agent extracts the figures, grounds each one
in a quote from the source document, classifies the assurance level, computes credit-analysis
ratios, and writes a lender-oriented summary. A deterministic rule engine scores data quality
and quarantines anything suspect for human review.

Built as a working demo of the data governance & data quality spec — RBAC, audit logging,
classification, versioned corrections, and a quarantine workflow.

## What it does

**Extraction (AI).** One Claude call per PDF with native Citations enabled. Every extracted
number is paired with a verbatim quote from the document; where the API confirms that quote
against the source text, the value is marked **✓ Verified** with a page number. Where it
doesn't, the quote is still shown but marked **⚠ Unverified** — never silently dropped.

It also detects:
- **Assurance tier** — compilation (CSRS 4200) / review (CSRE 2400) / audit / unaudited,
  quoted from the accountant's report itself.
- **Period coverage** — single-period vs multi-year, extracting every period present so
  comparatives are captured.
- **Format, language, and unit scale** — English/French/bilingual, mixed document structures,
  and thousands-vs-millions reporting scale. An ambiguous scale is quarantined rather than
  guessed at, because a misread scale distorts the whole analysis.

**Quality scoring (deterministic).** Completeness, validity, consistency (incl. the balance
sheet identity), uniqueness, and citation coverage — computed in Python, not by the model.
Failures are written to a quarantine queue with a reason code; nothing is silently dropped.

**Credit ratios (deterministic).** Liquidity, leverage, profitability, and coverage ratios
computed from the extracted figures. These are a standard commercial-lending framework, not a
reproduction of any lender's proprietary scorecard, and thresholds are rules of thumb that
vary by industry.

**Governance.** Role-based access control (viewer / editor / steward / admin), data
classification with least-privilege visibility, an audit log, and versioned corrections —
a human correction supersedes the AI value without overwriting its history.

## Running it locally

Backend:

```bash
cd backend
python -m venv venv
./venv/Scripts/python.exe -m pip install -r requirements.txt   # macOS/Linux: venv/bin/python
cp .env.example .env        # then fill in ANTHROPIC_API_KEY
./venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

Frontend (dev server with hot reload, talks to the backend on :8000):

```bash
cd frontend
npm install
npm run dev
```

For a single-origin build — the backend serves the built frontend, no CORS:

```bash
cd frontend && npm run build
# then start the backend and open http://localhost:8000
```

## Configuration

All backend config is environment variables; see [backend/.env.example](backend/.env.example)
for the full annotated list. The one that matters before sharing a link is
`UPLOAD_ROLE_PASSWORD` — without it, anyone who can reach the app can trigger billed Claude
API calls.

## Deploying

[render.yaml](render.yaml) is a Render blueprint for a single web service that builds the
frontend and serves it from the backend. It defaults to the free tier (no persistent disk, so
the SQLite database resets on redeploy); the file's header comment explains how to switch to a
durable setup.

## Known scope limits

This is a demo, and a few things are deliberately simplified — worth knowing before reading
the code as if it were production:

- **Authentication is a role picker**, not real identity. Sessions are an in-memory dict.
  RBAC itself *is* enforced server-side on every endpoint.
- **SQLite, no migrations.** Schema changes are applied by recreating the database.
- **No automated retention/purge jobs** and no "right to be forgotten" flow.
- **Citation verification is stochastic.** The Claude Citations API doesn't attach a citation
  to every quote on every run. The app is explicit about this rather than papering over it:
  unverified quotes are labelled, and only verified ones count toward the reliability score.
- **The AI model does not learn from your documents.** The executive dashboard tracks
  extraction quality trends, not model self-improvement — it says so on the page.
