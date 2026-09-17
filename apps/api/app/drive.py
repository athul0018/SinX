from __future__ import annotations

import io
import os
import pickle
from pathlib import Path

import google.auth
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from app.config import settings

DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]


def _credential_paths() -> tuple[Path, Path]:
    here = Path(__file__).resolve()
    roots = [here.parents[1], here.parents[3] if len(here.parents) > 3 else here.parents[1]]
    for root in roots:
        creds = root / "credentials.json"
        token = root / "drive_token.pickle"
        if creds.exists():
            return creds, token
    return Path("credentials.json"), Path("drive_token.pickle")


def _service():
    if os.getenv("K_SERVICE"):
        credentials, _ = google.auth.default(scopes=DRIVE_SCOPES)
        return build("drive", "v3", credentials=credentials, cache_discovery=False)

    creds_file, token_file = _credential_paths()
    credentials = None
    if token_file.exists():
        with token_file.open("rb") as handle:
            credentials = pickle.load(handle)
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials or not credentials.valid:
        if not creds_file.exists():
            raise RuntimeError("Google Drive credentials.json was not found.")
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), DRIVE_SCOPES)
        credentials = flow.run_local_server(host="localhost", port=8081, open_browser=True)
        with token_file.open("wb") as handle:
            pickle.dump(credentials, handle)
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def upload_plan_photo(content: bytes, filename: str, mime_type: str) -> str:
    service = _service()
    metadata: dict = {"name": filename}
    if settings.drive_folder_id:
        metadata["parents"] = [settings.drive_folder_id]
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
    result = (
        service.files()
        .create(body=metadata, media_body=media, fields="id,webViewLink")
        .execute()
    )
    return result.get("webViewLink") or f"https://drive.google.com/open?id={result['id']}"
