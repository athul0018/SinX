# GSB site management (web)

Telegram bot files at the repo root are frozen. The web product lives in `apps/`.

## Stack

- Next.js PWA on Vercel (`apps/web`)
- FastAPI (`apps/api`) — deploy on Fly.io or Railway
- Neon PostgreSQL

## Local run

1. Create a Neon database and copy the connection string.

2. API:

```
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Set `DATABASE_URL` to the Neon URL using SQLAlchemy scheme `postgresql+psycopg://...`.

```
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

Default owner (change after first login): `owner@example.com` / `changeme`

3. Web:

```
cd apps/web
copy .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000

## Attendance

- Morning: Present / Absent
- Evening (morning Present only): Full day or Half day, plus OT hours

## Master list

Owner: Home → Master list → download Excel template → upload filled file for the selected site.

Authorized users only see the master list for their assigned site. Daily PO progress writes erection status, erection front status, latest remarks, and the latest photo link onto that row.

Non-PO jobs are stored in a separate `non_po_jobs` table.

Photos go to Google Drive named `{plan number}_1.jpg`. Set `DRIVE_FOLDER_ID` in `apps/api/.env` and keep `credentials.json` available (same as the old bot).
