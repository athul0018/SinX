# Google Sheets setup

## Existing master workbook

Keep your existing tabs:

### Users

Telegram ID | Name | Role | Status

Roles supported by the new architecture:
- OWNER
- AUTHORIZED

### Employees

Employee ID | Name | Designation | Status | Joining Date

### Attendance

Date | Employee ID | Name | Morning | Afternoon | Morning Time | Afternoon Time | Marked By

## New Progress Reports tab

Create a tab named `Progress Reports` with this header:

Record ID | Date | Submitted By | Classification | Clarification | Job Description | Allocated Workers | Actual Status | Quantity Completed | Remarks | Photo Ref | Route

The bot first creates a PLAN row. When Actual Progress is submitted, it updates that same row with Actual Status, Quantity Completed, Remarks, Photo Ref, and Route. The same consolidated row is then carbon-copied to the routed workbook.

## Routing

Configure separate spreadsheet IDs:

PO_WORKS_SPREADSHEET_ID
LABOUR_SUPPLY_SPREADSHEET_ID
PO_AMENDMENT_SPREADSHEET_ID

The bot writes a carbon-copy row to the appropriate workbook.

Classification routing:

Under PO
→ PO Works File

Labour Supply
→ Labour Supply File

PO Amendment Required
→ PO Amendment File

## Important

If the three routing workbooks do not yet exist, leave the IDs blank. The master report still works.
