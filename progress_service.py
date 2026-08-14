from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from config import Settings
from sheets import SheetsRepository


@dataclass
class Plan:
    po_ref: str
    equipment_tag: str
    equipment_description: str
    classification: str
    clarification: str
    job_description: str
    workers: str
    plan_id: str = ""


@dataclass
class Actual:
    status: str
    quantity: str
    remarks: str
    photos: list[str]


class ProgressService:

    def __init__(
        self,
        settings: Settings,
        sheets: SheetsRepository,
    ):
        self.settings = settings
        self.sheets = sheets

    def route_id(
        self,
        classification: str,
    ) -> str | None:

        if classification == "Under PO":
            return self.settings.po_works_spreadsheet_id

        if classification == "Labour Supply":
            return self.settings.labour_supply_spreadsheet_id

        if classification == "PO Amendment Required":
            return self.settings.po_amendment_spreadsheet_id

        return None

    async def save_plan(
        self,
        date: str,
        submitted_by: str,
        plan: Plan,
    ) -> None:

        record_id = (
            f"{date}|"
            f"{submitted_by}|"
            f"{plan.job_description}"
        )

        # This function is retained for compatibility.
        # Your current Today's Plan flow may save directly
        # into Daily Plans from bot.py.

        row = [
            record_id,
            date,
            submitted_by,
            plan.po_ref,
            plan.equipment_tag,
            plan.equipment_description,
            plan.classification,
            plan.clarification,
            plan.job_description,
            plan.workers,
            "",
            "",
            "",
            "",
            "PLAN",
        ]

        await self.sheets.append_rows(
            self.settings.master_spreadsheet_id,
            self.settings.progress_tab,
            [row],
        )

    async def todays_plans(
        self,
        date: str,
        submitted_by: str,
    ) -> list[dict[str, Any]]:

        rows = await self.sheets.records(
            self.settings.master_spreadsheet_id,
            self.settings.daily_plans_tab,
        )

        results: list[dict[str, Any]] = []

        for row in rows:

            row_date = str(
                row.get("Date", "")
            ).strip()

            row_by = str(
                row.get("Planned By", "")
            ).strip()

            status = str(
                row.get("Status", "")
            ).strip().upper()

            if row_date != date:
                continue

            if row_by != submitted_by:
                continue

            if status != "PLANNED":
                continue

            results.append(row)

        return results

    async def consolidate_actual(
        self,
        date: str,
        submitted_by: str,
        plan: Plan,
        actual: Actual,
    ) -> None:

        # ---------------------------------------------------------
        # Photos
        # ---------------------------------------------------------

        photo_1 = (
            actual.photos[0]
            if len(actual.photos) >= 1
            else ""
        )

        photo_2 = (
            actual.photos[1]
            if len(actual.photos) >= 2
            else ""
        )

        # ---------------------------------------------------------
        # Report time
        # ---------------------------------------------------------

        report_time = datetime.now(
            self.settings.tz
        ).strftime("%H:%M:%S")

        # ---------------------------------------------------------
        # Actual Progress columns:
        #
        # Date
        # Plan ID
        # Classification
        # Job Description
        # Status
        # Quantity Completed
        # Remarks
        # Photo 1
        # Photo 2
        # Reported By
        # Report Time
        # ---------------------------------------------------------

        row = [
            date,
            plan.plan_id,
            plan.classification,
            plan.job_description,
            actual.status,
            actual.quantity,
            actual.remarks,
            photo_1,
            photo_2,
            submitted_by,
            report_time,
        ]

        # ---------------------------------------------------------
        # 1. Save Actual Progress
        # ---------------------------------------------------------

        await self.sheets.append_rows(
            self.settings.master_spreadsheet_id,
            self.settings.progress_tab,
            [row],
        )

        # ---------------------------------------------------------
        # 2. Find the selected Daily Plan
        # ---------------------------------------------------------

        daily_rows = await self.sheets.records(
            self.settings.master_spreadsheet_id,
            self.settings.daily_plans_tab,
        )

        target_row_number = None

        for row_number, existing in enumerate(
            daily_rows,
            start=2,
        ):

            existing_plan_id = str(
                existing.get("Plan ID", "")
            ).strip()

            if (
                existing_plan_id
                and existing_plan_id == plan.plan_id
            ):
                target_row_number = row_number
                break

        # ---------------------------------------------------------
        # 3. Mark Daily Plan as Completed
        # ---------------------------------------------------------

        if target_row_number is not None:

            # Daily Plans:
            #
            # A = Date
            # B = Plan ID
            # C = PO Ref
            # D = Job Description
            # E = Classification
            # F = Clarification
            # G = Allocated Workers
            # H = Planned By
            # I = Plan Time
            # J = Status

            await self.sheets.update_range(
                self.settings.master_spreadsheet_id,
                self.settings.daily_plans_tab,
                f"J{target_row_number}:J{target_row_number}",
                [["Completed"]],
            )

        # ---------------------------------------------------------
        # 4. Route to relevant workbook
        # ---------------------------------------------------------

        route_id = self.route_id(
            plan.classification
        )

        if route_id:

            await self.sheets.append_rows(
                route_id,
                self.settings.routing_tab,
                [row],
            )