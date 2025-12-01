import asyncio
import logging
import json
import os
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, PreCheckoutQuery, ContentType
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, WEBAPP_URL, PAYMENT_TOKEN

logging.basicConfig(level=logging.INFO)
router = Router()

MSK = timezone(timedelta(hours=3))
DATA_DIR = "/app/data" if os.path.exists("/app") else "./data"

# ID владельцев
OWNERS = [736051965, 315066232]

# Мастера/врачи
MASTERS = {
    "portos": [
        {"id": "artem", "name": "Артём"},
        {"id": "dmitry", "name": "Дмитрий"},
        {"id": "rustam", "name": "Рустам"},
        {"id": "vlad", "name": "Владислав"},
    ],
    "clinic": [
        {"id": "doc_ivanov", "name": "Иванов А.И."},
        {"id": "doc_petrova", "name": "Петрова М.С."},
        {"id": "doc_sidorov", "name": "Сидоров К.В."},
    ]
}

SLOTS = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "12:00", "12:30",
         "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00", "16:30",
         "17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00"]

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"items": []}

def save_json(filename, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, filename), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def now_msk():
    return datetime.now(MSK)

def is_owner(user_id: int) -> bool:
    return user_id in OWNERS

@router.message(CommandStart())
async def cmd_start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Открыть приложение", web_app=WebAppInfo(url=WEBAPP_URL))],
    ])
    
    text = """🎉 *Добро пожаловать в BookIt!*

🧋 Заказать в *Pink Purple*
💈 Записаться в *PORTOS*
🏥 Записаться в *Здоровье семьи*

Нажмите кнопку ниже 👇"""
    
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
    
    if is_owner(message.from_user.id):
        admin_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Управление расписанием", callback_data="admin_menu")]
        ])
        await message.answer("👑 *Панель владельца:*", parse_mode="Markdown", reply_markup=admin_kb)

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ Нет доступа")
        return
    await show_admin_menu(message)

async def show_admin_menu(msg):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💈 PORTOS", callback_data="admin_biz_portos")],
        [InlineKeyboardButton(text="🏥 Клиника", callback_data="admin_biz_clinic")],
    ])
    text = "⚙️ *Управление расписанием*\n\nВыберите бизнес:"
    
    if isinstance(msg, Message):
        await msg.answer(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await msg.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)

@router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await show_admin_menu(callback)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_biz_"))
async def cb_select_business(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    biz = callback.data.replace("admin_biz_", "")
    masters = MASTERS.get(biz, [])
    
    buttons = [[InlineKeyboardButton(text=m["name"], callback_data=f"admin_master_{biz}_{m['id']}")] for m in masters]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("👤 *Выберите мастера/врача:*", parse_mode="Markdown", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_master_"))
async def cb_select_master(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    parts = callback.data.split("_")
    biz = parts[2]
    master_id = parts[3]
    
    today = now_msk().date()
    buttons = []
    for i in range(7):
        d = today + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        display = d.strftime("%d.%m") + (" •сегодня" if i == 0 else "")
        buttons.append([InlineKeyboardButton(text=display, callback_data=f"admin_date_{biz}_{master_id}_{date_str}")])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_biz_{biz}")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("📅 *Выберите дату:*", parse_mode="Markdown", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_date_"))
async def cb_select_date(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    parts = callback.data.split("_")
    biz, master_id, date = parts[2], parts[3], parts[4]
    
    await show_slots(callback, biz, master_id, date)
    await callback.answer()

async def show_slots(callback, biz, master_id, date):
    bookings = load_json("bookings.json")
    
    booked = {}
    for b in bookings.get("items", []):
        if (b.get("master_id") == master_id and 
            b.get("date") == date and 
            b.get("status") != "cancelled"):
            booked[b["time"]] = b
    
    buttons = []
    row = []
    for slot in SLOTS:
        if slot in booked:
            b = booked[slot]
            if b.get("is_manual_block"):
                text = f"🔒{slot}"
                cb = f"admin_unblock_{biz}_{master_id}_{date}_{slot}"
            else:
                text = f"🔴{slot}"
                cb = f"admin_info_{biz}_{master_id}_{date}_{slot}"
        else:
            text = f"🟢{slot}"
            cb = f"admin_block_{biz}_{master_id}_{date}_{slot}"
        
        row.append(InlineKeyboardButton(text=text, callback_data=cb))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_master_{biz}_{master_id}")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    date_display = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")
    text = f"📅 *{date_display}*\n\n🟢 свободно | 🔴 занято | 🔒 заблокировано"
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)

@router.callback_query(F.data.startswith("admin_block_"))
async def cb_block(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    
    parts = callback.data.split("_")
    biz, master_id, date, time = parts[2], parts[3], parts[4], parts[5]
    
    bookings = load_json("bookings.json")
    if "items" not in bookings:
        bookings["items"] = []
    
    for b in bookings.get("items", []):
        if (b.get("master_id") == master_id and b.get("date") == date and 
            b.get("time") == time and b.get("status") != "cancelled"):
            await callback.answer("❌ Уже занято!", show_alert=True)
            return
    
    bookings["items"].append({
        "booking_id": f"BLK{now_msk().strftime('%Y%m%d%H%M%S')}",
        "user_id": callback.from_user.id,
        "business_id": biz,
        "master_id": master_id,
        "date": date,
        "time": time,
        "service_name": "Заблокировано",
        "master_name": "",
        "service_price": 0,
        "status": "blocked",
        "is_manual_block": True,
        "created_at": now_msk().isoformat()
    })
    save_json("bookings.json", bookings)
    
    await callback.answer(f"🔒 {time} заблокирован!", show_alert=True)
    await show_slots(callback, biz, master_id, date)

@router.callback_query(F.data.startswith("admin_unblock_"))
async def cb_unblock(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    
    parts = callback.data.split("_")
    biz, master_id, date, time = parts[2], parts[3], parts[4], parts[5]
    
    bookings = load_json("bookings.json")
    
    for b in bookings.get("items", []):
        if (b.get("master_id") == master_id and b.get("date") == date and 
            b.get("time") == time and b.get("is_manual_block") and b.get("status") != "cancelled"):
            b["status"] = "cancelled"
            save_json("bookings.json", bookings)
            await callback.answer(f"🔓 {time} разблокирован!", show_alert=True)
            await show_slots(callback, biz, master_id, date)
            return
    
    await callback.answer("❌ Не найдено", show_alert=True)

@router.callback_query(F.data.startswith("admin_info_"))
async def cb_info(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    
    parts = callback.data.split("_")
    master_id, date, time = parts[3], parts[4], parts[5]
    
    bookings = load_json("bookings.json")
    
    for b in bookings.get("items", []):
        if (b.get("master_id") == master_id and b.get("date") == date and 
            b.get("time") == time and b.get("status") != "cancelled"):
            info = f"👤 {b.get('first_name', '?')}\n📱 {b.get('phone', 'нет')}\n✂️ {b.get('service_name', '')}"
            await callback.answer(info, show_alert=True)
            return
    
    await callback.answer("Не найдено", show_alert=True)

# === TELEGRAM PAYMENTS ===

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    """Подтверждение перед оплатой - всегда отвечаем OK"""
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment_handler(message: Message):
    """Обработка успешной оплаты"""
    payment = message.successful_payment
    
    # Парсим payload
    try:
        payload = json.loads(payment.invoice_payload)
        order_id = payload.get("order_id")
        amount = payload.get("amount", 0)
    except:
        order_id = None
        amount = payment.total_amount
    
    # Получаем детали заказа
    order_details = None
    pickup_time = None
    items_text = ""
    
    if order_id:
        orders = load_json("orders.json")
        for order in orders.get("items", []):
            if order.get("order_id") == order_id:
                order["payment_status"] = "paid"
                order["payment_id"] = payment.telegram_payment_charge_id
                order["paid_at"] = datetime.now(MSK).isoformat()
                order["status"] = "new"  # Заказ подтверждён
                order_details = order
                pickup_time = order.get("pickup_time")
                # Формируем список товаров
                items = order.get("items", [])
                items_text = "\n".join([f"  • {item['name']} × {item['qty']} = {item['price'] * item['qty']}₽" for item in items])
                break
        save_json("orders.json", orders)
    
    # Отправляем подтверждение пользователю
    user_msg = (
        f"✅ *Оплата прошла успешно!*\n\n"
        f"💰 Сумма: {payment.total_amount // 100} ₽\n"
        f"🧾 Заказ: #{order_id or 'N/A'}\n"
    )
    if pickup_time:
        user_msg += f"⏰ К времени: {pickup_time}\n"
    user_msg += "\nСпасибо за заказ! 🎉"
    
    await message.answer(user_msg, parse_mode="Markdown")
    
    # Уведомляем ВСЕХ владельцев Pink Purple
    owner_ids = [736051965, 315066232]
    try:
        owner_msg = (
            f"🍵 *НОВЫЙ ОПЛАЧЕННЫЙ ЗАКАЗ!*\n\n"
            f"🧾 *Заказ #{order_id}*\n"
            f"👤 Клиент: {message.from_user.first_name}"
        )
        if message.from_user.username:
            owner_msg += f" (@{message.from_user.username})"
        owner_msg += f"\n💰 Сумма: {payment.total_amount // 100} ₽\n"
        if pickup_time:
            owner_msg += f"⏰ К времени: {pickup_time}\n"
        owner_msg += f"\n📋 *Состав заказа:*\n{items_text}\n"
        owner_msg += f"\n💳 _Оплачено через Telegram_"
        
        for owner_id in owner_ids:
            try:
                await message.bot.send_message(owner_id, owner_msg, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Failed to notify owner {owner_id}: {e}")

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    print("🚀 BookIt Bot запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
