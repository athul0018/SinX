from __future__ import annotations
from datetime import datetime
from typing import Any
from config import Settings
from sheets import SheetsRepository

class EmployeeService:
    def __init__(self, settings: Settings, sheets: SheetsRepository):
        self.settings = settings
        self.sheets = sheets

    async def find(self, employee_id: str):
        rows = await self.sheets.employees(force=True)
        for n, row in enumerate(rows, start=2):
            if str(row.get('Employee ID','')).strip().upper() == employee_id.strip().upper():
                return n, row
        return None

    async def add(self, employee_id: str, name: str, designation: str, joining_date: str):
        datetime.strptime(joining_date, '%d-%m-%Y')
        if await self.find(employee_id):
            raise ValueError('Employee ID already exists.')
        await self.sheets.append_rows(self.settings.master_spreadsheet_id, self.settings.employees_tab,
                                      [[employee_id, name, designation, 'Active', joining_date]])
        self.sheets.invalidate_employees()

    async def update(self, employee_id: str, name: str, designation: str, joining_date: str):
        found = await self.find(employee_id)
        if not found:
            raise ValueError('Employee ID not found.')
        datetime.strptime(joining_date, '%d-%m-%Y')
        row_no, old = found
        await self.sheets.update_range(self.settings.master_spreadsheet_id, self.settings.employees_tab,
                                       f'B{row_no}:E{row_no}',
                                       [[name, designation, old.get('Status','Active'), joining_date]])
        self.sheets.invalidate_employees()

    async def deactivate(self, employee_id: str):
        found = await self.find(employee_id)
        if not found:
            raise ValueError('Employee ID not found.')
        row_no, _ = found
        await self.sheets.update_range(self.settings.master_spreadsheet_id, self.settings.employees_tab,
                                       f'D{row_no}', [['Inactive']])
        self.sheets.invalidate_employees()
