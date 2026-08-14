# GSB Attendance + Progress Monitoring

This is a modular refactor for the existing Telegram attendance bot.

## Architecture

Telegram
  ↓
python-telegram-bot
  ↓
Conversation handlers
  ↓
AttendanceService / ProgressService
  ↓
SheetsRepository
  ↓
Google Sheets

Google Sheets is accessed through synchronous gspread in worker threads using asyncio.to_thread(). This prevents Google network latency from blocking the Telegram event loop.

## Performance

1. User/employee data is cached for a short TTL.
2. Worksheet objects and spreadsheet objects are cached.
3. Attendance loads today's records once per attendance session.
4. Attendance updates are batch-written.
5. Google 429/5xx/timeouts use exponential backoff with jitter.
6. Telegram users receive an acknowledgement before heavy Google operations.
7. ConversationHandler remains sequential. python-telegram-bot explicitly warns against concurrent update processing with stateful ConversationHandler.
8. The consolidated progress submission updates the existing plan row rather than creating a second master row.

## Progress workflow

/todayplan

1. Under PO / Not Under PO
2. If Not Under PO:
   - PO Amendment Required
   - Labour Supply
3. Job Description
4. Allocated Workers
5. Confirmation

/actualprogress

1. Status:
   - Hold
   - No Clearance
   - Progressing
   - Erection Completed
   - Alignment Completed
   - Handed Over
2. Quantity Completed
3. Remarks
4. Up to two photos
5. DONE
6. Master + routed report

## Photo storage

For permanent links, use:

PHOTO_STORAGE=drive

The first Drive upload will open an OAuth browser window. It creates a separate drive_token.pickle because Drive requires an additional OAuth scope.

## Migration warning

Do not overwrite your working bot before testing this version against a copy of your spreadsheet.

The current source supplied earlier contains additional Owner/User-management handlers that were not included in the source excerpt used for this refactor. Those handlers should be merged into this architecture rather than discarded.
