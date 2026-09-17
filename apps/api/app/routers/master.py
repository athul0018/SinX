from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_owner, require_site
from app.excel_master import master_template_bytes, parse_master_excel
from app.models import MasterEquipment, Site
from app.schemas import EquipmentIn, EquipmentOut

router = APIRouter(prefix="/sites/{site_id}/master", tags=["master"])


@router.get("", response_model=list[EquipmentOut])
def list_master(
    db: Session = Depends(get_db),
    site: Site = Depends(require_site),
) -> list[MasterEquipment]:
    return (
        db.query(MasterEquipment)
        .filter(MasterEquipment.site_id == site.id)
        .order_by(MasterEquipment.po_ref, MasterEquipment.equipment_tag)
        .all()
    )


@router.get("/template")
def download_template(_: Site = Depends(require_site), __=Depends(require_owner)):
    return StreamingResponse(
        BytesIO(master_template_bytes()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="GSB-master-list.xlsx"'},
    )


@router.post("/import")
def import_master(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    site: Site = Depends(require_site),
    _owner=Depends(require_owner),
) -> dict:
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Upload an Excel .xlsx file")
    rows = parse_master_excel(file.file.read())
    created = 0
    updated = 0
    for item in rows:
        existing = (
            db.query(MasterEquipment)
            .filter(
                MasterEquipment.site_id == site.id,
                MasterEquipment.po_ref == item["po_ref"],
                MasterEquipment.equipment_tag == item["equipment_tag"],
            )
            .first()
        )
        if existing:
            existing.description = item["description"]
            existing.unit = item["unit"]
            existing.po_quantity = item["po_quantity"]
            existing.completed_quantity = item["completed_quantity"]
            existing.remaining_quantity = item["remaining_quantity"]
            if item["status"]:
                existing.status = item["status"]
            if item["erection_front_status"]:
                existing.erection_front_status = item["erection_front_status"]
            if item["remarks"]:
                existing.remarks = item["remarks"]
            if item["photo_ref"]:
                existing.photo_ref = item["photo_ref"]
            updated += 1
        else:
            db.add(
                MasterEquipment(
                    site_id=site.id,
                    **item,
                )
            )
            created += 1
    db.flush()
    return {"created": created, "updated": updated, "total": created + updated}


@router.post("", response_model=EquipmentOut)
def add_master_row(
    body: EquipmentIn,
    db: Session = Depends(get_db),
    site: Site = Depends(require_site),
    _owner=Depends(require_owner),
) -> MasterEquipment:
    remaining = body.remaining_quantity
    if remaining == 0 and body.po_quantity:
        remaining = body.po_quantity - body.completed_quantity
        if remaining < 0:
            remaining = Decimal("0")
    row = MasterEquipment(
        site_id=site.id,
        po_ref=body.po_ref.strip(),
        equipment_tag=body.equipment_tag.strip(),
        description=body.description.strip(),
        unit=body.unit.strip(),
        po_quantity=body.po_quantity,
        completed_quantity=body.completed_quantity,
        remaining_quantity=remaining,
        status=body.status,
        erection_front_status=body.erection_front_status,
        remarks=body.remarks,
        photo_ref=body.photo_ref,
    )
    db.add(row)
    db.flush()
    return row
