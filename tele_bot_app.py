from collections import defaultdict
from datetime import datetime

import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Setup Google Sheets access
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('cred.json', scope)
client = gspread.authorize(creds)

# Global variables
is_superman = False
is_permitted = False
is_admin = False
input_id1 = None
user_admin_array = ['7228364', '7338109','5263826']
exclude = ['5914224']

# Connect to Google Sheets
signature_sheet_url = "https://docs.google.com/spreadsheets/d/1LbivWx0Ajc0YZQUEr-E0UV-WKOeTBmOPwW5oKl2tMl8"
present_sheet_url = "https://docs.google.com/spreadsheets/d/1j6P11N6vWy_SMvYgsaN5uqjrzWnslWuk6FO2ftxxX8g"
logging_sheet_url = "https://docs.google.com/spreadsheets/d/1QmYRDIsobpxtYZxR6jWTGZPcZIW5GDRS8RfbjQGHP6M/edit?gid=0#gid=0"
phone_sheet_url = "https://docs.google.com/spreadsheets/d/18EHXmBQx0eaBuQj_h6s-R42JhynsGlHVGZrPU37So6s"

tele_token = "7656861568:AAFeAWvsPeJFXaDmYk0bnyQsjPKWW8AqQAs"

# Open the Google Sheets
present_sheet = client.open_by_url(present_sheet_url).worksheet('א')
signatures_spreadsheet = client.open_by_url(signature_sheet_url)
logging_spreadsheet = client.open_by_url(logging_sheet_url)
phone_spreadsheet = client.open_by_url(phone_sheet_url).sheet1

data = present_sheet.get_all_records()
df = pd.DataFrame(data)

# State tracking
user_states = {}

OPTIONS = ["צוות 1", "צוות 2", "צוות 3", "מפלג", "בונקר", "5.56 רגיל", "5.56 ירוק"]


# ──────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = 'awaiting_id'
    print("✅ Bot is running and waiting for messages...")
    await update.message.reply_text("ברוך הבא! אנא הזן את המספר האישי שלך:")
    global is_superman
    is_superman = False


# ──────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text.strip()
    state = user_states.get(user_id)
    print('state: ', state)

    if state == 'awaiting_id':
        await process_personal_id(update, context, message_text)
    elif state == 'awaiting_menu':
        await handle_menu_choice(update, context, message_text)
    elif state == 'awaiting_name':
        await get_phone_number(update, context, message_text)
        user_states[user_id] = 'awaiting_menu'
        return
    elif state == 'awaiting_report':
        await handle_report_manu_choice(update, context, message_text)
        user_states[user_id] = 'awaiting_report'
        return
    else:
        await update.message.reply_text("שלח /start כדי להתחיל מחדש.")


# ──────────────────────────────────────────────
async def process_personal_id(update, context, input_id):
    user_id = update.effective_user.id
    row = df[df['מספר אישי'].astype(str) == input_id]
    if input_id in exclude:
        await update.message.reply_text("❌ אין לך הרשאה להשתמש בבוט זה.")
        print(
            f"[{datetime.now()}] User {user_id} ({update.effective_user.full_name}) attempted to use the bot but is excluded.")
        return

    if row.empty:
        await update.message.reply_text(f"⚠️ לא נמצאה שורה עבור מספר אישי {input_id}")
        print(
            f"[{datetime.now()}] User {user_id} ({update.effective_user.full_name}) queried ID {input_id} — Result: Not Found")
        return

    context.user_data['personal_id'] = input_id
    context.user_data['row_data'] = row.iloc[0]
    context.user_data['team'] = await get_user_team(input_id)
    user_states[user_id] = 'awaiting_menu'
    global input_id1
    input_id1 = input_id
    # await update_user_activity(context)
    await is_user_admin(update, context)
    await is_user_permitted(update, context)
    await is_user_superman(update, context)
    await show_main_menu(update)


# ────────────user-setters─────────────────────────

async def is_user_superman(update, context):
    # Define sheet groups
    team_sheets = "מפלג"
    matched_rows = df[df['מספר אישי'].astype(str) == input_id1]
    if not matched_rows.empty:
        item_type = str(matched_rows.get('מחלקה', '')).strip()
        if team_sheets in item_type:
            await update.message.reply_text("🦸 אתה סופרמן, יש לך גישה לכל האפשרויות.")
            global is_superman
            is_superman = True


async def is_user_admin(update, context):
    if input_id1 in user_admin_array:
        global is_admin
        is_admin = True


async def is_user_permitted(update, context):
    sheet = signatures_spreadsheet.worksheet("data")
    all_rows = sheet.get_all_values()
    for row in all_rows[1:]:
        if input_id1 == row[1]:
            global is_permitted
            is_permitted = True


# ────────────data-getters───────────────────────

async def get_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE, name):
    user_id = update.effective_user.id
    user_states[user_id] = 'awaiting_menu'
    data1 = phone_spreadsheet.get_all_records()
    df1 = pd.DataFrame(data1)
    matched_rows = df1[df1['שם פרטי'].astype(str).str.contains(name, na=False)]
    if matched_rows.empty:
        matched_rows = df1[df1['שם משפחה'].astype(str).str.contains(name, na=False)]
    if not matched_rows.empty:
        items = []
        for _, row_data in matched_rows.iterrows():
            first_name = str(row_data.get('שם פרטי', '')).strip()
            last_name = str(row_data.get('שם משפחה', '')).strip()
            phone_number =str(row_data.get('טלפון נייד', '')).strip()
            if first_name or last_name:
                row_desc = []
                res = f"מספר הטלפון של {first_name} {last_name} הוא {phone_number}"
                row_desc.append(res)

                items.append(" • " + ", ".join(row_desc))
        if items:
            response = "☎️ *מספר טלפון:* \n" + "\n".join(items)
            await update.message.reply_text(response, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"⚠️ לא נמצאו רשומות עבור השם {name}")
    return


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = 'awaiting_name'
    await update.message.reply_text("הכנס שם לחיפוש")
    return


async def get_user_team(input_id):
    matched_rows = df[df['מספר אישי'].astype(str) == input_id]
    if not matched_rows.empty:
        team = str(matched_rows.iloc[0].get('מחלקה', '')).strip()
        return team
    return None


async def get_ammo_summary_report(update, context):
    sheet = signatures_spreadsheet.worksheet('ammo-sum')
    rows = sheet.get_all_values()[1:]
    item_idx = sheet.get_all_values()[0].index("סוג תחמושת")
    totals = defaultdict(int)

    team_index = sheet.get_all_values()[0].index('סהכ') if is_admin else sheet.get_all_values()[0].index(
        context.user_data['team'])

    for row in rows:
        item = row[item_idx].strip()
        amount = row[team_index].strip()
        if item and amount != '0':
            totals[item] += int(amount)
    res = "\n".join(f"{item}: {total}" for item, total in totals.items())
    return res


async def get_ammo_distribution_report(update, context):
    sheet = signatures_spreadsheet.worksheet('ammo-sum')
    data1 = sheet.get_all_values()
    df1 = pd.DataFrame(data1[1:], columns=data1[0])

    # Convert numeric columns (excluding the first one which is the item name)
    for col in df1.columns[1:]:
        df1[col] = pd.to_numeric(df1[col], errors='coerce').fillna(0).astype(int)
    # Reshape to long format (excluding the last column 'סהכ')
    company_columns = df1.columns[1:-1]
    long_df = df1.melt(id_vars=[df1.columns[0]], value_vars=company_columns,
                       var_name='פלוגה', value_name='כמות')

    # Group by company and build message
    series = long_df.groupby('פלוגה').apply(
        lambda group: "\n" + "\n".join(
            f"{item}: {amount}"
            for item, amount in zip(group.drop(columns=['פלוגה'])[df1.columns[0]], group['כמות'])
            if amount > 0
        )
    )
    message_lines = []
    for unit, items in series.items():
        # Insert newline and bullets between items
        item_lines = items.replace(":", ": ").replace("item", "\n  - item")  # adjust if needed
        formatted = f"📌 {unit}\n {item_lines.strip()}"
        message_lines.append(formatted)
    return "\n\n".join(message_lines)


async def get_weapon_distribution_report(update, context):
    sheet = signatures_spreadsheet.worksheet('sum')
    data1 = sheet.get_all_values()
    data1 = [row[:7] for row in data1]
    # Create DataFrame with headers from the first row
    df1 = pd.DataFrame(data1[1:], columns=data1[0])
    # Convert numeric columns (excluding the first one which is the item name)
    for col in df1.columns[1:]:
        df1[col] = pd.to_numeric(df1[col], errors='coerce').fillna(0).astype(int)
    # Reshape to long format (excluding the last column 'סהכ')
    company_columns = df1.columns[1:-1]
    long_df = df1.melt(id_vars=[df1.columns[0]], value_vars=company_columns,
                       var_name='פלוגה', value_name='כמות')

    # Group by company and build message
    series = long_df.groupby('פלוגה').apply(
        lambda group: "\n" + "\n".join(
            f"{item}: {amount}"
            for item, amount in zip(group.drop(columns=['פלוגה'])[df1.columns[0]], group['כמות'])
            if amount > 0
        )
    )
    message_lines = []
    for unit, items in series.items():
        # Insert newline and bullets between items
        item_lines = items.replace(":", ": ").replace("item", "\n  - item")  # adjust if needed
        formatted = f"📌 {unit}\n {item_lines.strip()}"
        message_lines.append(formatted)
    return "\n\n".join(message_lines)


async def get_ammo_summary_report_bunker(update, context):
    sheet = signatures_spreadsheet.worksheet('ammo-sum')
    rows = sheet.get_all_values()[1:]
    item_idx = sheet.get_all_values()[0].index("סוג תחמושת")
    totals = defaultdict(int)

    team_index = sheet.get_all_values()[0].index('בונקר')

    for row in rows:
        item = row[item_idx].strip()
        amount = row[team_index].strip()
        if item and amount != '0':
            totals[item] += int(amount)
    return "\n".join(f"{item}: {total}" for item, total in totals.items())


async def get_guns_summary_report_bunker(update, context):
    sheet = signatures_spreadsheet.worksheet('sum')
    rows = sheet.get_all_values()[1:]
    item_idx = sheet.get_all_values()[0].index("סוג נשק")
    totals = defaultdict(int)

    team_index = sheet.get_all_values()[0].index('בונקר-')

    for row in rows:
        item = row[item_idx].strip()
        amount = row[team_index].strip()
        if item and amount != '0':
            totals[item] += int(amount)
    return "\n".join(f"{item}: {total}" for item, total in totals.items())


async def get_weapons_summary_report_bunker(update, context):
    sheet = signatures_spreadsheet.worksheet('sum')
    rows = sheet.get_all_values()[1:]
    item_idx = sheet.get_all_values()[0].index("סוג צלמ")
    totals = defaultdict(int)

    team_index = sheet.get_all_values()[0].index('בונקר')

    for row in rows:
        item = row[item_idx].strip()
        amount = row[team_index].strip()
        if item and amount != '0':
            totals[item] += int(amount)
    return "\n".join(f"{item}: {total}" for item, total in totals.items())


async def get_weapon_report(update, context):
    sheet = signatures_spreadsheet.worksheet('sum')
    rows = sheet.get_all_values()[1:]
    item_idx = 0
    totals = defaultdict(int)

    team_index = sheet.get_all_values()[0].index('סהכ') if is_admin else sheet.get_all_values()[0].index(
        context.user_data['team'])

    for row in rows:
        item = row[item_idx].strip()
        amount = row[team_index].strip()
        if item and amount != '0':
            totals[item] += int(amount)
    res = "\n".join(f"{item}: {total}" for item, total in totals.items())
    return res


async def get_logistic_report(update, context):
    sheet = signatures_spreadsheet.worksheet('לוגיסטיקה')
    rows = sheet.get_all_values()[1:]
    item_idx = sheet.get_all_values()[0].index("סוג פריט")
    totals = defaultdict(int)
    team_index = sheet.get_all_values()[0].index('סהכ')

    for row in rows:
        item = row[item_idx].strip()
        amount = row[team_index].strip()
        if item and amount != '0':
            totals[item] += int(amount)
    res = "\n".join(f"{item}: {total}" for item, total in totals.items())
    return res


async def get_guns_report(update, context):
    sheet = signatures_spreadsheet.worksheet('sum')
    rows = sheet.get_all_values()[1:]
    item_idx = sheet.get_all_values()[0].index('סוג נשק')
    totals = defaultdict(int)

    team_index = (sheet.get_all_values()[0].index('סהכ') if not is_admin else sheet.get_all_values()[0].index(
        context.user_data['team'])) + item_idx

    for row in rows:
        item = row[item_idx].strip()
        amount = row[team_index].strip()
        if item and amount != '0':
            totals[item] += int(amount)
    res = "\n".join(f"{item}: {total}" for item, total in totals.items())
    return res


# ──────────menus───────────────────────

async def show_main_menu(update):
    if is_admin:
        await update.message.reply_text(
            "📋 *תפריט ראשי:*\n"
            "1️⃣ נוכחות\n"
            "2️⃣ חתימות\n"
            "3️⃣ חפש מספר טלפון\n"
            "4️⃣ תחמושת אישית\n"
            "5️⃣ דוחות\n"
            "0️⃣ חזרה לתפריט זה בכל שלב\n\n"
            "הקלד את מספר האפשרות הרצויה:",
            parse_mode='Markdown'
        )
    elif is_superman:
        await update.message.reply_text(
            "📋 *תפריט ראשי (סופרמן):*\n"
            "1️⃣ נוכחות\n"
            "2️⃣ חתימות\n"
            "3️⃣ חפש מספר טלפון\n"
            "4️⃣ תחמושת אישית\n"
            "0️⃣ חזרה לתפריט זה בכל שלב\n\n"
            "הקלד את מספר האפשרות הרצויה:",
            parse_mode='Markdown'
        )
    elif is_permitted:
        await update.message.reply_text(
            "📋 *תפריט ראשי(מורשים):*\n"
            "1️⃣ נוכחות\n"
            "2️⃣ חתימות\n"
            "3️⃣ חפש מספר טלפון\n"
            "4️⃣ דוחות\n"
            "0️⃣ חזרה לתפריט זה בכל שלב\n\n"
            "הקלד את מספר האפשרות הרצויה:",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "📋 *תפריט ראשי:*\n"
            "1️⃣ נוכחות\n"
            "2️⃣ חתימות\n"
            "3️⃣ חפש מספר טלפון\n"
            "0️⃣ חזרה לתפריט זה בכל שלב\n\n"
            "הקלד את מספר האפשרות הרצויה:",
            parse_mode='Markdown'
        )


async def show_report_manu(update):
    if is_admin:
        await update.message.reply_text(
            "📋 *תפריט ,דוחות ראשי:*\n"
            "1️⃣ הצג דוח תחמושת\n"
            "2️⃣ הצג דוח צלמ\n"
            "3️⃣ הצג דוח נשק\n"
            "4️⃣ הצג דוח תחמושת בבונקר\n"
            "5️⃣ הצג דוח צלמ ונשק בבונקר\n"
            "6️⃣ הצג דוח לוגיסטיקה\n"
            "0️⃣ חזרה לתפריט זה בכל שלב\n\n"
            "הקלד את מספר האפשרות הרצויה:",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "📋 *תפריט ,דוחות ראשי:*\n"
            "1️⃣ הצג דוח תחמושת\n"
            "2️⃣ הצג דוח צלמ\n"
            "0️⃣ חזרה לתפריט זה בכל שלב\n\n"
            "הקלד את מספר האפשרות הרצויה:",
            parse_mode='Markdown'
        )


async def show_report_response(context, update, response):
    msg = 'דוח תחמושת מסכם' if is_admin else f"דוח תחמושת מסכם עבור {context.user_data['team']}"
    response = response if response != '' else "אין תחמושת ברשותך"
    await update.message.reply_text(
        f"📋 *{msg}:*\n\n"
        f"{response}\n\n"
        f"0️⃣ חזרה לתפריט הראשי\n\n",
        parse_mode='Markdown'
    )


async def show_summary_report_response(context, update, response, response2=None):
    msg = 'דוח תחמושת מרכז'
    await update.message.reply_text(
        f"📋 *{msg}:*\n\n"
        f"*סיכום: *\n\n"
        f"{response}\n\n"
        f"התפלגות לפי צוותים\n\n"
        f"{response2}\n\n"
        f"0️⃣ חזרה לתפריט הראשי\n\n",
        parse_mode='Markdown'
    )


async def show_weapon_summary_report_response(context, update, response, response2):
    msg = 'דוח צלמ מרכז'
    await update.message.reply_text(
        f"📋 *{msg}:*\n\n"
        f"*סיכום: *\n\n"
        f"{response}\n\n"
        f"התפלגות לפי צוותים\n\n"
        f"{response2}\n\n"
        f"0️⃣ חזרה לתפריט הראשי\n\n",
        parse_mode='Markdown'
    )


async def show_weapon_report_response(context, update, response):
    msg = 'דוח צלמ מסכם' if is_admin else f"דוח צלמ מסכם עבור {context.user_data['team']}"
    response = response if response != '' else "אין צלמ ברשותך"
    await update.message.reply_text(
        f"📋 *{msg}:*\n\n"
        f"{response}\n\n"
        f"0️⃣ חזרה לתפריט הראשי\n\n",
        parse_mode='Markdown'
    )


async def show_guns_report_response(context, update, response):
    msg = 'דוח נשק מסכם' if is_admin else f"דוח נשק מסכם עבור {context.user_data['team']}"
    response = response if response != '' else "אין צלמ ברשותך"
    await update.message.reply_text(
        f"📋 *{msg}:*\n\n"
        f"{response}\n\n"
        f"0️⃣ חזרה לתפריט הראשי\n\n",
        parse_mode='Markdown'
    )


async def show_ammo_bunker_report_response(context, update, response):
    msg = 'דוח תחמושת מסכם לבונקר'
    await update.message.reply_text(
        f"📋 *{msg}:*\n\n"
        f"{response}\n\n"
        f"0️⃣ חזרה לתפריט הראשי\n\n",
        parse_mode='Markdown'
    )


async def show_bunker_report_response(context, update, response1, response2):
    msg = 'דוח מסכם לבונקר'
    await update.message.reply_text(
        f"📋 *{msg}:*\n\n"
        f" *נשק:*""\n\n"
        f"{response1}\n\n"
        f" *צלמ:*""\n\n"
        f"{response2}\n\n"
        f"0️⃣ חזרה לתפריט הראשי\n\n",
        parse_mode='Markdown'
    )


async def show_guns_bunker_report_response(context, update, response):
    msg = 'דוח נשק וצלמ מסכם לבונקר'
    await update.message.reply_text(
        f"📋 *{msg}:*\n\n"
        f"{response}\n\n"
        f"0️⃣ חזרה לתפריט הראשי\n\n",
        parse_mode='Markdown'
    )


async def show_logistic_report_response(context, update, response, response2):
    msg = 'דוח לוגיסטי מסכם'
    await update.message.reply_text(
        f"📋 *{msg}:*\n\n"
        f"{response}\n\n"
        f"0️⃣ חזרה לתפריט הראשי\n\n",
        parse_mode='Markdown'
    )


# ──────────menu-handlers───────────────────────
async def handle_menu_choice(update, context, choice):
    user_id = update.effective_user.id
    if choice == '0':
        await show_main_menu(update)
        return

    elif choice == '1':
        await handle_attendance(update, context)
        return

    elif choice == '2':
        await update.message.reply_text("טוען, נא להמתין...")
        await handle_signatures(update, context)
        return

    elif choice == '3':
        await get_name(update, context)
        return

    elif choice == '4' and is_superman:
        await handle_superman_ammo(update, context)
        return

    elif choice == '4' and is_permitted:
        user_states[user_id] = 'awaiting_report'
        await show_report_manu(update)
        return
    elif choice == '5' and is_admin:
        user_states[user_id] = 'awaiting_report'
        await show_report_manu(update)
        return

    else:
        await update.message.reply_text("אפשרות לא מוכרת. אנא הקלד 1,2,3  או 0 לחזרה לתפריט.") if not is_superman else \
            await update.message.reply_text("אפשרות לא מוכרת. אנא הקלד 1,2,3,4  או 0 לחזרה לתפריט.")
        return


async def handle_report_manu_choice(update, context, choice):
    user_id = update.effective_user.id
    if choice == '0':
        user_states[input_id1] = 'awaiting_manu'
        await show_main_menu(update)
        return
    elif choice == '1' and is_admin:
        user_states[user_id] = 'awaiting_report'
        res = await get_ammo_summary_report(update, context)
        res2 = await get_ammo_distribution_report(update, context)
        await show_summary_report_response(context, update, res, res2)
        return
    elif choice == '1' and not is_admin:
        user_states[user_id] = 'awaiting_report'
        res = await get_ammo_summary_report(update, context)
        await show_report_response(context, update, res)
        return
    elif choice == '2' and is_admin:
        user_states[user_id] = 'awaiting_report'
        res = await get_weapon_report(update, context)
        res2 = await get_weapon_distribution_report(update, context)
        await show_weapon_summary_report_response(context, update, res, res2)
        return
    elif choice == '2':
        user_states[user_id] = 'awaiting_report'
        res = await get_weapon_report(update, context)
        await show_weapon_report_response(context, update, res)
        return
    elif choice == '3' and is_admin:
        user_states[user_id] = 'awaiting_report'
        res = await get_guns_report(update, context)
        await show_guns_report_response(context, update, res)
        return
    elif choice == '4' and is_admin:
        user_states[user_id] = 'awaiting_report'
        res = await get_ammo_summary_report_bunker(update, context)
        await show_ammo_bunker_report_response(context, update, res)
        return
    elif choice == '5' and is_admin:
        user_states[user_id] = 'awaiting_report'
        res = await get_guns_summary_report_bunker(update, context)
        res2 = await get_weapons_summary_report_bunker(update, context)
        await show_bunker_report_response(context, update, res, res2)
        return
    elif choice == '6' and is_admin:
        user_states[user_id] = 'awaiting_report'
        res = await get_logistic_report(update, context)
        res2 = ''
        await show_logistic_report_response(context, update, res, res2)
        return
    else:
        user_states[input_id1] = 'awaiting_manu'
        await update.message.reply_text("אפשרות לא מוכרת. אנא הקלד 1,2 או 0 לחזרה לתפריט.")
        return


# ──────────handlers──────────────────────────
async def handle_attendance(update, context):
    input_id = context.user_data.get('personal_id')
    row_data = context.user_data.get('row_data')

    statuses_present = {"נוכח", "יצא היום", "חזר היום"}
    status_holiday = "חופש"

    full_name = f"{row_data.get('שם פרטי', '')} {row_data.get('שם משפחה', '')}".strip()
    attendance_entries = {
        col: val for col, val in row_data.items()
        if col not in ['מספר אישי', 'שם פרטי', 'שם משפחה']
    }

    attendance_count = sum(1 for v in attendance_entries.values() if v in statuses_present)
    holiday_count = sum(1 for v in attendance_entries.values() if v == status_holiday)

    try:
        first_date = sorted([
            datetime.strptime(date_str, "%d/%m/%Y")
            for date_str, val in attendance_entries.items()
            if val in statuses_present
        ])[0].strftime("%d/%m/%Y")
    except Exception:
        first_date = "לא ידוע"

    today = datetime.now().strftime("%d/%m/%Y")
    today_status = row_data.get(today, "אין סטטוס להיום")

    response = (
        f"👤 שם: *{full_name}*\n"
        f"ו🆔 מספר אישי: *{input_id}*\n"
        f"📅 תאריך התייצבות: *{first_date}*\n"
        f"✅ נוכח ימים (כולל יצא/חזר היום): *{attendance_count}*\n"
        f"🌴 ימי חופש: *{holiday_count}*\n"
        f"🎯 סה״כ ימ״מים: *{holiday_count + attendance_count}*\n"
        f"📌 סטטוס להיום ({today}): *{today_status}*"
    )

    await update.message.reply_text(response, parse_mode='Markdown')
    print(
        f"[{datetime.now()}] User  ({update.effective_user.full_name}) with personal ID {input_id} — Result: Success")


async def handle_superman_ammo(update, context):
    ammo_sheet = 'תחמושת מפלג'
    sheet = signatures_spreadsheet.worksheet(ammo_sheet)
    df = pd.DataFrame(sheet.get_all_records())
    matched_rows = df[df['מספר אישי'].astype(str) == input_id1]
    if matched_rows.empty:
        await update.message.reply_text(f"⚠️ לא נמצאו רשומות תחמושת עבור מספר אישי {input_id1}")
        return
    else:
        items = []
        for _, row_data in matched_rows.iterrows():
            total_items = str(row_data.get('סהכ', '')).strip()
            item_id = str(row_data.get('מס', '')).strip()
            if total_items or item_id:
                row_desc = []
                if total_items:
                    if total_items == '1':
                        row_desc.append("ברשותך רימון אחד")
                    else:
                        row_desc.append(f"ברשותך  — {total_items}רימונים ")
                if item_id:
                    if total_items == '1':
                        row_desc.append(f"מספר — {item_id}")
                    else:
                        row_desc.append(f"מספר — {item_id}, {item_id} א")
                items.append(" • " + ", ".join(row_desc))

        if items:
            response = "📦 *תחמושת:* \n" + "\n".join(items)
            await update.message.reply_text(response, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"✍️ לא נמצאו נתונים עבור מספר אישי {input_id1}")


async def handle_signatures(update, context):
    user_id = update.effective_user.id
    input_id = context.user_data.get('personal_id')
    full_name = None

    # Define sheet groups
    team_sheets = ["צוות 1", "צוות 2", "צוות 3", "קשר", "מפלג", "לוגיסטיקה"]
    weapon_sheet = "נשק אישי"

    grouped_items = {}

    # Process team sheets (סוג + מסד)
    for sheet_name in team_sheets:
        try:
            sheet = signatures_spreadsheet.worksheet(sheet_name)
            df = pd.DataFrame(sheet.get_all_records())
            matched_rows = df[df['מספר אישי'].astype(str) == input_id]

            if not matched_rows.empty:
                items = []
                for _, row_data in matched_rows.iterrows():
                    if full_name is None:
                        full_name = str(matched_rows.iloc[0].get('חייל', '')).strip()
                    item_type = str(row_data.get('סוג', '')).strip()
                    item_id = str(row_data.get('מסד', '')).strip()
                    if item_type or item_id:
                        row_desc = []
                        if item_type:
                            row_desc.append(f"סוג — {item_type}")
                        if item_id:
                            row_desc.append(f"מסד — {item_id}")
                        items.append(" • " + ", ".join(row_desc))

                if items:
                    grouped_items[sheet_name] = items

        except Exception as e:
            print(f"[{datetime.now()}] Error in sheet '{sheet_name}': {e}")

    # Process נשק אישי (סוג נשק + מספר נשק)
    try:
        sheet = signatures_spreadsheet.worksheet(weapon_sheet)
        df = pd.DataFrame(sheet.get_all_records())
        matched_rows = df[df['מספר אישי'].astype(str) == input_id]

        if not matched_rows.empty:
            items = []
            for _, row_data in matched_rows.iterrows():
                if full_name is None:
                    full_name = str(matched_rows.iloc[0].get('חייל', '')).strip()
                weapon_type = str(row_data.get('סוג נשק', '')).strip()
                weapon_id = str(row_data.get('מספר נשק', '')).strip()
                if weapon_type or weapon_id:
                    row_desc = []
                    if weapon_type:
                        row_desc.append(f"סוג נשק — {weapon_type}")
                    if weapon_id:
                        row_desc.append(f"מספר נשק — {weapon_id}")
                    items.append(" • " + ", ".join(row_desc))

            if items:
                grouped_items[weapon_sheet] = items

    except Exception as e:
        print(f"[{datetime.now()}] Error in sheet '{weapon_sheet}': {e}")

    # Format result
    if not grouped_items:
        await update.message.reply_text(f"✍️ לא נמצאו נתונים עבור מספר אישי {input_id}")
        return

    lines = []
    total = 0
    for sheet, entries in grouped_items.items():
        lines.append(f"📄 *{sheet}*")
        lines.extend(entries)
        lines.append("")
        total += len(entries)

    response = (
            f"✍️ *נתונים עבור {full_name}:*\n" +
            "\n".join(lines) +
            f"\nסה״כ רשומות: *{total}*"
    )
    await update.message.reply_text(response, parse_mode='Markdown')
    print(
        f"[{datetime.now()}] User {user_id} ({update.effective_user.full_name}) viewed {total} rows for ID {input_id}")


# ──────────────────────────────────────────────
async def update_armory_movements(context: ContextTypes.DEFAULT_TYPE):

    actions_sheet = signatures_spreadsheet.worksheet('תנועות תחמושת')
    armory_sheet = signatures_spreadsheet.worksheet('ammo-sum')

    inventory_rows = armory_sheet.get_all_values()
    actions_rows = actions_sheet.get_all_values()

    items_list=[]
    for idx, row in enumerate(inventory_rows[:-1]):  # skip last if i+1 needed
        items_list.append(inventory_rows[idx + 1][0])

    actions_headers = actions_rows[0]
    inv_headers = inventory_rows[0]

    idx_team = actions_headers.index("צוות") + 1
    idx_item = actions_headers.index("פריט") + 1
    idx_quantity = actions_headers.index("כמות") + 1
    action_idx = actions_headers.index("פעולה") + 1
    idx_status = actions_headers.index("האם עודכן") + 1

    for i, row in enumerate(actions_rows[1:], start=2):
        if len(row) < idx_status or row[idx_status - 1].strip() != 'לא':
            continue
        company = row[idx_team - 1].strip()
        item = row[idx_item - 1].strip()
        try:
            quantity = int(row[idx_quantity - 1].strip())
        except ValueError:
            continue
        action = row[action_idx-1].strip()
        bunker_index = inv_headers.index('בונקר')
        if company != 'בונקר':
            col_index = inv_headers.index(company) + 1
            if item not in items_list:
                armory_sheet.update_cell(len(inventory_rows)+1, 1, item)
            for j, inv_row in enumerate(inventory_rows[1:], start=2):  # start=2 to match rows
                if len(inv_row) < col_index:
                    continue
                if inv_row[0].strip() == item:
                    try:
                        current_val = int(inv_row[col_index - 1])
                        bunker_current_val = int(inv_row[bunker_index])
                        new_val = current_val + quantity if action == 'החתמת צוות' else max(current_val - quantity, 0)
                        if action == 'החתמת צוות':
                            bunker_new_val = max(bunker_current_val - quantity, 0)
                        elif action == 'שצל':
                            bunker_new_val = bunker_current_val
                        else:
                            bunker_new_val =bunker_current_val + quantity
                        armory_sheet.update_cell(j, col_index, new_val)
                        armory_sheet.update_cell(j, bunker_index + 1, bunker_new_val)
                        actions_sheet.update_cell(i, idx_status, 'כן')
                        break
                    except ValueError:
                        continue

        else:
            print('bunker')
            inventory_index = next((i for i, row in enumerate(inventory_rows) if row[0] == item), -1)
            for row in inventory_rows:
                if row and row[0].strip() == item:
                    inventory_rows = row
                    break
            for inventory_row in inventory_rows:
                if inventory_row and inventory_row[0].strip() == item:
                    inventory_rows = inventory_row
                    break
            for j in enumerate(inventory_rows, start=2):
                if inventory_rows[0].strip() == item:
                    try:
                        current_val = int(inventory_rows[bunker_index])
                        new_val = current_val + quantity if action == 'קבלת תחמושת' else max(current_val - quantity, 0)
                        armory_sheet.update_cell(inventory_index +1, bunker_index +1 , new_val)
                        actions_sheet.update_cell(i, idx_status, 'כן')
                        break
                    except ValueError:
                        continue
        print(f"[{datetime.now()}] Armory movements updated.")
        armory_sheet = signatures_spreadsheet.worksheet('ammo-sum')
        inventory_rows = armory_sheet.get_all_values()
        items_list = []
        for idx, row in enumerate(inventory_rows[:-1]):  # skip last if i+1 needed
            items_list.append(inventory_rows[idx + 1][0])
        inv_headers = inventory_rows[0]


# ──────────────────────────────────────────────

async def update_user_activity_log(context: ContextTypes.DEFAULT_TYPE):
    tab = logging_spreadsheet.worksheet('Audit Log1')
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    username = context.application.bot_data.get("username")[0]
    user_id = context.application.bot_data.get("userid")[0]
    for action in context.application.bot_data.get('user_activity_list'):
        tab.append_row([timestamp, username, user_id, action])
        context.application.bot_data.get('user_activity_list').remove(action)


# Helpers to build keyboard with checkmarks
def build_keyboard(selected: set[str]) -> InlineKeyboardMarkup:
    rows = []
    # one button per row (or group them if you prefer)
    for opt in OPTIONS:
        label = f"{'✅ ' if opt in selected else ''}{opt}"
        rows.append([InlineKeyboardButton(label, callback_data=f"TOGGLE|{opt}")])
    # action row
    rows.append([
        InlineKeyboardButton("בחר הכל", callback_data="SELECT_ALL"),
        InlineKeyboardButton("נקה", callback_data="CLEAR")
    ])
    rows.append([
        InlineKeyboardButton("סיום ✔", callback_data="DONE"),
        InlineKeyboardButton("בטל ✖", callback_data="CANCEL"),
    ])
    return InlineKeyboardMarkup(rows)


async def on_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    selected: set[str] = context.user_data.get("selected", set())

    if data.startswith("TOGGLE|"):
        _, opt = data.split("|", 1)
        if opt in selected:
            selected.remove(opt)
        else:
            selected.add(opt)
        context.user_data["selected"] = selected
        await query.edit_message_reply_markup(reply_markup=build_keyboard(selected))
        return

    if data == "SELECT_ALL":
        context.user_data["selected"] = set(OPTIONS)
        await query.edit_message_reply_markup(reply_markup=build_keyboard(context.user_data["selected"]))
        return

    if data == "CLEAR":
        context.user_data["selected"] = set()
        await query.edit_message_reply_markup(reply_markup=build_keyboard(set()))
        return

    if data == "DONE":
        choices = list(selected)
        text = "נבחרו: " + (", ".join(choices) if choices else "לא נבחר דבר")
        # Lock the message by replacing keyboard with plain text summary
        await query.edit_message_text(text)
        # Do something with `choices` here (save to DB, call API, etc.)
        return

    if data == "CANCEL":
        await query.edit_message_text("בוטל.")
        context.user_data["selected"] = set()
        return


# Telegram bot setup
app = ApplicationBuilder().token(tele_token).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
# app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quantity_input))
app.job_queue.run_repeating(update_armory_movements, interval=10, first=1)

app.run_polling()
