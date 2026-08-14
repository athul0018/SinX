from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    master_spreadsheet_id: str
    users_tab: str
    employees_tab: str
    attendance_tab: str
    progress_tab: str
    daily_plans_tab: str
    master_data_tab: str
    timezone: str
    cache_ttl: int
    sheets_retries: int
    retry_base: float
    photo_storage: str
    drive_folder_id: str | None
    po_works_spreadsheet_id: str | None
    labour_supply_spreadsheet_id: str | None
    po_amendment_spreadsheet_id: str | None
    routing_tab: str

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def load_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    master = os.getenv("MASTER_SPREADSHEET_ID", "").strip()
    daily_plans_tab=os.getenv("DAILY_PLANS_TAB", "Daily Plans"),
    master_data_tab=os.getenv("MASTER_DATA_TAB", "Progress"),

    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")
    if not master:
        raise RuntimeError("MASTER_SPREADSHEET_ID is not configured.")

    return Settings(
    telegram_token=token,
    master_spreadsheet_id=master,

    users_tab=os.getenv("USERS_TAB", "Users"),
    employees_tab=os.getenv("EMPLOYEES_TAB", "Employees"),
    attendance_tab=os.getenv("ATTENDANCE_TAB", "Attendance"),

    progress_tab=os.getenv(
        "PROGRESS_TAB",
        "Progress Reports"
    ),

    daily_plans_tab=os.getenv(
        "DAILY_PLANS_TAB",
        "Daily Plans"
    ),

    master_data_tab=os.getenv(
        "MASTER_DATA_TAB",
        "Progress"
    ),

    timezone=os.getenv(
        "BOT_TIMEZONE",
        "Asia/Kolkata"
    ),

    cache_ttl=int(
        os.getenv("CACHE_TTL", "30")
    ),

    sheets_retries=int(
        os.getenv("SHEETS_RETRIES", "5")
    ),

    retry_base=float(
        os.getenv("RETRY_BASE", "0.5")
    ),

    photo_storage=os.getenv(
        "PHOTO_STORAGE",
        "drive"
    ).lower(),

    drive_folder_id=os.getenv(
        "DRIVE_FOLDER_ID"
    ) or None,

    po_works_spreadsheet_id=os.getenv(
        "PO_WORKS_SPREADSHEET_ID"
    ) or None,

    labour_supply_spreadsheet_id=os.getenv(
        "LABOUR_SUPPLY_SPREADSHEET_ID"
    ) or None,

    po_amendment_spreadsheet_id=os.getenv(
        "PO_AMENDMENT_SPREADSHEET_ID"
    ) or None,

    routing_tab=os.getenv(
        "ROUTING_TAB",
        "Progress Reports"
    ),
)
