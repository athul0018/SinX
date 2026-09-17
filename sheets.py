from __future__ import annotations

import asyncio
import logging
import os
import pickle
import random
import time
from typing import Any, Callable, TypeVar

import gspread
import google.auth
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

from config import Settings


log = logging.getLogger(__name__)
T = TypeVar("T")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"
]


class SheetsRepository:
    """Centralized asynchronous wrapper around synchronous gspread."""

    def __init__(self, settings: Settings):
        self.settings = settings

        # Google client
        self._client_obj: gspread.Client | None = None
        self._client_lock = asyncio.Lock()

        # Spreadsheet / worksheet cache
        self._spreadsheets: dict[str, gspread.Spreadsheet] = {}
        self._worksheets: dict[
            tuple[str, str],
            gspread.Worksheet,
        ] = {}

        # General cache lock
        self._cache_lock = asyncio.Lock()

        # Users cache
        self._users_cache: list[dict[str, Any]] | None = None
        self._users_at = 0.0

        # Employees cache
        self._employees_cache: list[dict[str, Any]] | None = None
        self._employees_at = 0.0

    # =========================================================
    # GOOGLE AUTHENTICATION
    # =========================================================
    def _authorize_sync(self) -> gspread.Client:
        """Create Google Sheets client."""

        # Cloud Run authentication
        if os.getenv("K_SERVICE"):
            credentials, _ = google.auth.default(
                scopes=SCOPES
            )

            return gspread.authorize(credentials)

        # Local Windows authentication
        credentials = None

        if os.path.exists("token.pickle"):
            try:
                with open("token.pickle", "rb") as token:
                    credentials = pickle.load(token)

            except Exception:
                log.warning(
                    "Could not load token.pickle."
                )
                credentials = None

        if (
            credentials
            and credentials.expired
            and credentials.refresh_token
        ):
            credentials.refresh(Request())

        if not credentials or not credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                SCOPES,
            )

            credentials = flow.run_local_server(
                host="localhost",
                port=8080,
                open_browser=True,
            )

            with open("token.pickle", "wb") as token:
                pickle.dump(credentials, token)

        return gspread.authorize(credentials)
    
    async def _client(self) -> gspread.Client:
        """Return the cached Google client."""

        if self._client_obj is not None:
            return self._client_obj

        async with self._client_lock:
            if self._client_obj is None:
                self._client_obj = await asyncio.to_thread(
                    self._authorize_sync
                )

        return self._client_obj
        
    # =========================================================
    # WORKSHEET ACCESS
    # =========================================================

    async def worksheet(
        self,
        spreadsheet_id: str,
        tab: str,
    ) -> gspread.Worksheet:
        """Return a cached worksheet object."""

        key = (spreadsheet_id, tab)

        if key in self._worksheets:
            return self._worksheets[key]

        client = await self._client()

        if spreadsheet_id not in self._spreadsheets:
            self._spreadsheets[spreadsheet_id] = (
                await asyncio.to_thread(
                    client.open_by_key,
                    spreadsheet_id,
                )
            )

        worksheet = await asyncio.to_thread(
            self._spreadsheets[spreadsheet_id].worksheet,
            tab,
        )

        self._worksheets[key] = worksheet

        return worksheet

    # =========================================================
    # RETRY / BACKOFF
    # =========================================================

    @staticmethod
    def _retryable(error: Exception) -> bool:
        """Determine whether a Google API error should be retried."""

        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)

        if status in {429, 500, 502, 503, 504}:
            return True

        message = str(error).lower()

        retry_messages = (
            "429",
            "rate limit",
            "too many requests",
            "timeout",
            "timed out",
            "500",
            "502",
            "503",
            "504",
            "service unavailable",
        )

        return any(
            token in message
            for token in retry_messages
        )

    async def _call(
        self,
        function: Callable[[], T],
        operation: str,
    ) -> T:
        """
        Execute a synchronous gspread operation outside the
        asyncio event loop, with retry/backoff.
        """

        last_error: Exception | None = None

        retries = getattr(
            self.settings,
            "sheets_retries",
            5,
        )

        retry_base = getattr(
            self.settings,
            "retry_base_seconds",
            0.5,
        )

        for attempt in range(retries + 1):
            try:
                return await asyncio.to_thread(function)

            except Exception as error:
                last_error = error

                if (
                    attempt >= retries
                    or not self._retryable(error)
                ):
                    log.exception(
                        "Sheets operation failed: %s",
                        operation,
                    )
                    raise

                delay = min(
                    10.0,
                    retry_base * (2 ** attempt),
                )

                delay += random.uniform(
                    0.0,
                    0.25,
                )

                log.warning(
                    "%s failed. Retrying in %.2fs "
                    "(attempt %d/%d)",
                    operation,
                    delay,
                    attempt + 1,
                    retries,
                )

                await asyncio.sleep(delay)

        raise last_error or RuntimeError(operation)

    # =========================================================
    # READ OPERATIONS
    # =========================================================

    async def records(
        self,
        spreadsheet_id: str,
        tab: str,
    ) -> list[dict[str, Any]]:
        """Read all records from a worksheet."""

        ws = await self.worksheet(
            spreadsheet_id,
            tab,
        )

        return await self._call(
            ws.get_all_records,
            f"get_all_records:{tab}",
        )

    async def attendance(self) -> list[dict[str, Any]]:
        """Return attendance records."""

        return await self.records(
            self.settings.master_spreadsheet_id,
            self.settings.attendance_tab,
        )

    async def search_master_data(
        self,
        search_text: str,
    ) -> list[dict[str, Any]]:
        """Search master equipment data by PO, tag, or description."""

        search_text = search_text.strip().lower()

        if not search_text:
            return []

        ws = await self.worksheet(
            self.settings.master_spreadsheet_id,
            self.settings.master_data_tab,
        )

        values = await self._call(
            ws.get_all_values,
            f"search_master_data:{self.settings.master_data_tab}",
        )

        if not values:
            log.warning(
                "Master Data sheet is empty: %s",
                self.settings.master_data_tab,
            )
            return []

        # --------------------------------------------------
        # Find the actual header row.
        # This handles blank rows above the table.
        # --------------------------------------------------

        header_row_index = None

        for i, row in enumerate(values[:20]):
            normalized = [
                str(cell).strip().lower()
                for cell in row
            ]

            if "po ref" in normalized:
                header_row_index = i
                break

        if header_row_index is None:
            log.error(
                "Could not find 'PO ref' header in Master Data. "
                "Tab=%s First rows=%r",
                self.settings.master_data_tab,
                values[:5],
            )
            return []

        headers = values[header_row_index]

        # --------------------------------------------------
        # Map headers safely
        # --------------------------------------------------

        header_map: dict[str, int] = {}

        for index, header in enumerate(headers):
            key = str(header).strip().lower()

            if key and key not in header_map:
                header_map[key] = index

        log.info(
            "Master Data headers found: %s",
            list(header_map.keys()),
        )

        def get_value(
            row: list[str],
            header: str,
        ) -> str:

            index = header_map.get(
                header.lower()
            )

            if index is None:
                return ""

            if index >= len(row):
                return ""

            return str(row[index]).strip()

        # --------------------------------------------------
        # Search data rows
        # --------------------------------------------------

        results: list[dict[str, Any]] = []

        for row in values[header_row_index + 1:]:
            po_ref = get_value(
                row,
                "PO ref",
            )

            equipment_tag = get_value(
                row,
                "Equipment Tag No.",
            )

            description = get_value(
                row,
                "Equipment Description",
            )

            searchable = " ".join(
                [
                    po_ref,
                    equipment_tag,
                    description,
                ]
            ).lower()

            if search_text in searchable:
                results.append({
                    "PO ref": po_ref,
                    "Equipment Tag No.": equipment_tag,
                    "Equipment Description": description,
                })

        log.info(
            "Master Data search '%s' returned %d result(s)",
            search_text,
            len(results),
        )

        return results
    # =========================================================
    # WRITE OPERATIONS
    # =========================================================

    async def append_rows(
        self,
        spreadsheet_id: str,
        tab: str,
        rows: list[list[Any]],
    ) -> None:
        """Append multiple rows in one Google Sheets request."""

        if not rows:
            return

        ws = await self.worksheet(
            spreadsheet_id,
            tab,
        )

        await self._call(
            lambda: ws.append_rows(
                rows,
                value_input_option="USER_ENTERED",
            ),
            f"append_rows:{tab}",
        )

    async def update_range(
        self,
        spreadsheet_id: str,
        tab: str,
        range_name: str,
        values: list[list[Any]],
    ) -> None:
        """Update a specific range."""

        ws = await self.worksheet(
            spreadsheet_id,
            tab,
        )

        await self._call(
            lambda: ws.update(
                range_name,
                values,
                value_input_option="USER_ENTERED",
            ),
            f"update:{tab}:{range_name}",
        )

    async def batch_update(
        self,
        spreadsheet_id: str,
        tab: str,
        requests: list[dict[str, Any]],
    ) -> None:
        """Perform multiple worksheet updates."""

        if not requests:
            return

        ws = await self.worksheet(
            spreadsheet_id,
            tab,
        )

        await self._call(
            lambda: ws.batch_update(
                requests,
                value_input_option="USER_ENTERED",
            ),
            f"batch_update:{tab}",
        )

    # =========================================================
    # USERS CACHE
    # =========================================================

    async def users(
        self,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        """Return Users records using an in-memory TTL cache."""

        now = time.monotonic()

        cache_ttl = getattr(
            self.settings,
            "cache_ttl_seconds",
            30,
        )

        async with self._cache_lock:
            if (
                not force
                and self._users_cache is not None
                and now - self._users_at < cache_ttl
            ):
                return list(self._users_cache)

        rows = await self.records(
            self.settings.master_spreadsheet_id,
            self.settings.users_tab,
        )

        async with self._cache_lock:
            self._users_cache = list(rows)
            self._users_at = time.monotonic()

        return list(rows)

    def invalidate_users(self) -> None:
        """Clear the Users cache."""

        self._users_cache = None
        self._users_at = 0.0

    # =========================================================
    # EMPLOYEES CACHE
    # =========================================================

    async def employees(
        self,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        """Return Employees records using an in-memory TTL cache."""

        now = time.monotonic()

        cache_ttl = getattr(
            self.settings,
            "cache_ttl_seconds",
            30,
        )

        async with self._cache_lock:
            if (
                not force
                and self._employees_cache is not None
                and now - self._employees_at < cache_ttl
            ):
                return list(self._employees_cache)

        rows = await self.records(
            self.settings.master_spreadsheet_id,
            self.settings.employees_tab,
        )

        async with self._cache_lock:
            self._employees_cache = list(rows)
            self._employees_at = time.monotonic()

        return list(rows)

    def invalidate_employees(self) -> None:
        """Clear the Employees cache."""

        self._employees_cache = None
        self._employees_at = 0.0