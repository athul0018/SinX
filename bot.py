from __future__ import annotations

import asyncio
import logging
import math
import os
from datetime import datetime

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
import uvicorn

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import Settings, load_settings
from sheets import SheetsRepository
from user_service import UserService
from employee_service import EmployeeService
from attendance_service import AttendanceService
from progress_service import ProgressService, Plan, Actual
from drive import DriveUploader

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
log=logging.getLogger('gsb-bot')

ADD_ID,ADD_NAME,ADD_DESIG,ADD_DATE,ADD_CONFIRM=range(1,6)
EDIT_ID,EDIT_NAME,EDIT_DESIG,EDIT_DATE,EDIT_CONFIRM=range(10,15)
DEACT_ID,DEACT_CONFIRM=range(20,22)
USER_ID,USER_NAME,USER_CONFIRM=range(30,33)
ATT_ACTION,ATT_CONFIRM=range(40,42)
PLAN_CLASS, PLAN_CLARIFY, PLAN_MASTER_SEARCH, PLAN_MASTER_SELECT, PLAN_JOB, PLAN_WORKERS, PLAN_CONFIRM = range(50,57)
ACT_JOB,ACT_STATUS,ACT_QTY,ACT_REMARKS,ACT_PHOTOS=range(60,65)

STATUSES=['Hold','No Clearance','Progressing','Erection Completed','Alignment Completed','Handed Over']

def svc(c):
    d=c.application.bot_data
    return d['settings'],d['sheets'],d['users'],d['employees'],d['attendance'],d['progress'],d['drive']

def kb(rows): return ReplyKeyboardMarkup(rows, resize_keyboard=True)
def today(s): return datetime.now(s.tz).strftime('%d-%m-%Y')

async def user_for(update, users): return await users.get(update.effective_user.id)
async def require(update, users, roles):
    u=await user_for(update,users)
    if not u:
        await update.message.reply_text('❌ Access denied.'); return None
    if str(u.get('Role','')).strip().upper() not in roles:
        await update.message.reply_text('❌ You do not have permission.'); return None
    return u

async def start(update,c):
    s,sh,u,*_=svc(c); user=await user_for(update,u)
    if not user:
        await update.message.reply_text('❌ You are not authorized to use this system.'); return
    role=str(user.get('Role','')).upper()
    if role=='OWNER':
        menu=[['👥 Employees'],['👤 Authorized Person'],['📊 Attendance'],['📈 Progress Monitoring'],['📥 Reports']]
    elif role=='AUTHORIZED':
        menu=[['👥 Employees'],['🌅 Morning Attendance'],['☀️ Afternoon Attendance'],['📈 Progress Monitoring'],["📊 Today's Status"]]
    else:
        await update.message.reply_text('❌ Invalid user role.'); return
    await update.message.reply_text(f"Welcome {user.get('Name') or update.effective_user.first_name}!\n\n{'🏠 OWNER PANEL' if role=='OWNER' else '📋 SITE ATTENDANCE PANEL'}\n\nSelect an option:",reply_markup=kb(menu))

async def back(update,c): await start(update,c)
async def myid(update,c): await update.message.reply_text(f'Your Telegram User ID is:\n\n{update.effective_user.id}')

# ---------- employee management ----------
async def employee_menu(update,c):
    s,sh,u,e,*_=svc(c)
    if not await require(update,u,{'OWNER','AUTHORIZED'}): return
    await update.message.reply_text('👥 EMPLOYEE MANAGEMENT',reply_markup=kb([['➕ Add Employee'],['📋 Employee List'],['✏️ Edit Employee'],['🚫 Deactivate Employee'],['🔙 Back']]))

async def employee_list(update,c):
    s,sh,u,e,*_=svc(c)
    if not await require(update,u,{'OWNER','AUTHORIZED'}): return
    rows=await sh.employees()
    if not rows: await update.message.reply_text('📋 No employees found.'); return
    out=['📋 EMPLOYEE LIST\n']
    for r in rows: out.append(f"• {r.get('Employee ID','')}\n  {r.get('Name','')}\n  {r.get('Designation','')}\n  Status: {r.get('Status','')}\n")
    await update.message.reply_text('\n'.join(out))

async def add_start(update,c): await update.message.reply_text('➕ ADD EMPLOYEE\n\nEnter Employee ID.'); return ADD_ID
async def add_id(update,c): c.user_data['eid']=update.message.text.strip(); await update.message.reply_text('Enter employee full name.'); return ADD_NAME
async def add_name(update,c): c.user_data['ename']=update.message.text.strip(); await update.message.reply_text('Enter designation.'); return ADD_DESIG
async def add_desig(update,c): c.user_data['edesig']=update.message.text.strip(); await update.message.reply_text('Enter joining date.\nFormat: DD-MM-YYYY'); return ADD_DATE
async def add_date(update,c):
    v=update.message.text.strip()
    try: datetime.strptime(v,'%d-%m-%Y')
    except ValueError: await update.message.reply_text('❌ Invalid date. Use DD-MM-YYYY.'); return ADD_DATE
    c.user_data['edate']=v
    await update.message.reply_text(f"📋 CONFIRM EMPLOYEE\n\nID: {c.user_data['eid']}\nName: {c.user_data['ename']}\nDesignation: {c.user_data['edesig']}\nJoining Date: {v}\n\nAdd employee?",reply_markup=kb([['✅ Confirm'],['❌ Cancel']])); return ADD_CONFIRM
async def add_confirm(update,c):
    if update.message.text.strip()=='❌ Cancel': c.user_data.clear(); await update.message.reply_text('❌ Employee addition cancelled.'); return ConversationHandler.END
    if update.message.text.strip()!='✅ Confirm': return ADD_CONFIRM
    s,sh,u,e,*_=svc(c); await update.message.reply_text('⏳ Saving employee...')
    try:
        await e.add(c.user_data['eid'],c.user_data['ename'],c.user_data['edesig'],c.user_data['edate'])
        eid,name=c.user_data['eid'],c.user_data['ename']; c.user_data.clear(); await update.message.reply_text(f'✅ EMPLOYEE ADDED\n\nID: {eid}\nName: {name}')
    except ValueError as ex: await update.message.reply_text(f'❌ {ex}')
    except Exception: log.exception('add employee'); await update.message.reply_text('⚠️ Unable to add employee.')
    return ConversationHandler.END

async def edit_start(update,c): await update.message.reply_text('✏️ EDIT EMPLOYEE\n\nEnter Employee ID.'); return EDIT_ID
async def edit_id(update,c):
    s,sh,u,e,*_=svc(c); eid=update.message.text.strip(); found=await e.find(eid)
    if not found: await update.message.reply_text('❌ Employee ID not found.'); return EDIT_ID
    c.user_data.update(edit_id=eid,edit_old=found[1]); await update.message.reply_text(f"Enter new employee name.\nCurrent: {found[1].get('Name','')}"); return EDIT_NAME
async def edit_name(update,c): c.user_data['edit_name']=update.message.text.strip(); await update.message.reply_text('Enter new designation.'); return EDIT_DESIG
async def edit_desig(update,c): c.user_data['edit_desig']=update.message.text.strip(); await update.message.reply_text('Enter new joining date.\nFormat: DD-MM-YYYY'); return EDIT_DATE
async def edit_date(update, c):
    from datetime import datetime

    text = update.message.text.strip()

    try:
        date_value = datetime.strptime(
            text,
            "%d-%m-%Y"
        )
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid date.\n\n"
            "Please use DD-MM-YYYY.\n"
            "Example: 10-08-2026"
        )
        return EDIT_DATE

    c.user_data["edit_date"] = date_value.strftime("%d-%m-%Y")

    await update.message.reply_text(
    "✏️ EDIT EMPLOYEE — CONFIRM\n\n"
    f"Employee ID: {c.user_data.get('edit_id', '')}\n"
    f"New Name: {c.user_data.get('edit_name', '')}\n"
    f"New Designation: {c.user_data.get('edit_desig', '')}\n"
    f"New Joining Date: {c.user_data.get('edit_date', '')}\n\n"
    "Please select an option:",
    reply_markup=kb([
        ["✅ Confirm Edit"],
        ["❌ Cancel"],
    ]),
)

    return EDIT_CONFIRM
    from datetime import datetime

    text = update.message.text.strip()

    try:
        date_value = datetime.strptime(
            text,
            "%d-%m-%Y"
        )
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid date.\n\n"
            "Please use DD-MM-YYYY.\n"
            "Example: 10-08-2026"
        )
        return EDIT_DATE

    c.user_data["edit_date"] = date_value.strftime(
        "%d-%m-%Y"
    )

    old = c.user_data.get("edit_old", {})
    
    await update.message.reply_text(
        "✏️ EDIT EMPLOYEE — CONFIRM\n\n"
        f"Employee ID: {c.user_data.get('edit_id', '')}\n"
        f"New Name: {c.user_data.get('edit_name', '')}\n"
        f"New Designation: {c.user_data.get('edit_desig', '')}\n"
        f"New Joining Date: {c.user_data.get('edit_date', '')}\n\n"
        "Type YES to save or NO to cancel."
    )

    return EDIT_CONFIRM
    v=update.message.text.strip()
    try: datetime.strptime(v,'%d-%m-%Y')
    except ValueError: await update.message.reply_text('❌ Invalid date.'); return EDIT_DATE
    c.user_data['edit_date']=v; await update.message.reply_text('Save these changes?',reply_markup=kb([['✅ Confirm Edit'],['❌ Cancel']])); return EDIT_CONFIRM
async def edit_confirm(update,c):
    if update.message.text.strip()=='❌ Cancel': c.user_data.clear(); await update.message.reply_text('❌ Edit cancelled.'); return ConversationHandler.END
    if update.message.text.strip()!='✅ Confirm Edit': return EDIT_CONFIRM
    s,sh,u,e,*_=svc(c); await update.message.reply_text('⏳ Updating employee...')
    try: await e.update(c.user_data['edit_id'],c.user_data['edit_name'],c.user_data['edit_desig'],c.user_data['edit_date']); c.user_data.clear(); await update.message.reply_text('✅ EMPLOYEE UPDATED SUCCESSFULLY.')
    except Exception: log.exception('edit employee'); await update.message.reply_text('⚠️ Unable to update employee.')
    return ConversationHandler.END

async def deact_start(update,c): await update.message.reply_text('🚫 DEACTIVATE EMPLOYEE\n\nEnter Employee ID.'); return DEACT_ID
async def deact_id(update,c):
    s,sh,u,e,*_=svc(c); eid=update.message.text.strip(); found=await e.find(eid)
    if not found: await update.message.reply_text('❌ Employee ID not found.'); return DEACT_ID
    if str(found[1].get('Status','')).upper()=='INACTIVE': await update.message.reply_text('ℹ️ This employee is already inactive.'); return ConversationHandler.END
    c.user_data['deact_id']=eid; await update.message.reply_text(f"⚠️ CONFIRM DEACTIVATION\n\nID: {eid}\nName: {found[1].get('Name','')}\n\nContinue?",reply_markup=kb([['✅ Deactivate'],['❌ Cancel']])); return DEACT_CONFIRM
async def deact_confirm(update,c):
    if update.message.text.strip()=='❌ Cancel': c.user_data.clear(); await update.message.reply_text('❌ Deactivation cancelled.'); return ConversationHandler.END
    if update.message.text.strip()!='✅ Deactivate': return DEACT_CONFIRM
    s,sh,u,e,*_=svc(c); await update.message.reply_text('⏳ Updating employee status...')
    try: await e.deactivate(c.user_data['deact_id']); c.user_data.clear(); await update.message.reply_text('✅ EMPLOYEE DEACTIVATED.\n\nHistorical records are preserved.')
    except Exception: log.exception('deactivate'); await update.message.reply_text('⚠️ Unable to deactivate employee.')
    return ConversationHandler.END

# ---------- owner users ----------
async def user_menu(update,c):
    s,sh,u,*_=svc(c)
    if not await require(update,u,{'OWNER'}): return
    await update.message.reply_text('👤 USER MANAGEMENT',reply_markup=kb([['➕ Add Authorized Person'],['➕ Add Owner'],['🔙 Back']]))
async def user_start(update,c):
    c.user_data['new_role']='AUTHORIZED' if update.message.text.strip()=='➕ Add Authorized Person' else 'OWNER'
    await update.message.reply_text('Enter the Telegram User ID.\n\nUse /myid in this bot to find an ID.'); return USER_ID
async def user_id(update,c):
    v=update.message.text.strip()
    if not v.isdigit(): await update.message.reply_text('❌ Invalid Telegram ID. Please enter numbers only.'); return USER_ID
    c.user_data['new_id']=v; await update.message.reply_text('Enter the person\'s name.'); return USER_NAME
async def user_name(update,c):
    c.user_data['new_name']=update.message.text.strip(); await update.message.reply_text(f"📋 CONFIRM USER\n\nTelegram ID: {c.user_data['new_id']}\nName: {c.user_data['new_name']}\nRole: {c.user_data['new_role']}\n\nAdd this user?",reply_markup=kb([['✅ Confirm User'],['❌ Cancel']])); return USER_CONFIRM
async def user_confirm(update,c):
    if update.message.text.strip()=='❌ Cancel': c.user_data.clear(); await update.message.reply_text('❌ User addition cancelled.'); return ConversationHandler.END
    if update.message.text.strip()!='✅ Confirm User': return USER_CONFIRM
    s,sh,u,*_=svc(c); await update.message.reply_text('⏳ Saving user...')
    try: await u.add(c.user_data['new_id'],c.user_data['new_name'],c.user_data['new_role']); role=c.user_data['new_role']; c.user_data.clear(); await update.message.reply_text(f'✅ {role} ADDED SUCCESSFULLY.')
    except ValueError as ex: await update.message.reply_text(f'❌ {ex}')
    except Exception: log.exception('add user'); await update.message.reply_text('⚠️ Unable to add user.')
    return ConversationHandler.END

# ---------- attendance ----------
async def attendance_menu(update,c):
    s,sh,u,*_=svc(c)
    if not await require(update,u,{'OWNER','AUTHORIZED'}): return
    await update.message.reply_text('📊 ATTENDANCE',reply_markup=kb([['🌅 Morning Attendance'],['☀️ Afternoon Attendance'],["📊 Today's Status"],['🔙 Back']]))
async def att_start(update,c):
    s,sh,u,e,a,*_=svc(c)
    if not await require(update,u,{'OWNER','AUTHORIZED'}): return ConversationHandler.END
    session='Morning' if update.message.text.strip()=='🌅 Morning Attendance' else 'Afternoon'
    await update.message.reply_text(f'⏳ Loading {session.lower()} attendance...')
    pending=await a.begin(session)
    if not pending: await update.message.reply_text(f'⚠️ {session} attendance is already marked for all active employees today.'); return ConversationHandler.END
    user=await user_for(update,u); c.user_data['att']={'session':session,'employees':pending,'index':0,'answers':{},'marked_by':user.get('Name') or update.effective_user.first_name}; return await att_show(update,c)
async def att_show(update,c):
    st=c.user_data['att']
    if st['index']>=len(st['employees']): return await att_review(update,c)
    e=st['employees'][st['index']]
    await update.message.reply_text(f"{'🌅' if st['session']=='Morning' else '☀️'} {st['session'].upper()} ATTENDANCE\n\nEmployee {st['index']+1} of {len(st['employees'])}\n\nID: {e.get('Employee ID','')}\nName: {e.get('Name','')}\nDesignation: {e.get('Designation','')}",reply_markup=kb([['✅ Present','❌ Absent'],['🛑 Cancel Attendance']])); return ATT_ACTION
async def att_action(update,c):
    st=c.user_data['att']; v=update.message.text.strip()
    if v=='🛑 Cancel Attendance': c.user_data.clear(); await update.message.reply_text('❌ Attendance cancelled.'); return ConversationHandler.END
    if v not in {'✅ Present','❌ Absent'}: await update.message.reply_text('Select Present or Absent.'); return ATT_ACTION
    eid=str(st['employees'][st['index']].get('Employee ID','')).strip(); st['answers'][eid]='Present' if v=='✅ Present' else 'Absent'; st['index']+=1; return await att_show(update,c)
async def att_review(update,c):
    s,*_=svc(c); st=c.user_data['att']; p=sum(v=='Present' for v in st['answers'].values()); ab=sum(v=='Absent' for v in st['answers'].values()); await update.message.reply_text(f"📋 ATTENDANCE REVIEW\n\nSession: {st['session']}\nDate: {today(s)}\n\n✅ Present: {p}\n❌ Absent: {ab}\n\nSubmit?",reply_markup=kb([['✅ Submit Attendance'],['❌ Cancel']])); return ATT_CONFIRM
async def att_confirm(update,c):
    s,sh,u,e,a,*_=svc(c); v=update.message.text.strip()
    if v=='❌ Cancel': c.user_data.clear(); await update.message.reply_text('❌ Attendance cancelled.'); return ConversationHandler.END
    if v!='✅ Submit Attendance': return ATT_CONFIRM
    st=c.user_data['att']; await update.message.reply_text('⏳ Saving attendance to Google Sheets...')
    try:
        await a.save(st['session'],st['marked_by'],st['answers']); p=sum(v=='Present' for v in st['answers'].values()); ab=sum(v=='Absent' for v in st['answers'].values()); mb=st['marked_by']; sess=st['session']; c.user_data.clear(); await update.message.reply_text(f'✅ {sess.upper()} ATTENDANCE SAVED\n\nPresent: {p}\nAbsent: {ab}\nMarked by: {mb}')
    except Exception: log.exception('attendance save'); await update.message.reply_text('⚠️ Attendance could not be saved.'); return ATT_CONFIRM
    return ConversationHandler.END
async def att_status(update,c):
    s,sh,u,*_=svc(c)
    if not await require(update,u,{'OWNER','AUTHORIZED'}): return
    date=today(s); rows=await sh.records(s.master_spreadsheet_id,s.attendance_tab); emps=await sh.employees(); by={str(r.get('Employee ID','')).strip().upper():r for r in rows if str(r.get('Date','')).strip()==date}; out=[f'📊 TODAY\'S ATTENDANCE\n\n📅 {date}\n']
    for e in emps:
        if str(e.get('Status','')).upper()!='ACTIVE': continue
        eid=str(e.get('Employee ID','')).strip(); r=by.get(eid.upper(),{}); out.append(f"• {eid} - {e.get('Name','')}\n  🌅 {r.get('Morning') or '—'}   ☀️ {r.get('Afternoon') or '—'}")
    await update.message.reply_text('\n'.join(out))

# ---------- progress ----------
async def progress_menu(update,c):
    s,sh,u,*_=svc(c)
    if not await require(update,u,{'OWNER','AUTHORIZED'}): return
    await update.message.reply_text('📈 PROGRESS MONITORING',reply_markup=kb([["📝 Today's Plan"],['📊 Actual Progress'],["📥 Today's Progress Report"],['🔙 Back']]))
async def plan_start(update, c):
    s, sh, u, e, a, p, drive = svc(c)

    if not await require(
        update,
        u,
        {'OWNER', 'AUTHORIZED'}
    ):
        return ConversationHandler.END

    c.user_data['plan'] = {}

    await update.message.reply_text(
        "📝 TODAY'S PLAN\n\n"
        "Is the work Under PO or Not Under PO?",
        reply_markup=kb([
            ['Under PO'],
            ['Not Under PO'],
            ['❌ Cancel'],
        ])
    )

    return PLAN_CLASS


async def plan_class(update, c):
    v = update.message.text.strip()

    if v == '❌ Cancel':
        c.user_data.clear()

        await update.message.reply_text(
            '❌ Plan cancelled.'
        )

        return ConversationHandler.END

    if v not in {
        'Under PO',
        'Not Under PO'
    }:
        await update.message.reply_text(
            'Select Under PO or Not Under PO.'
        )

        return PLAN_CLASS

    c.user_data['plan']['classification'] = v

    # =====================================================
    # NOT UNDER PO
    # No Master Data search
    # =====================================================

    if v == 'Not Under PO':

        c.user_data['plan']['po_ref'] = 'N/A'

        await update.message.reply_text(
            "Select clarification:",
            reply_markup=kb([
                ['PO Amendment Required'],
                ['Labour Supply'],
                ['❌ Cancel'],
            ])
        )

        return PLAN_CLARIFY

    # =====================================================
    # UNDER PO
    # Search Master Data
    # =====================================================

    await update.message.reply_text(
        "🔎 MASTER DATA\n\n"
        "Enter PO Ref, Equipment Tag No., "
        "or Equipment Description.\n\n"
        "Example:\n"
        "1200-T-04\n"
        "or\n"
        "Metallic Tank\n\n"
        "The bot will search the Master Data.",
        reply_markup=kb([
            ['❌ Cancel'],
        ])
    )

    return PLAN_MASTER_SEARCH


async def plan_clarify(update, c):
    v = update.message.text.strip()

    if v == '❌ Cancel':
        c.user_data.clear()

        await update.message.reply_text(
            '❌ Plan cancelled.'
        )

        return ConversationHandler.END

    if v not in {
        'PO Amendment Required',
        'Labour Supply'
    }:
        await update.message.reply_text(
            'Select PO Amendment Required or Labour Supply.'
        )

        return PLAN_CLARIFY

    c.user_data['plan']['clarification'] = v
    c.user_data['plan']['po_ref'] = 'N/A'

    await update.message.reply_text(
        "Enter Job Description.\n\n"
        "Example:\n"
        "Material shifting\n"
        "Identification\n"
        "Positioning\n"
        "Erection"
    )

    return PLAN_JOB


async def plan_master_search(update, c):
    text = update.message.text.strip()

    if text == '❌ Cancel':
        c.user_data.clear()

        await update.message.reply_text(
            '❌ Plan cancelled.'
        )

        return ConversationHandler.END

    s, sh, u, e, a, p, drive = svc(c)

    await update.message.reply_text(
        "🔎 Searching Master Data..."
    )

    try:
        results = await sh.search_master_data(text)

    except Exception:
        log.exception(
            'master data search'
        )

        await update.message.reply_text(
            "⚠️ Unable to search Master Data."
        )

        return PLAN_MASTER_SEARCH

    if not results:
        await update.message.reply_text(
            "❌ No matching Master Data found.\n\n"
            "Try:\n"
            "• PO Ref\n"
            "• Equipment Tag No.\n"
            "• Equipment Description",
            reply_markup=kb([
                ['❌ Cancel'],
            ])
        )

        return PLAN_MASTER_SEARCH

    # Limit Telegram keyboard size
    results = results[:10]

    c.user_data['master_results'] = results

    buttons = []

    for i, row in enumerate(
        results,
        start=1
    ):
        po_ref = str(
            row.get('PO ref', '')
        ).strip()

        equipment_tag = str(
            row.get('Equipment Tag No.', '')
        ).strip()

        description = str(
            row.get('Equipment Description', '')
        ).strip()

        label = (
            f"{i}. {po_ref} | "
            f"{equipment_tag} | "
            f"{description}"
        )

        # Telegram keyboard button limit
        buttons.append([
            label[:64]
        ])

    buttons.append(['🔎 New Search'])
    buttons.append(['❌ Cancel'])

    await update.message.reply_text(
        "📋 MASTER DATA RESULTS\n\n"
        "Select the required equipment:",
        reply_markup=kb(buttons)
    )

    return PLAN_MASTER_SELECT


async def plan_master_select(update, c):
    text = update.message.text.strip()

    if text == '❌ Cancel':
        c.user_data.clear()

        await update.message.reply_text(
            '❌ Plan cancelled.'
        )

        return ConversationHandler.END

    if text == '🔎 New Search':
        await update.message.reply_text(
            "Enter PO Ref, Equipment Tag No., "
            "or Equipment Description."
        )

        return PLAN_MASTER_SEARCH

    results = c.user_data.get(
        'master_results',
        []
    )

    selected = None

    for i, row in enumerate(
        results,
        start=1
    ):
        po_ref = str(
            row.get('PO ref', '')
        ).strip()

        equipment_tag = str(
            row.get('Equipment Tag No.', '')
        ).strip()

        description = str(
            row.get('Equipment Description', '')
        ).strip()

        expected = (
            f"{i}. {po_ref} | "
            f"{equipment_tag} | "
            f"{description}"
        )

        if text == expected[:64]:
            selected = row
            break

    if selected is None:
        await update.message.reply_text(
            "❌ Invalid selection.\n\n"
            "Please select one of the displayed "
            "Master Data results."
        )

        return PLAN_MASTER_SELECT

    po_ref = str(
        selected.get('PO ref', '')
    ).strip()

    c.user_data['plan']['po_ref'] = po_ref

    c.user_data['plan']['equipment_tag'] = str(
        selected.get(
            'Equipment Tag No.',
            ''
        )
    ).strip()

    c.user_data['plan']['equipment_description'] = str(
        selected.get(
            'Equipment Description',
            ''
        )
    ).strip()

    c.user_data.pop(
        'master_results',
        None
    )

    await update.message.reply_text(
        "✅ MASTER DATA SELECTED\n\n"
        f"PO Ref: {po_ref}\n"
        f"Equipment Tag: "
        f"{c.user_data['plan']['equipment_tag']}\n"
        f"Equipment: "
        f"{c.user_data['plan']['equipment_description']}\n\n"
        "Enter Job Description.\n\n"
        "Example:\n"
        "Shifting & Identification\n"
        "Positioning\n"
        "Erection\n"
        "Alignment"
    )

    return PLAN_JOB


async def plan_job(update, c):
    v = update.message.text.strip()

    if v == '❌ Cancel':
        c.user_data.clear()

        await update.message.reply_text(
            '❌ Plan cancelled.'
        )

        return ConversationHandler.END

    if not v:
        await update.message.reply_text(
            'Job Description cannot be empty.'
        )

        return PLAN_JOB

    c.user_data['plan']['job'] = v

    await update.message.reply_text(
        "Enter Allocated Workers.\n\n"
        "Example: 12\n"
        "or\n"
        "Arun, Rahul, Suresh"
    )

    return PLAN_WORKERS


async def plan_workers(update, c):
    v = update.message.text.strip()

    if v == '❌ Cancel':
        c.user_data.clear()

        await update.message.reply_text(
            '❌ Plan cancelled.'
        )

        return ConversationHandler.END

    if not v:
        await update.message.reply_text(
            'Enter worker count or names.'
        )

        return PLAN_WORKERS

    c.user_data['plan']['workers'] = v

    p = c.user_data['plan']

    await update.message.reply_text(
        "📋 PLAN REVIEW\n\n"
        f"PO Ref: {p.get('po_ref', 'N/A')}\n"
        f"Classification: "
        f"{p.get('classification', '')}\n"
        f"Clarification: "
        f"{p.get('clarification') or '—'}\n"
        f"Job: {p.get('job', '')}\n"
        f"Workers: {p.get('workers', '')}\n\n"
        "Save?",
        reply_markup=kb([
            ['✅ Save Plan'],
            ['❌ Cancel'],
        ])
    )

    return PLAN_CONFIRM


async def plan_confirm(update, c):
    s, sh, u, e, a, p, drive = svc(c)

    v = update.message.text.strip()

    if v == '❌ Cancel':
        c.user_data.clear()

        await update.message.reply_text(
            '❌ Plan cancelled.'
        )

        return ConversationHandler.END

    if v != '✅ Save Plan':
        return PLAN_CONFIRM

    user = await user_for(update, u)

    d = c.user_data['plan']

    await update.message.reply_text(
        "⏳ Saving today's plan..."
    )

    try:
        date = today(s)

        plan_time = datetime.now(
            s.tz
        ).strftime("%H:%M:%S")

        # Generate Plan ID
        existing = await sh.records(
            s.master_spreadsheet_id,
            s.daily_plans_tab
        )

        sequence = len(existing) + 1

        plan_id = (
            f"PLAN-{datetime.now(s.tz):%Y%m%d}-"
            f"{sequence:03d}"
        )

        row = [[
            date,
            plan_id,
            d.get('po_ref', 'N/A'),
            d.get('job', ''),
            d.get('classification', ''),
            d.get('clarification', '—'),
            d.get('workers', ''),
            user.get('Name')
                or update.effective_user.first_name,
            plan_time,
            'Planned',
        ]]

        await sh.append_rows(
            s.master_spreadsheet_id,
            s.daily_plans_tab,
            row
        )

        c.user_data.clear()

        await update.message.reply_text(
        "✅ TODAY'S PLAN SAVED\n\n"
        f"Plan ID: {plan_id}\n"
        f"PO Ref: {row[0][2]}\n"
        f"Job: {row[0][3]}\n"
        f"Workers: {row[0][6]}",
        reply_markup=kb([
        ["➕ Add Another Plan"],
        ["📋 Planned Activities"],
        ["🔙 Back"],
    ])
        )

        return ConversationHandler.END

    except Exception:
        log.exception(
            "save today's plan"
        )

        await update.message.reply_text(
            "⚠️ Unable to save today's plan."
        )

        return PLAN_CONFIRM

    return ConversationHandler.END
async def todays_plans(update, c):
    s, sh, u, e, a, p, drive = svc(c)

    if not await require(
        update,
        u,
        {'OWNER', 'AUTHORIZED'}
    ):
        return

    try:
        date = today(s)

        rows = await sh.records(
            s.master_spreadsheet_id,
            s.daily_plans_tab
        )

        plans = [
            row
            for row in rows
            if str(
                row.get("Date", "")
            ).strip() == date
        ]

        if not plans:
            await update.message.reply_text(
                f"📋 TODAY'S PLANS\n\n"
                f"📅 {date}\n\n"
                "No plans found for today."
            )
            return

        out = [
            "📋 TODAY'S PLANS",
            "",
            f"📅 {date}",
            ""
        ]

        for i, row in enumerate(plans, start=1):

            out.append(
                f"{i}. {row.get('Plan ID', '')}\n"
                f"   PO Ref: {row.get('PO Ref', 'N/A')}\n"
                f"   Job: {row.get('Job Description', '')}\n"
                f"   Classification: "
                f"{row.get('Classification', '')}\n"
                f"   Clarification: "
                f"{row.get('Clarification', '—')}\n"
                f"   Workers: "
                f"{row.get('Allocated Workers', '')}\n"
                f"   Planned By: "
                f"{row.get('Planned By', '')}\n"
                f"   Time: "
                f"{row.get('Plan Time', '')}\n"
                f"   Status: "
                f"{row.get('Status', '')}\n"
            )

        await update.message.reply_text(
            "\n".join(out),
            reply_markup=kb([
                ["➕ Add Another Plan"],
                ["🔙 Back"]
            ])
        )

    except Exception:
        log.exception("today's plans")

        await update.message.reply_text(
            "⚠️ Unable to load today's plans."
        )
async def actual_start(update, c):
    s, sh, u, e, a, p, drive = svc(c)

    if not await require(
        update,
        u,
        {'OWNER', 'AUTHORIZED'}
    ):
        return ConversationHandler.END

    user = await user_for(update, u)

    plans = await p.todays_plans(
        today(s),
        user.get('Name', '')
    )
    log.info("ACTUAL PLANS: %r", plans)

    if not plans:
        await update.message.reply_text(
            "⚠️ No Today's Plan found for you today.\n\n"
            "Please use /todayplan first."
        )
        return ConversationHandler.END

    c.user_data['actual'] = {
        'plans': plans,
        'photos': []
    }

    buttons = []

    for row in plans:
        job = str(
            row.get('Job description', '')
        ).strip()

        if job:
            buttons.append([job])

    buttons.append(["❌ Cancel"])

    await update.message.reply_text(
        "📊 ACTUAL PROGRESS\n\n"
        "Select the job:",
        reply_markup=kb(buttons)
    )

    return ACT_JOB


async def actual_job(update, c):

    v = update.message.text.strip()

    if v == '❌ Cancel':
        c.user_data.clear()

        await update.message.reply_text(
            "❌ Actual progress cancelled."
        )

        return ConversationHandler.END

    plans = c.user_data.get(
        'actual',
        {}
    ).get(
        'plans',
        []
    )

    selected_plan = None

    for row in plans:

        job = str(
            row.get('Job description', '')
        ).strip()

        if job == v:
            selected_plan = row
            break

    if selected_plan is None:

        await update.message.reply_text(
            "Please select a job button."
        )

        return ACT_JOB

    c.user_data['actual']['plan'] = selected_plan

    await update.message.reply_text(
        "Select actual status:",
        reply_markup=kb(
            [[x] for x in STATUSES] +
            [["❌ Cancel"]]
        )
    )

    return ACT_STATUS
async def actual_status(update,c):
    v=update.message.text.strip()
    if v=='❌ Cancel': c.user_data.clear(); await update.message.reply_text('❌ Actual progress cancelled.'); return ConversationHandler.END
    if v not in STATUSES: await update.message.reply_text('Select one of the listed statuses.'); return ACT_STATUS
    c.user_data['actual']['status']=v; await update.message.reply_text('Enter Quantity Completed.\nExample: 4 or 12.5'); return ACT_QTY
async def actual_qty(update,c):
    v=update.message.text.strip()
    if v=='❌ Cancel': c.user_data.clear(); await update.message.reply_text('❌ Actual progress cancelled.'); return ConversationHandler.END
    try:
        n=float(v)
        if not math.isfinite(n) or n<0: raise ValueError
    except ValueError: await update.message.reply_text('Enter a valid non-negative number.'); return ACT_QTY
    c.user_data['actual']['qty']=v; await update.message.reply_text('Enter Remarks.'); return ACT_REMARKS
async def actual_remarks(update,c):
    v=update.message.text.strip()
    if v=='❌ Cancel': c.user_data.clear(); await update.message.reply_text('❌ Actual progress cancelled.'); return ConversationHandler.END
    c.user_data['actual']['remarks']=v; await update.message.reply_text('📷 Send up to 2 photos. Send one at a time, then type DONE.\n\nIf no photo is required, type DONE.',reply_markup=ReplyKeyboardRemove()); return ACT_PHOTOS
async def actual_photos(update,c):
    s,sh,u,e,a,p,drive=svc(c); st=c.user_data['actual']
    if update.message.text:
        v=update.message.text.strip().upper()
        if v=='CANCEL': c.user_data.clear(); await update.message.reply_text('❌ Actual progress cancelled.'); return ConversationHandler.END
        if v!='DONE': await update.message.reply_text('Send a photo or type DONE.'); return ACT_PHOTOS
        return await actual_submit(update,c)
    if not update.message.photo: await update.message.reply_text('Send a photo or type DONE.'); return ACT_PHOTOS
    if len(st['photos'])>=2: await update.message.reply_text('Maximum 2 photos reached. Type DONE.'); return ACT_PHOTOS
    photo=update.message.photo[-1]
    if s.photo_storage=='drive':
        f=await c.bot.get_file(photo.file_id); data=bytes(await f.download_as_bytearray()); link=await drive.upload(data,f"progress_{today(s)}_{update.effective_user.id}_{len(st['photos'])+1}.jpg",'image/jpeg'); st['photos'].append(link)
    else: st['photos'].append(f'telegram_file_id:{photo.file_id}')
    await update.message.reply_text(f"📷 Photo {len(st['photos'])}/2 received.{' Type DONE when finished.' if len(st['photos'])==2 else ' Send another photo or type DONE.'}"); return ACT_PHOTOS
async def actual_submit(update, c):
    s, sh, u, e, a, p, drive = svc(c)

    st = c.user_data['actual']
    r = st['plan']

    plan = Plan(
        str(r.get('PO Ref', '')),
        str(r.get('Equipment Tag No.', '')),
        str(r.get('Equipment Description', '')),
        str(r.get('Classification', '')),
        str(r.get('Clarification', '')),
        str(r.get('Job description', '')),
        str(r.get('Allocated Workers', '')),
        str(r.get('Plan ID', ''))
    )

    actual = Actual(
        st['status'],
        st['qty'],
        st['remarks'],
        st['photos']
    )

    planned_by = str(
        r.get('Planned By', '')
    ).strip()

    await update.message.reply_text(
        '⏳ Consolidating master report and routing...'
    )

    try:
        # ---------------------------------------------
        # SAVE ACTUAL PROGRESS
        # ---------------------------------------------
        await p.consolidate_actual(
            today(s),
            planned_by,
            plan,
            actual
        )

        # ---------------------------------------------
        # LOAD REMAINING PLANNED ACTIVITIES
        # ---------------------------------------------
        log.info(
            "NEXT PLAN CHECK: date=%r planned_by=%r",
            today(s),
            planned_by
        )

        plans = await p.todays_plans(
            today(s),
            planned_by
        )

        log.info(
            "REMAINING ACTUAL PLANS: %r",
            plans
        )

        # ---------------------------------------------
        # NO MORE PLANS
        # ---------------------------------------------
        if not plans:
            c.user_data.clear()

            await update.message.reply_text(
                '✅ PROGRESS REPORT SUBMITTED\n\n'
                'No more planned activities remain for today.',
                reply_markup=kb([
                    ['🔙 Back']
                ])
            )

            return ConversationHandler.END

        # ---------------------------------------------
        # STORE REMAINING PLANS
        # ---------------------------------------------
        c.user_data['actual'] = {
            'plans': plans,
            'photos': []
        }

        # ---------------------------------------------
        # BUILD NEXT ACTIVITY BUTTONS
        # ---------------------------------------------
        buttons = []

        for row in plans:
            job = str(
                row.get('Job description', '')
            ).strip()

            log.info(
                "NEXT ACTIVITY JOB: %r",
                job
            )

            if job:
                buttons.append([job])

        buttons.append(['❌ Cancel'])

        log.info(
            "NEXT ACTIVITY BUTTONS: %r",
            buttons
        )

        # ---------------------------------------------
        # SHOW NEXT ACTIVITY
        # ---------------------------------------------
        await update.message.reply_text(
            '✅ PROGRESS REPORT SUBMITTED\n\n'
            'Select the next planned activity:',
            reply_markup=kb(buttons)
        )

        return ACT_JOB

    except Exception:
        log.exception(
            'actual progress'
        )

        await update.message.reply_text(
            '⚠️ Progress report could not be saved.'
        )

        return ACT_PHOTOS
async def progress_report(update,c):
    s,sh,u,*_=svc(c)
    if not await require(update,u,{'OWNER','AUTHORIZED'}): return
    rows=await sh.records(s.master_spreadsheet_id,s.progress_tab); date=today(s); rows=[r for r in rows if str(r.get('Date','')).strip()==date]
    if not rows: await update.message.reply_text(f'No progress records for {date}.'); return
    out=[f"📈 TODAY'S PROGRESS REPORT\n\n📅 {date}\n"]
    for r in rows[-20:]: out.append(f"• {r.get('Job Description','')}\n  Category: {r.get('Classification','')}\n  Status: {r.get('Actual Status') or 'Plan only'}\n  Qty: {r.get('Quantity Completed') or '—'}\n  Remarks: {r.get('Remarks') or '—'}\n")
    await update.message.reply_text('\n'.join(out))
async def reports(update,c):
    s,sh,u,*_=svc(c)
    if not await require(update,u,{'OWNER'}): return
    date=today(s); ar=await sh.records(s.master_spreadsheet_id,s.attendance_tab); pr=await sh.records(s.master_spreadsheet_id,s.progress_tab); await update.message.reply_text(f"📥 TODAY'S REPORT\n\n📅 {date}\nAttendance records: {sum(str(x.get('Date','')).strip()==date for x in ar)}\nProgress records: {sum(str(x.get('Date','')).strip()==date for x in pr)}")

async def cancel(update,c): c.user_data.clear(); await update.message.reply_text('❌ Operation cancelled.'); return ConversationHandler.END
async def error_handler(update,c): log.exception('Unhandled Telegram exception',exc_info=c.error)

def conv(entry, handlers):
    return ConversationHandler(
        entry_points=entry,
        states=handlers,
        fallbacks=[CommandHandler("cancel", cancel)],
    )

def build(settings: Settings):
    sh = SheetsRepository(settings)
    u = UserService(settings, sh)
    e = EmployeeService(settings, sh)
    a = AttendanceService(settings, sh)
    p = ProgressService(settings, sh)
    drive = DriveUploader(settings.drive_folder_id)

    app = (
        Application.builder()
        .token(settings.telegram_token)
        .build()
    )

    app.bot_data.update(
        settings=settings,
        sheets=sh,
        users=u,
        employees=e,
        attendance=a,
        progress=p,
        drive=drive,
    )

    # =====================================================
    # BASIC COMMANDS
    # =====================================================

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("myid", myid)
    )

    # =====================================================
    # MAIN MENU
    # =====================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^👥 Employees$"),
            employee_menu,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^👤 Authorized Person$"),
            user_menu,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^📊 Attendance$"),
            attendance_menu,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^📈 Progress Monitoring$"),
            progress_menu,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^📥 Reports$"),
            reports,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^📊 Today's Status$"),
            att_status,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^📥 Today's Progress Report$"),
            progress_report,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^🔙 Back$"),
            back,
        )
    )


    # =====================================================
    # EMPLOYEE LIST
    # THIS WAS MISSING
    # =====================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^📋 Employee List$"),
            employee_list,
        )
    )

    # =====================================================
    # ADD EMPLOYEE
    # =====================================================

    app.add_handler(
        conv(
            [
                MessageHandler(
                    filters.Regex(r"^➕ Add Employee$"),
                    add_start,
                )
            ],
            {
                ADD_ID: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        add_id,
                    )
                ],
                ADD_NAME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        add_name,
                    )
                ],
                ADD_DESIG: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        add_desig,
                    )
                ],
                ADD_DATE: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        add_date,
                    )
                ],
                ADD_CONFIRM: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        add_confirm,
                    )
                ],
            },
        )
    )

    # =====================================================
    # EDIT EMPLOYEE
    # =====================================================

    app.add_handler(
        conv(
            [
                MessageHandler(
                    filters.Regex(r'^✏️ Edit Employee$'),
                    edit_start
)
            ],
            {
                EDIT_ID: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        edit_id,
                    )
                ],
                EDIT_NAME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        edit_name,
                    )
                ],
                EDIT_DESIG: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        edit_desig,
                    )
                ],
                EDIT_DATE: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        edit_date,
                    )
                ],
                EDIT_CONFIRM: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        edit_confirm,
                    )
                ],
            },
        )
    )

    # =====================================================
    # DEACTIVATE EMPLOYEE
    # =====================================================

    app.add_handler(
        conv(
            [
                MessageHandler(
                    filters.Regex(r'^🚫 Deactivate Employee$'),
                    deact_start
)
            ],
            {
                DEACT_ID: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        deact_id,
                    )
                ],
                DEACT_CONFIRM: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        deact_confirm,
                    )
                ],
            },
        )
    )

    # =====================================================
    # AUTHORIZED PERSON / OWNER
    # =====================================================

    app.add_handler(
        conv(
            [
                MessageHandler(
                    filters.Regex(
                        r"^➕ Add Authorized Person$|^➕ Add Owner$"
                    ),
                    user_start,
                )
            ],
            {
                USER_ID: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        user_id,
                    )
                ],
                USER_NAME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        user_name,
                    )
                ],
                USER_CONFIRM: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        user_confirm,
                    )
                ],
            },
        )
    )

    # =====================================================
    # ATTENDANCE
    # =====================================================

    app.add_handler(
        conv(
            [
                MessageHandler(
                    filters.Regex(
                        r"^🌅 Morning Attendance$|^☀️ Afternoon Attendance$"
                    ),
                    att_start,
                )
            ],
            {
                ATT_ACTION: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        att_action,
                    )
                ],
                ATT_CONFIRM: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        att_confirm,
                    )
                ],
            },
        )
    )
    # =====================================================
# TODAY'S PLAN
# =====================================================

    app.add_handler(
            conv(
        [
                MessageHandler(
                     filters.Regex(
                    r"^📝 Today's Plan$|^➕ Add Another Plan$"
                ),
                    plan_start,
            ),
        ],
        {
            PLAN_CLASS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    plan_class,
                )
            ],

            PLAN_CLARIFY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    plan_clarify,
                )
            ],

            PLAN_MASTER_SEARCH: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    plan_master_search,
                )
            ],

            PLAN_MASTER_SELECT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    plan_master_select,
                )
            ],

            PLAN_JOB: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    plan_job,
                )
            ],

            PLAN_WORKERS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    plan_workers,
                )
            ],

            PLAN_CONFIRM: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    plan_confirm,
                )
            ],
        },
    )
)

# =====================================================
# PLANNED ACTIVITIES
# =====================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^📋 Planned Activities$"),
            todays_plans,
    )
)
# =====================================================
# ACTUAL PROGRESS
# =====================================================

    app.add_handler(
            conv(
        [
            MessageHandler(
                filters.Regex(r"^📊 Actual Progress$"),
                actual_start,
            ),
            CommandHandler(
                "actualprogress",
                actual_start,
            ),
        ],
        {
            ACT_JOB: [
                MessageHandler(
                    filters.Regex(r"^❌ Cancel$"),
                    actual_job,
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    actual_job,
                ),
            ],

            ACT_STATUS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    actual_status,
                )
            ],

            ACT_QTY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    actual_qty,
                )
            ],

            ACT_REMARKS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    actual_remarks,
                )
            ],

            ACT_PHOTOS: [
                MessageHandler(
                    filters.PHOTO,
                    actual_photos,
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    actual_photos,
                ),
            ],
        },
    )
)
   

    # =====================================================
    # ERROR HANDLER
    # =====================================================

    app.add_error_handler(error_handler)

    return app

def main():
    settings=load_settings(); log.info('GSB Integrated Bot starting'); build(settings).run_polling(drop_pending_updates=True)

if __name__=='__main__': main()
