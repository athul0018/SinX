from __future__ import annotations
from typing import Any
from config import Settings
from sheets import SheetsRepository

class UserService:
    def __init__(self, settings: Settings, sheets: SheetsRepository):
        self.settings = settings
        self.sheets = sheets

    async def get(self, telegram_id: int) -> dict[str, Any] | None:
        tid = str(telegram_id).strip()
        for row in await self.sheets.users():
            if str(row.get('Telegram ID','')).strip() == tid:
                if str(row.get('Status','')).strip().upper() == 'ACTIVE':
                    return row
                return None
        return None

    async def add(self, telegram_id: str, name: str, role: str) -> None:
        rows = await self.sheets.users(force=True)
        if any(str(r.get('Telegram ID','')).strip() == telegram_id for r in rows):
            raise ValueError('Telegram ID already exists.')
        await self.sheets.append_rows(self.settings.master_spreadsheet_id, self.settings.users_tab,
                                      [[telegram_id, name, role.upper(), 'Active']])
        self.sheets.invalidate_users()
