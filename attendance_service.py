from __future__ import annotations

from datetime import datetime
from typing import Any

from config import Settings
from sheets import SheetsRepository


class AttendanceService:

    def __init__(
        self,
        settings: Settings,
        sheets: SheetsRepository,
    ):
        self.settings = settings
        self.sheets = sheets

    def today(self) -> str:
        return datetime.now(
            self.settings.tz
        ).strftime("%d-%m-%Y")

    def current_time(self) -> str:
        return datetime.now(
            self.settings.tz
        ).strftime("%H:%M:%S")

    async def active_employees(
        self,
    ) -> list[dict[str, Any]]:
        rows = await self.sheets.employees()

        return [
            row
            for row in rows
            if str(
                row.get("Status", "")
            ).strip().upper() == "ACTIVE"
        ]

    async def start_session(
        self,
        session: str,
    ) -> tuple[
        list[dict[str, Any]],
        dict[str, dict[str, Any]],
    ]:
        employees = await self.active_employees()

        date = self.today()

        rows = await self.sheets.attendance()

        existing = {
            str(
                row.get("Employee ID", "")
            ).strip().upper(): row
            for row in rows
            if str(
                row.get("Date", "")
            ).strip() == date
        }

        column = (
            "Morning"
            if session == "Morning"
            else "Afternoon"
        )

        pending = [
            employee
            for employee in employees
            if not str(
                existing.get(
                    str(
                        employee.get(
                            "Employee ID",
                            "",
                        )
                    ).strip().upper(),
                    {},
                ).get(column, "")
            ).strip()
        ]

        return pending, existing

    async def save_session(
        self,
        session: str,
        marked_by: str,
        answers: dict[str, str],
    ) -> None:
        date = self.today()

        employees = await self.active_employees()

        rows = await self.sheets.attendance()

        existing: dict[
            str,
            tuple[int, dict[str, Any]],
        ] = {}

        for row_number, row in enumerate(
            rows,
            start=2,
        ):
            if str(
                row.get("Date", "")
            ).strip() != date:
                continue

            employee_id = str(
                row.get("Employee ID", "")
            ).strip().upper()

            existing[employee_id] = (
                row_number,
                row,
            )

        new_rows: list[list[Any]] = []

        updates: list[dict[str, Any]] = []

        timestamp = self.current_time()

        for employee in employees:
            employee_id = str(
                employee.get(
                    "Employee ID",
                    "",
                )
            ).strip()

            key = employee_id.upper()

            status = answers.get(employee_id)

            if not status:
                continue

            old = existing.get(key)

            if old:
                row_number, row = old

                morning = str(
                    row.get("Morning", "")
                ).strip()

                afternoon = str(
                    row.get("Afternoon", "")
                ).strip()

                morning_time = str(
                    row.get("Morning Time", "")
                ).strip()

                afternoon_time = str(
                    row.get("Afternoon Time", "")
                ).strip()

                marked = str(
                    row.get("Marked By", "")
                ).strip()

                if session == "Morning":
                    if morning:
                        continue

                    morning = status
                    morning_time = timestamp

                else:
                    if afternoon:
                        continue

                    afternoon = status
                    afternoon_time = timestamp

                marker = (
                    f"{marked}; "
                    if marked
                    else ""
                ) + f"{session}: {marked_by}"

                updates.append(
                    {
                        "range": (
                            f"A{row_number}:H"
                            f"{row_number}"
                        ),
                        "values": [
                            [
                                date,
                                employee_id,
                                employee.get(
                                    "Name",
                                    "",
                                ),
                                morning,
                                afternoon,
                                morning_time,
                                afternoon_time,
                                marker,
                            ]
                        ],
                    }
                )

            else:
                morning = (
                    status
                    if session == "Morning"
                    else ""
                )

                afternoon = (
                    status
                    if session == "Afternoon"
                    else ""
                )

                morning_time = (
                    timestamp
                    if session == "Morning"
                    else ""
                )

                afternoon_time = (
                    timestamp
                    if session == "Afternoon"
                    else ""
                )

                new_rows.append(
                    [
                        date,
                        employee_id,
                        employee.get(
                            "Name",
                            "",
                        ),
                        morning,
                        afternoon,
                        morning_time,
                        afternoon_time,
                        f"{session}: {marked_by}",
                    ]
                )

        if updates:
            await self.sheets.batch_update(
                self.settings.master_spreadsheet_id,
                self.settings.attendance_tab,
                updates,
            )

        if new_rows:
            await self.sheets.append_rows(
                self.settings.master_spreadsheet_id,
                self.settings.attendance_tab,
                new_rows,
            )

    async def begin(
        self,
        session: str,
    ) -> list[dict[str, Any]]:
        """
        Compatibility method used by bot.py.
        """
        pending, _ = await self.start_session(
            session
        )

        return pending

    async def save(
        self,
        session: str,
        marked_by: str,
        answers: dict[str, str],
    ) -> None:
        """
        Compatibility method used by bot.py.
        """
        await self.save_session(
            session,
            marked_by,
            answers,
        )