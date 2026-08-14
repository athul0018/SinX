from __future__ import annotations

import asyncio
import io
import os
import pickle

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]


class DriveUploader:
    """Optional Google Drive photo uploader."""

    def __init__(self, folder_id: str | None):
        self.folder_id = folder_id
        self._service = None
        self._lock = asyncio.Lock()

    def _build_sync(self):
        credentials = None

        if os.path.exists("drive_token.pickle"):
            try:
                with open("drive_token.pickle", "rb") as f:
                    credentials = pickle.load(f)
            except Exception:
                credentials = None

        if credentials and credentials.expired and credentials.refresh_token:
            from google.auth.transport.requests import Request
            credentials.refresh(Request())

        if not credentials or not credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                DRIVE_SCOPES,
            )
            credentials = flow.run_local_server(
                host="localhost",
                port=8081,
                open_browser=True,
            )

            with open("drive_token.pickle", "wb") as f:
                pickle.dump(credentials, f)

        return build(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

    async def service(self):
        if self._service is not None:
            return self._service

        async with self._lock:
            if self._service is None:
                self._service = await asyncio.to_thread(
                    self._build_sync
                )

        return self._service

    async def upload(
        self,
        content: bytes,
        filename: str,
        mime_type: str,
    ) -> str:
        service = await self.service()

        def upload_sync() -> str:
            metadata = {"name": filename}

            if self.folder_id:
                metadata["parents"] = [self.folder_id]

            media = MediaIoBaseUpload(
                io.BytesIO(content),
                mimetype=mime_type,
                resumable=False,
            )

            result = service.files().create(
                body=metadata,
                media_body=media,
                fields="id,webViewLink",
            ).execute()

            return (
                result.get("webViewLink")
                or f"https://drive.google.com/open?id={result['id']}"
            )

        return await asyncio.to_thread(upload_sync)
