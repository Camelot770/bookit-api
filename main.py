from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
import json
import os
import httpx
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Московское время (UTC+3)
MSK = timezone(timedelta(hours=3))

def now_msk():
    return datetime.now(MSK)

# === Запуск бота в фоне ===
async def start_bot():
    """Запускает Telegram бота в фоновом режиме"""
    try:
        from aiogram import Bot, Dispatcher, F, Router
        from aiogram.filters import CommandStart
        from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, PreCheckoutQuery, ContentType
        from aiogram.fsm.storage.memory import MemoryStorage
        
        BOT_TOKEN = os.getenv("BOT_TOKEN", "7731397363:AAE7-L0anyBwzFmbYP_fYQnE2pP4SilBLPs")
        WEBAPP_URL = os.getenv("WEBAPP_URL", "https://bookit.vercel.app")
        
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())
        router = Router()
        
        @router.message(CommandStart())
        async def cmd_start(message: Message):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Открыть BookIt", web_app=WebAppInfo(url=WEBAPP_URL))]
            ])
            await message.answer(
                "👋 Добро пожаловать в *BookIt*!\n\n"
                "🍵 Заказывай напитки в Pink Purple\n"
                "💈 Записывайся в барбершоп PORTOS\n"
                "🏥 Бронируй приём в клинике\n\n"
                "Нажми кнопку ниже 👇",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        
        @router.pre_checkout_query()
        async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
            await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
        
        @router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
        async def successful_payment_handler(message: Message):
            payment = message.successful_payment
            try:
                payload = json.loads(payment.invoice_payload)
                order_id = payload.get("order_id")
            except:
                order_id = None
            
            # Обновляем статус заказа и получаем детали
            order_details = None
            business_id = "pink_purple"
            if order_id:
                orders = load_json("orders.json")
                for order in orders.get("items", []):
                    if order.get("order_id") == order_id:
                        order["payment_status"] = "paid"
                        order["payment_id"] = payment.telegram_payment_charge_id
                        order["paid_at"] = now_msk().isoformat()
                        order["status"] = "new"  # Теперь заказ активен
                        order_details = order
                        business_id = order.get("business_id", "pink_purple")
                        break
                save_json("orders.json", orders)
            
            # Подтверждение пользователю
            user_msg = f"✅ *Оплата прошла успешно!*\n\n💰 Сумма: {payment.total_amount // 100} ₽\n🧾 Заказ: #{order_id or 'N/A'}"
            if order_details and order_details.get("points_earned", 0) > 0:
                user_msg += f"\n⭐ Начислено баллов: {order_details['points_earned']}"
            user_msg += "\n\nСпасибо за заказ! 🎉"
            
            await message.answer(user_msg, parse_mode="Markdown")
            
            # Уведомление ВСЕМ владельцам бизнеса
            owner_ids = OWNERS.get(business_id, [736051965, 315066232])
            if order_details:
                try:
                    items = order_details.get("items", [])
                    items_text = "\n".join([f"  • {item['name']} × {item['qty']} = {item['price'] * item['qty']}₽" for item in items])
                    
                    owner_msg = f"🍵 *НОВЫЙ ОПЛАЧЕННЫЙ ЗАКАЗ!*\n\n🧾 *Заказ #{order_id}*\n"
                    owner_msg += f"👤 Клиент: {message.from_user.first_name}"
                    if message.from_user.username:
                        owner_msg += f" (@{message.from_user.username})"
                    if order_details.get("phone"):
                        owner_msg += f"\n📱 Телефон: {order_details['phone']}"
                    
                    owner_msg += f"\n\n📋 *Состав заказа:*\n{items_text}"
                    
                    # Детали оплаты
                    subtotal = sum(item['price'] * item['qty'] for item in items)
                    owner_msg += f"\n\n💵 Сумма товаров: {subtotal}₽"
                    
                    if order_details.get("discount", 0) > 0:
                        owner_msg += f"\n🎟️ Скидка ({order_details.get('promo_code', '')}): -{order_details['discount']}₽"
                    
                    if order_details.get("points_used", 0) > 0:
                        owner_msg += f"\n⭐ Списано баллов: -{order_details['points_used']}₽"
                    
                    if order_details.get("tips", 0) > 0:
                        owner_msg += f"\n💝 Чаевые: +{order_details['tips']}₽"
                    
                    owner_msg += f"\n\n💰 *ИТОГО: {order_details['total']}₽*"
                    
                    if order_details.get("pickup_time"):
                        owner_msg += f"\n⏰ К времени: {order_details['pickup_time']}"
                    else:
                        owner_msg += f"\n⏰ Как можно скорее"
                    
                    owner_msg += f"\n\n💳 _Оплачено через Telegram_"
                    
                    # Отправляем всем владельцам
                    for owner_id in owner_ids:
                        try:
                            await bot.send_message(owner_id, owner_msg, parse_mode="Markdown")
                        except Exception as e:
                            logger.error(f"Failed to notify owner {owner_id}: {e}")
                except Exception as e:
                    logger.error(f"Failed to prepare owner notification: {e}")
        
        dp.include_router(router)
        logger.info("🤖 Telegram Bot started!")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запуск бота в фоне
    bot_task = asyncio.create_task(start_bot())
    yield
    # Остановка при выключении
    bot_task.cancel()

app = FastAPI(title="BookIt API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Конфигурация ===

BOT_TOKEN = os.getenv("BOT_TOKEN", "7731397363:AAE7-L0anyBwzFmbYP_fYQnE2pP4SilBLPs")
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN", "390540012:LIVE:83691")

OWNERS = {
    "pink_purple": [736051965, 315066232],  # Два владельца
    "portos": [736051965],
    "clinic": [736051965],
}

# Проверка является ли пользователь владельцем
def is_owner(user_id: int, business_id: str = None) -> bool:
    if business_id:
        return user_id in OWNERS.get(business_id, [])
    # Проверяем все бизнесы
    for owners in OWNERS.values():
        if user_id in owners:
            return True
    return False

def get_owner_ids(business_id: str) -> list:
    return OWNERS.get(business_id, [])

WORKING_SLOTS = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "12:00", "12:30", 
                 "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00", "16:30",
                 "17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00"]

# === Данные клиник ===

CLINIC_BRANCHES = {
    "branch_central": {
        "id": "branch_central",
        "name": "Центральный филиал",
        "address": "ул. Ленина, 42",
        "phone": "+7 (999) 111-22-33",
        "work_hours": "8:00 - 20:00"
    },
    "branch_north": {
        "id": "branch_north", 
        "name": "Северный филиал",
        "address": "пр. Мира, 128",
        "phone": "+7 (999) 222-33-44",
        "work_hours": "9:00 - 21:00"
    },
    "branch_south": {
        "id": "branch_south",
        "name": "Южный филиал", 
        "address": "ул. Гагарина, 15",
        "phone": "+7 (999) 333-44-55",
        "work_hours": "8:00 - 19:00"
    }
}

# Услуги с привязкой к специальности
CLINIC_SERVICES = {
    "branch_central": {
        "therapy": {
            "name": "🩺 Терапия", 
            "specialty": "Терапевт",
            "items": [
                {"id": "consult_therapy", "name": "Приём терапевта", "price": 1500, "duration": 30},
                {"id": "checkup_basic", "name": "Базовый осмотр", "price": 2000, "duration": 45},
            ]
        },
        "cardio": {
            "name": "❤️ Кардиология", 
            "specialty": "Кардиолог",
            "items": [
                {"id": "consult_cardio", "name": "Приём кардиолога", "price": 2000, "duration": 40},
                {"id": "ecg", "name": "ЭКГ", "price": 1200, "duration": 20},
                {"id": "echo", "name": "ЭхоКГ", "price": 3500, "duration": 45},
            ]
        },
        "neuro": {
            "name": "🧠 Неврология", 
            "specialty": "Невролог",
            "items": [
                {"id": "consult_neuro", "name": "Приём невролога", "price": 1800, "duration": 30},
            ]
        },
        "pediatrics": {
            "name": "👶 Педиатрия", 
            "specialty": "Педиатр",
            "items": [
                {"id": "consult_child", "name": "Приём педиатра", "price": 1600, "duration": 30},
                {"id": "vaccination", "name": "Вакцинация", "price": 800, "duration": 15},
            ]
        },
    },
    "branch_north": {
        "therapy": {
            "name": "🩺 Терапия", 
            "specialty": "Терапевт",
            "items": [
                {"id": "consult_therapy", "name": "Приём терапевта", "price": 1400, "duration": 30},
            ]
        },
        "gyneco": {
            "name": "👩 Гинекология", 
            "specialty": "Гинеколог",
            "items": [
                {"id": "consult_gyn", "name": "Приём гинеколога", "price": 2200, "duration": 40},
                {"id": "uzi_gyn", "name": "УЗИ органов малого таза", "price": 2500, "duration": 30},
            ]
        },
        "surgery": {
            "name": "🔪 Хирургия", 
            "specialty": "Хирург",
            "items": [
                {"id": "consult_surg", "name": "Консультация хирурга", "price": 1800, "duration": 30},
                {"id": "minor_surg", "name": "Малая хирургия", "price": 5000, "duration": 60},
            ]
        },
    },
    "branch_south": {
        "therapy": {
            "name": "🩺 Терапия", 
            "specialty": "Терапевт",
            "items": [
                {"id": "consult_therapy", "name": "Приём терапевта", "price": 1300, "duration": 30},
            ]
        },
        "derma": {
            "name": "🧴 Дерматология", 
            "specialty": "Дерматолог",
            "items": [
                {"id": "consult_derma", "name": "Приём дерматолога", "price": 1700, "duration": 30},
                {"id": "derma_procedure", "name": "Процедуры", "price": 2500, "duration": 45},
            ]
        },
        "ortho": {
            "name": "🦴 Ортопедия", 
            "specialty": "Ортопед",
            "items": [
                {"id": "consult_ortho", "name": "Приём ортопеда", "price": 1900, "duration": 40},
                {"id": "xray", "name": "Рентген", "price": 1500, "duration": 20},
            ]
        },
        "eye": {
            "name": "👁️ Офтальмология", 
            "specialty": "Офтальмолог",
            "items": [
                {"id": "consult_eye", "name": "Приём офтальмолога", "price": 1600, "duration": 30},
                {"id": "eye_check", "name": "Проверка зрения", "price": 800, "duration": 15},
            ]
        },
    }
}

# Врачи с привязкой к специальности
CLINIC_DOCTORS = {
    "branch_central": [
        {"id": "doc_ivanov", "name": "Иванов А.И.", "specialty": "Терапевт", "experience": "15 лет", "rating": 4.9},
        {"id": "doc_petrova", "name": "Петрова М.С.", "specialty": "Кардиолог", "experience": "12 лет", "rating": 4.8},
        {"id": "doc_sidorov", "name": "Сидоров К.В.", "specialty": "Невролог", "experience": "10 лет", "rating": 4.7},
        {"id": "doc_kozlova", "name": "Козлова Е.А.", "specialty": "Педиатр", "experience": "8 лет", "rating": 4.9},
    ],
    "branch_north": [
        {"id": "doc_smirnov", "name": "Смирнов Д.П.", "specialty": "Терапевт", "experience": "20 лет", "rating": 4.9},
        {"id": "doc_volkova", "name": "Волкова И.Н.", "specialty": "Гинеколог", "experience": "14 лет", "rating": 4.8},
        {"id": "doc_morozov", "name": "Морозов А.С.", "specialty": "Хирург", "experience": "18 лет", "rating": 4.9},
    ],
    "branch_south": [
        {"id": "doc_novikov", "name": "Новиков П.А.", "specialty": "Терапевт", "experience": "11 лет", "rating": 4.7},
        {"id": "doc_fedorova", "name": "Фёдорова О.В.", "specialty": "Дерматолог", "experience": "9 лет", "rating": 4.8},
        {"id": "doc_alexeev", "name": "Алексеев В.М.", "specialty": "Ортопед", "experience": "16 лет", "rating": 4.9},
        {"id": "doc_egorova", "name": "Егорова Т.С.", "specialty": "Офтальмолог", "experience": "7 лет", "rating": 4.6},
    ]
}

PORTOS_MASTERS = [
    {"id": "artem", "name": "Артём", "rating": 4.9},
    {"id": "dmitry", "name": "Дмитрий", "rating": 4.8},
    {"id": "rustam", "name": "Рустам", "rating": 4.9},
    {"id": "vlad", "name": "Владислав", "rating": 4.7},
]

PORTOS_SERVICES = {
    "haircut": {"name": "✂️ Стрижки", "items": [
        {"id": "mens", "name": "Мужская стрижка", "price": 1200, "duration": 45},
        {"id": "kids", "name": "Детская стрижка", "price": 800, "duration": 30},
    ]},
    "beard": {"name": "🧔 Борода", "items": [
        {"id": "trim", "name": "Моделирование бороды", "price": 700, "duration": 30},
    ]},
    "combo": {"name": "🎯 Комбо", "items": [
        {"id": "full", "name": "Стрижка + Борода", "price": 1700, "duration": 75},
    ]}
}

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def load_json(filename: str) -> dict:
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(filename: str, data: dict):
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def filter_past_slots(slots: list, date: str) -> list:
    """Убираем слоты которые уже прошли (для сегодняшней даты)"""
    now = now_msk()
    today = now.strftime("%Y-%m-%d")
    
    if date != today:
        return slots
    
    current_time = now.strftime("%H:%M")
    return [s for s in slots if s > current_time]

class OrderItem(BaseModel):
    id: str
    name: str
    price: int
    qty: int

class CreateOrder(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    business_id: str
    items: List[OrderItem]
    total: int
    phone: Optional[str] = None
    pickup_time: Optional[str] = None
    payment_method: Optional[str] = "telegram"  # telegram или cash
    payment_status: Optional[str] = "pending"   # pending, paid
    tips: Optional[int] = 0
    promo_code: Optional[str] = None
    discount: Optional[int] = 0
    points_used: Optional[int] = 0
    points_earned: Optional[int] = 0

class CreateBooking(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    business_id: str
    branch_id: Optional[str] = None
    service_id: str
    service_name: str
    service_price: int
    master_id: str
    master_name: str
    date: str
    time: str
    phone: Optional[str] = None

class CreateReservation(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    business_id: str
    guest_name: str
    guests: str
    date: str
    time: str
    comment: Optional[str] = None
    phone: Optional[str] = None

class UserProfile(BaseModel):
    user_id: int
    phone: str
    first_name: Optional[str] = None
    username: Optional[str] = None

async def send_telegram_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
            print(f"Telegram send to {chat_id}: {response.status_code} - {response.text[:200]}")
            return response.json()
    except Exception as e:
        print(f"Telegram send error: {e}")
        raise

@app.get("/")
def root():
    return {"status": "ok", "service": "BookIt API", "version": "2.1.0", "time": now_msk().isoformat()}

@app.post("/api/user/register")
def register_user(profile: UserProfile):
    users = load_json("users.json")
    users[str(profile.user_id)] = {
        "user_id": profile.user_id,
        "phone": profile.phone,
        "first_name": profile.first_name,
        "username": profile.username,
        "registered_at": now_msk().isoformat()
    }
    save_json("users.json", users)
    return {"status": "ok"}

@app.get("/api/user/{user_id}/profile")
def get_user_profile(user_id: int):
    users = load_json("users.json")
    user = users.get(str(user_id))
    if not user:
        return {"registered": False}
    return {"registered": True, **user}

@app.get("/api/user/{user_id}/bookings")
def get_user_bookings(user_id: int):
    bookings = load_json("bookings.json")
    user_bookings = [b for b in bookings.get("items", []) if b.get("user_id") == user_id]
    now = now_msk()
    for b in user_bookings:
        try:
            booking_dt = datetime.strptime(f"{b['date']} {b['time']}", "%Y-%m-%d %H:%M").replace(tzinfo=MSK)
            b["is_past"] = booking_dt < now
        except:
            b["is_past"] = False
    user_bookings.sort(key=lambda x: (x.get("is_past", False), x.get("date", ""), x.get("time", "")))
    return user_bookings

@app.get("/api/user/{user_id}/orders")
def get_user_orders(user_id: int):
    orders = load_json("orders.json")
    user_orders = [o for o in orders.get("items", []) if o.get("user_id") == user_id]
    user_orders.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return user_orders

@app.get("/api/clinic/branches")
def get_clinic_branches():
    return list(CLINIC_BRANCHES.values())

@app.get("/api/clinic/branch/{branch_id}")
def get_branch_info(branch_id: str):
    if branch_id not in CLINIC_BRANCHES:
        raise HTTPException(status_code=404, detail="Branch not found")
    return CLINIC_BRANCHES[branch_id]

@app.get("/api/clinic/branch/{branch_id}/services")
def get_branch_services(branch_id: str):
    """Возвращает категории услуг (специальности) филиала"""
    if branch_id not in CLINIC_SERVICES:
        raise HTTPException(status_code=404, detail="Branch not found")
    return CLINIC_SERVICES[branch_id]

@app.get("/api/clinic/branch/{branch_id}/doctors")
def get_branch_doctors(branch_id: str, specialty: Optional[str] = None):
    """Возвращает врачей филиала, опционально фильтруя по специальности"""
    if branch_id not in CLINIC_DOCTORS:
        raise HTTPException(status_code=404, detail="Branch not found")
    
    doctors = CLINIC_DOCTORS[branch_id]
    if specialty:
        doctors = [d for d in doctors if d["specialty"] == specialty]
    return doctors

@app.get("/api/clinic/slots/{branch_id}/{doctor_id}/{date}")
def get_doctor_slots(branch_id: str, doctor_id: str, date: str):
    """Возвращает доступные слоты врача, исключая прошедшие и заблокированные"""
    bookings = load_json("bookings.json")
    blocked = load_json("blocked_slots.json")
    
    booked = []
    for b in bookings.get("items", []):
        if (b.get("branch_id") == branch_id and 
            b.get("master_id") == doctor_id and 
            b.get("date") == date and 
            b.get("status") != "cancelled"):
            booked.append(b["time"])
    
    # Учитываем заблокированные слоты
    blocked_slots = []
    for bl in blocked.get("items", []):
        if bl.get("master_id") == doctor_id and bl.get("date") == date:
            blocked_slots.extend(bl.get("slots", []))
    
    available = [s for s in WORKING_SLOTS if s not in booked and s not in blocked_slots]
    # Убираем прошедшие слоты для сегодняшней даты
    available = filter_past_slots(available, date)
    
    return {"date": date, "doctor_id": doctor_id, "slots": available}

@app.get("/api/portos/masters")
def get_masters():
    return PORTOS_MASTERS

@app.get("/api/portos/services")
def get_barber_services():
    return PORTOS_SERVICES

@app.get("/api/portos/slots/{master_id}/{date}")
def get_barber_slots(master_id: str, date: str):
    """Возвращает доступные слоты мастера, исключая прошедшие и заблокированные"""
    bookings = load_json("bookings.json")
    blocked = load_json("blocked_slots.json")
    
    booked = []
    for b in bookings.get("items", []):
        if (b.get("master_id") == master_id and 
            b.get("date") == date and 
            b.get("business_id") == "portos" and 
            b.get("status") != "cancelled"):
            booked.append(b["time"])
    
    # Учитываем заблокированные слоты
    blocked_slots = []
    for bl in blocked.get("items", []):
        if bl.get("master_id") == master_id and bl.get("date") == date:
            blocked_slots.extend(bl.get("slots", []))
    
    available = [s for s in WORKING_SLOTS if s not in booked and s not in blocked_slots]
    # Убираем прошедшие слоты для сегодняшней даты
    available = filter_past_slots(available, date)
    
    return {"date": date, "master_id": master_id, "slots": available}

# === Управление слотами для владельцев ===

class BlockSlot(BaseModel):
    owner_id: int
    business_id: str  # "portos" или "clinic"
    master_id: str    # ID мастера/врача
    branch_id: Optional[str] = None  # Для клиники
    date: str         # "2024-12-05"
    time: str         # "14:00"
    reason: Optional[str] = None  # Причина блокировки

@app.post("/api/admin/slots/block")
async def block_slot(data: BlockSlot):
    """Владелец блокирует слот (занято из другого источника)"""
    if data.owner_id not in OWNERS.values():
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    bookings = load_json("bookings.json")
    if "items" not in bookings:
        bookings["items"] = []
    
    # Проверяем, не занят ли уже слот
    for b in bookings.get("items", []):
        if (b.get("master_id") == data.master_id and 
            b.get("date") == data.date and 
            b.get("time") == data.time and
            b.get("status") != "cancelled"):
            raise HTTPException(status_code=400, detail="Слот уже занят")
    
    booking_id = f"BLK{now_msk().strftime('%Y%m%d%H%M%S')}"
    block_data = {
        "booking_id": booking_id,
        "user_id": data.owner_id,
        "business_id": data.business_id,
        "branch_id": data.branch_id,
        "master_id": data.master_id,
        "date": data.date,
        "time": data.time,
        "service_name": data.reason or "Заблокировано владельцем",
        "master_name": "",
        "service_price": 0,
        "status": "blocked",
        "is_manual_block": True,
        "created_at": now_msk().isoformat()
    }
    bookings["items"].append(block_data)
    save_json("bookings.json", bookings)
    
    return {"status": "blocked", "booking_id": booking_id}

@app.post("/api/admin/slots/unblock")
async def unblock_slot(owner_id: int, booking_id: str):
    """Владелец разблокирует слот"""
    if owner_id not in OWNERS.values():
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    bookings = load_json("bookings.json")
    for b in bookings.get("items", []):
        if b.get("booking_id") == booking_id and b.get("is_manual_block"):
            b["status"] = "cancelled"
            save_json("bookings.json", bookings)
            return {"status": "unblocked"}
    
    raise HTTPException(status_code=404, detail="Блокировка не найдена")

@app.get("/api/admin/slots/blocked/{business_id}")
async def get_blocked_slots(business_id: str, owner_id: int):
    """Получить все заблокированные слоты"""
    if owner_id not in OWNERS.values():
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    bookings = load_json("bookings.json")
    blocked = [b for b in bookings.get("items", []) 
               if b.get("business_id") == business_id 
               and b.get("is_manual_block") 
               and b.get("status") != "cancelled"]
    
    return blocked

@app.get("/api/orders/business/{business_id}")
async def get_business_orders(business_id: str, limit: int = 100):
    """Получить заказы бизнеса (для панели владельца) - только оплаченные"""
    orders = load_json("orders.json")
    business_orders = [
        o for o in orders.get("items", [])
        if o.get("business_id") == business_id 
        and o.get("payment_status") == "paid"  # Только оплаченные!
    ]
    # Сортируем по дате, новые первые
    business_orders.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return business_orders[:limit]

@app.patch("/api/orders/{order_id}/status")
async def update_order_status(order_id: str, status: str):
    """Обновить статус заказа (для панели владельца)"""
    valid_statuses = ["new", "preparing", "ready", "completed", "cancelled"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Неверный статус")
    
    orders = load_json("orders.json")
    for order in orders.get("items", []):
        if order.get("order_id") == order_id:
            order["status"] = status
            order["updated_at"] = now_msk().isoformat()
            save_json("orders.json", orders)
            return {"status": "updated", "order": order}
    
    raise HTTPException(status_code=404, detail="Заказ не найден")

@app.get("/api/analytics/{business_id}")
async def get_business_analytics(business_id: str, period: str = "week"):
    """Расширенная аналитика бизнеса"""
    orders = load_json("orders.json")
    
    now = now_msk()
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=7)
    elif period == "month":
        start = now - timedelta(days=30)
    else:
        start = now - timedelta(days=365)
    
    # Только оплаченные заказы
    business_orders = [
        o for o in orders.get("items", [])
        if o.get("business_id") == business_id and
           o.get("payment_status") == "paid" and
           datetime.fromisoformat(o.get("created_at", now.isoformat())) >= start
    ]
    
    total_orders = len(business_orders)
    total_revenue = sum(o.get("total", 0) for o in business_orders)
    total_tips = sum(o.get("tips", 0) for o in business_orders)
    total_discount = sum(o.get("discount", 0) for o in business_orders)
    total_points_used = sum(o.get("points_used", 0) for o in business_orders)
    avg_check = total_revenue // total_orders if total_orders > 0 else 0
    unique_clients = len(set(o.get("user_id") for o in business_orders))
    
    # Топ товаров
    item_counts = {}
    item_revenue = {}
    for order in business_orders:
        for item in order.get("items", []):
            name = item.get("name", "Unknown")
            qty = item.get("qty", 1)
            price = item.get("price", 0)
            item_counts[name] = item_counts.get(name, 0) + qty
            item_revenue[name] = item_revenue.get(name, 0) + (price * qty)
    
    top_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Заказы по дням (для графика)
    orders_by_day = {}
    revenue_by_day = {}
    for order in business_orders:
        day = order.get("created_at", "")[:10]
        orders_by_day[day] = orders_by_day.get(day, 0) + 1
        revenue_by_day[day] = revenue_by_day.get(day, 0) + order.get("total", 0)
    
    # Заказы по часам
    orders_by_hour = {}
    for order in business_orders:
        hour = order.get("created_at", "")[11:13]
        if hour:
            orders_by_hour[hour] = orders_by_hour.get(hour, 0) + 1
    
    # Использование промокодов
    promo_usage = {}
    for order in business_orders:
        promo = order.get("promo_code")
        if promo:
            promo_usage[promo] = promo_usage.get(promo, 0) + 1
    
    return {
        "period": period,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "total_tips": total_tips,
        "total_discount": total_discount,
        "total_points_used": total_points_used,
        "avg_check": avg_check,
        "unique_clients": unique_clients,
        "top_items": [{"name": n, "count": c, "revenue": item_revenue.get(n, 0)} for n, c in top_items],
        "orders_by_day": [{"date": d, "orders": c, "revenue": revenue_by_day.get(d, 0)} for d, c in sorted(orders_by_day.items())],
        "orders_by_hour": [{"hour": h, "count": c} for h, c in sorted(orders_by_hour.items())],
        "promo_usage": [{"code": c, "count": n} for c, n in promo_usage.items()]
    }

# === СТОП-ЛИСТ И УПРАВЛЕНИЕ МЕНЮ ===

class StopListItem(BaseModel):
    item_id: str
    reason: Optional[str] = None

class UpdateJuiceballsRequest(BaseModel):
    available: List[str]  # Список доступных джусболов

class UpdateSettingsRequest(BaseModel):
    is_open: Optional[bool] = None
    opening_time: Optional[str] = None
    closing_time: Optional[str] = None
    min_order: Optional[int] = None
    delivery_available: Optional[bool] = None
    pickup_times: Optional[List[str]] = None

@app.get("/api/menu/stoplist/{business_id}")
async def get_stoplist(business_id: str):
    """Получить стоп-лист бизнеса"""
    stoplist = load_json("stoplist.json")
    return stoplist.get(business_id, [])

@app.post("/api/menu/stoplist/{business_id}/add")
async def add_to_stoplist(business_id: str, item: StopListItem):
    """Добавить товар в стоп-лист"""
    stoplist = load_json("stoplist.json")
    if business_id not in stoplist:
        stoplist[business_id] = []
    
    # Проверяем, не добавлен ли уже
    existing_ids = [i.get("item_id") for i in stoplist[business_id]]
    if item.item_id not in existing_ids:
        stoplist[business_id].append({
            "item_id": item.item_id,
            "reason": item.reason,
            "added_at": now_msk().isoformat()
        })
        save_json("stoplist.json", stoplist)
    
    return {"status": "added", "stoplist": stoplist[business_id]}

@app.post("/api/menu/stoplist/{business_id}/remove")
async def remove_from_stoplist(business_id: str, item: StopListItem):
    """Убрать товар из стоп-листа"""
    stoplist = load_json("stoplist.json")
    if business_id in stoplist:
        stoplist[business_id] = [i for i in stoplist[business_id] if i.get("item_id") != item.item_id]
        save_json("stoplist.json", stoplist)
    
    return {"status": "removed", "stoplist": stoplist.get(business_id, [])}

@app.get("/api/menu/juiceballs/{business_id}")
async def get_juiceballs(business_id: str):
    """Получить доступные джусболы"""
    logger.info(f"GET juiceballs for {business_id}")
    settings = load_json("business_settings.json")
    default_juiceballs = ["Клубника", "Черника", "Киви", "Виноград", "Манго", "Маракуйя"]
    result = settings.get(business_id, {}).get("juiceballs", default_juiceballs)
    logger.info(f"Returning juiceballs: {result}")
    return result

@app.post("/api/menu/juiceballs/{business_id}")
async def update_juiceballs(business_id: str, data: UpdateJuiceballsRequest):
    """Обновить доступные джусболы"""
    logger.info(f"POST juiceballs for {business_id}: {data.available}")
    settings = load_json("business_settings.json")
    if business_id not in settings:
        settings[business_id] = {}
    settings[business_id]["juiceballs"] = data.available
    save_json("business_settings.json", settings)
    logger.info(f"Saved juiceballs for {business_id}")
    return {"status": "updated", "juiceballs": data.available}

@app.get("/api/business/settings/{business_id}")
async def get_business_settings(business_id: str):
    """Получить настройки бизнеса"""
    settings = load_json("business_settings.json")
    default_settings = {
        "is_open": True,
        "opening_time": "10:00",
        "closing_time": "22:00",
        "min_order": 0,
        "delivery_available": False,
        "pickup_times": ["Как можно скорее", "Через 15 мин", "Через 30 мин", "Через 45 мин", "Через 1 час"],
        "juiceballs": ["Клубника", "Черника", "Киви", "Виноград", "Манго", "Маракуйя"]
    }
    return {**default_settings, **settings.get(business_id, {})}

@app.post("/api/business/settings/{business_id}")
async def update_business_settings(business_id: str, data: UpdateSettingsRequest):
    """Обновить настройки бизнеса"""
    settings = load_json("business_settings.json")
    if business_id not in settings:
        settings[business_id] = {}
    
    if data.is_open is not None:
        settings[business_id]["is_open"] = data.is_open
    if data.opening_time is not None:
        settings[business_id]["opening_time"] = data.opening_time
    if data.closing_time is not None:
        settings[business_id]["closing_time"] = data.closing_time
    if data.min_order is not None:
        settings[business_id]["min_order"] = data.min_order
    if data.delivery_available is not None:
        settings[business_id]["delivery_available"] = data.delivery_available
    if data.pickup_times is not None:
        settings[business_id]["pickup_times"] = data.pickup_times
    
    save_json("business_settings.json", settings)
    return {"status": "updated", "settings": settings[business_id]}

@app.get("/api/menu/available/{business_id}")
async def get_available_menu(business_id: str):
    """Получить меню с учётом стоп-листа (для клиентов)"""
    stoplist = load_json("stoplist.json")
    settings = load_json("business_settings.json")
    
    stopped_ids = [i.get("item_id") for i in stoplist.get(business_id, [])]
    business_settings = settings.get(business_id, {})
    
    return {
        "stopped_items": stopped_ids,
        "is_open": business_settings.get("is_open", True),
        "juiceballs": business_settings.get("juiceballs", ["Клубника", "Черника", "Киви", "Виноград", "Манго", "Маракуйя"]),
        "opening_time": business_settings.get("opening_time", "10:00"),
        "closing_time": business_settings.get("closing_time", "22:00"),
        "min_order": business_settings.get("min_order", 0)
    }

# === API ДЛЯ РАСПИСАНИЯ ВЛАДЕЛЬЦА ===

class BlockSlotsRequest(BaseModel):
    master_id: str
    date: str
    slots: List[str]
    reason: Optional[str] = None

class UnblockSlotRequest(BaseModel):
    master_id: str
    date: str
    slot: str

class CancelBookingRequest(BaseModel):
    master_id: str
    date: str
    slot: str

@app.get("/api/owner/schedule/{master_id}/{date}")
async def get_owner_schedule(master_id: str, date: str):
    """Получить расписание мастера на день (для владельца)"""
    bookings = load_json("bookings.json")
    blocked = load_json("blocked_slots.json")
    
    # Фильтруем записи на этот день
    day_bookings = []
    for b in bookings.get("items", []):
        if b.get("master_id") == master_id and b.get("date") == date and b.get("status") != "cancelled":
            day_bookings.append({
                "time": b.get("time"),
                "client": b.get("guest_name") or b.get("first_name") or "Клиент",
                "service": b.get("service_name", "Услуга"),
                "phone": b.get("phone", ""),
                "booking_id": b.get("booking_id")
            })
    
    # Фильтруем заблокированные слоты
    blocked_slots = []
    for bl in blocked.get("items", []):
        if bl.get("master_id") == master_id and bl.get("date") == date:
            blocked_slots.extend(bl.get("slots", []))
    
    return {
        "bookings": day_bookings,
        "blocked": blocked_slots
    }

@app.post("/api/owner/block-slots")
async def block_slots(data: BlockSlotsRequest):
    """Заблокировать слоты (владелец)"""
    blocked = load_json("blocked_slots.json")
    if "items" not in blocked:
        blocked["items"] = []
    
    # Ищем существующую запись
    existing = None
    for bl in blocked["items"]:
        if bl.get("master_id") == data.master_id and bl.get("date") == data.date:
            existing = bl
            break
    
    if existing:
        # Добавляем новые слоты
        for slot in data.slots:
            if slot not in existing["slots"]:
                existing["slots"].append(slot)
        existing["reason"] = data.reason
    else:
        # Создаём новую запись
        blocked["items"].append({
            "master_id": data.master_id,
            "date": data.date,
            "slots": data.slots,
            "reason": data.reason,
            "created_at": now_msk().isoformat()
        })
    
    save_json("blocked_slots.json", blocked)
    return {"status": "blocked", "slots": data.slots}

@app.post("/api/owner/unblock-slot")
async def unblock_slot(data: UnblockSlotRequest):
    """Разблокировать слот (владелец)"""
    blocked = load_json("blocked_slots.json")
    
    for bl in blocked.get("items", []):
        if bl.get("master_id") == data.master_id and bl.get("date") == data.date:
            if data.slot in bl.get("slots", []):
                bl["slots"].remove(data.slot)
            break
    
    save_json("blocked_slots.json", blocked)
    return {"status": "unblocked", "slot": data.slot}

@app.post("/api/owner/cancel-booking")
async def owner_cancel_booking(data: CancelBookingRequest):
    """Отменить запись (владелец)"""
    bookings = load_json("bookings.json")
    
    for b in bookings.get("items", []):
        if (b.get("master_id") == data.master_id and 
            b.get("date") == data.date and 
            b.get("time") == data.slot):
            b["status"] = "cancelled"
            b["cancelled_by"] = "owner"
            b["cancelled_at"] = now_msk().isoformat()
            
            # Отправляем уведомление клиенту
            if b.get("user_id"):
                try:
                    message = f"❌ *Запись отменена*\n\nВаша запись на {data.date} в {data.slot} была отменена заведением.\n\nПриносим извинения за неудобства."
                    await send_telegram_message(b["user_id"], message)
                except:
                    pass
            break
    
    save_json("bookings.json", bookings)
    return {"status": "cancelled"}

@app.post("/api/orders")
async def create_order(order: CreateOrder):
    orders = load_json("orders.json")
    if "items" not in orders:
        orders["items"] = []
    
    now = now_msk()
    order_id = f"ORD{len(orders['items']) + 1:05d}"
    order_data = {
        "order_id": order_id,
        "user_id": order.user_id,
        "username": order.username,
        "first_name": order.first_name,
        "business_id": order.business_id,
        "items": [item.dict() for item in order.items],
        "total": order.total,
        "phone": order.phone,
        "pickup_time": order.pickup_time,
        "payment_method": order.payment_method or "telegram",
        "payment_status": order.payment_status or "pending",
        "tips": order.tips or 0,
        "promo_code": order.promo_code,
        "discount": order.discount or 0,
        "points_used": order.points_used or 0,
        "points_earned": order.points_earned or 0,
        "status": "pending",  # pending пока не оплачен
        "created_at": now.isoformat()
    }
    orders["items"].append(order_data)
    save_json("orders.json", orders)
    
    # НЕ отправляем уведомление владельцу здесь!
    # Уведомление отправляется ТОЛЬКО после успешной оплаты в боте
    
    return {"order_id": order_id, "status": "created"}

@app.post("/api/orders/{order_id}/cancel")
async def cancel_order(order_id: str, user_id: int):
    """Отмена заказа пользователем"""
    orders = load_json("orders.json")
    for order in orders.get("items", []):
        if order.get("order_id") == order_id and order.get("user_id") == user_id:
            if order.get("status") != "new":
                raise HTTPException(status_code=400, detail="Заказ уже нельзя отменить")
            
            order["status"] = "cancelled"
            save_json("orders.json", orders)
            
            now = now_msk()
            items_text = ", ".join([f"{i['name']} x{i['qty']}" for i in order.get("items", [])])
            message = f"❌ *ОТМЕНА ЗАКАЗА #{order_id}*\n\n⏰ {now.strftime('%d.%m.%Y %H:%M')} (МСК)\n\n👤 {order.get('first_name', 'Клиент')}\n📱 {order.get('phone', 'нет')}\n\n*Был заказ:*\n{items_text}\n\n💰 *Сумма: {order.get('total', 0)}₽*"
            
            try:
                await send_telegram_message(OWNERS.get(order.get("business_id", "pink_purple"), OWNERS["pink_purple"]), message)
            except Exception as e:
                print(f"Failed to send cancel notification: {e}")
            
            return {"status": "cancelled"}
    
    raise HTTPException(status_code=404, detail="Заказ не найден")

@app.post("/api/bookings")
async def create_booking(booking: CreateBooking):
    bookings = load_json("bookings.json")
    if "items" not in bookings:
        bookings["items"] = []
    
    now = now_msk()
    booking_id = f"BK{len(bookings['items']) + 1:05d}"
    booking_data = {
        "booking_id": booking_id,
        "user_id": booking.user_id,
        "username": booking.username,
        "first_name": booking.first_name,
        "business_id": booking.business_id,
        "branch_id": booking.branch_id,
        "service_id": booking.service_id,
        "service_name": booking.service_name,
        "service_price": booking.service_price,
        "master_id": booking.master_id,
        "master_name": booking.master_name,
        "date": booking.date,
        "time": booking.time,
        "phone": booking.phone,
        "status": "confirmed",
        "created_at": now.isoformat()
    }
    bookings["items"].append(booking_data)
    save_json("bookings.json", bookings)
    
    date_display = datetime.strptime(booking.date, "%Y-%m-%d").strftime("%d.%m.%Y")
    if booking.business_id == "clinic":
        branch = CLINIC_BRANCHES.get(booking.branch_id, {})
        message = f"🏥 *НОВАЯ ЗАПИСЬ #{booking_id}*\n\n📅 {date_display} в {booking.time}\n🏢 Филиал: {branch.get('name', '')}\n\n👤 {booking.first_name or 'Пациент'}\n📱 {booking.phone or 'Нет телефона'}\n\n🩺 Услуга: *{booking.service_name}*\n👨‍⚕️ Врач: *{booking.master_name}*\n💰 Стоимость: *{booking.service_price}₽*"
    else:
        message = f"💈 *НОВАЯ ЗАПИСЬ #{booking_id}*\n\n📅 {date_display} в {booking.time}\n\n👤 {booking.first_name or 'Клиент'}\n📱 {booking.phone or 'Нет телефона'}\n\n✂️ Услуга: *{booking.service_name}*\n👨‍🦱 Мастер: *{booking.master_name}*\n💰 Стоимость: *{booking.service_price}₽*"
    
    try:
        await send_telegram_message(OWNERS.get(booking.business_id, OWNERS["portos"]), message)
    except Exception as e:
        print(f"Failed to send booking notification: {e}")
    
    return {"booking_id": booking_id, "status": "confirmed"}

@app.post("/api/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str, user_id: int):
    bookings = load_json("bookings.json")
    for booking in bookings.get("items", []):
        if booking.get("booking_id") == booking_id and booking.get("user_id") == user_id:
            booking["status"] = "cancelled"
            save_json("bookings.json", bookings)
            
            now = now_msk()
            phone = booking.get('phone', 'не указан')
            username = booking.get('username', '')
            user_link = f"@{username}" if username else "нет username"
            
            if booking["business_id"] == "clinic":
                branch = CLINIC_BRANCHES.get(booking.get("branch_id"), {})
                message = f"❌ *ОТМЕНА ЗАПИСИ*\n\n🆔 #{booking_id}\n⏰ Отменено: {now.strftime('%d.%m.%Y %H:%M')} (МСК)\n\n📅 Была запись: {booking['date']} в {booking['time']}\n🏢 {branch.get('name', '')}\n🩺 {booking['service_name']}\n👨‍⚕️ Врач: {booking['master_name']}\n\n👤 {booking.get('first_name', 'Пациент')}\n📱 {phone}\n💬 {user_link}"
            else:
                message = f"❌ *ОТМЕНА ЗАПИСИ*\n\n🆔 #{booking_id}\n⏰ Отменено: {now.strftime('%d.%m.%Y %H:%M')} (МСК)\n\n📅 Была запись: {booking['date']} в {booking['time']}\n✂️ {booking['service_name']}\n👨‍🦱 Мастер: {booking['master_name']}\n\n👤 {booking.get('first_name', 'Клиент')}\n📱 {phone}\n💬 {user_link}"
            
            try:
                await send_telegram_message(OWNERS.get(booking["business_id"], OWNERS["portos"]), message)
            except Exception as e:
                print(f"Failed to send cancel notification: {e}")
            return {"status": "cancelled"}
    raise HTTPException(status_code=404, detail="Запись не найдена")

# === ЧЕРНОВАР: Бронирование столиков ===

@app.post("/api/reservations")
async def create_reservation(res: CreateReservation):
    """Бронирование столика в ресторане"""
    reservations = load_json("reservations.json")
    if "items" not in reservations:
        reservations["items"] = []
    
    now = now_msk()
    res_id = f"RES{len(reservations['items']) + 1:05d}"
    
    res_data = {
        "reservation_id": res_id,
        "user_id": res.user_id,
        "username": res.username,
        "first_name": res.first_name,
        "business_id": res.business_id,
        "guest_name": res.guest_name,
        "guests": res.guests,
        "date": res.date,
        "time": res.time,
        "comment": res.comment,
        "phone": res.phone,
        "status": "confirmed",
        "created_at": now.isoformat()
    }
    reservations["items"].append(res_data)
    save_json("reservations.json", reservations)
    
    date_display = datetime.strptime(res.date, "%Y-%m-%d").strftime("%d.%m.%Y")
    username_text = f"\n💬 @{res.username}" if res.username else ""
    comment_text = f"\n📝 {res.comment}" if res.comment else ""
    
    message = f"🍽️ *НОВАЯ БРОНЬ #{res_id}*\n\n📅 {date_display} в {res.time}\n👥 Гостей: *{res.guests}*\n\n👤 На имя: *{res.guest_name}*\n📱 {res.phone or 'Нет телефона'}{username_text}{comment_text}"
    
    try:
        owner_ids = OWNERS.get(res.business_id, OWNERS.get("pink_purple", [736051965]))
        for owner_id in owner_ids:
            await send_telegram_message(owner_id, message)
    except Exception as e:
        print(f"Failed to send reservation notification: {e}")
    
    return {"reservation_id": res_id, "status": "confirmed"}

@app.get("/api/user/{user_id}/reservations")
def get_user_reservations(user_id: int):
    """Получить брони пользователя"""
    reservations = load_json("reservations.json")
    user_res = [r for r in reservations.get("items", []) if r.get("user_id") == user_id]
    
    now = now_msk()
    today = now.strftime("%Y-%m-%d")
    
    for r in user_res:
        r["is_past"] = r["date"] < today
    
    return sorted(user_res, key=lambda x: (x["date"], x["time"]), reverse=True)

@app.post("/api/reservations/{res_id}/cancel")
async def cancel_reservation(res_id: str, user_id: int):
    """Отмена брони"""
    reservations = load_json("reservations.json")
    for res in reservations.get("items", []):
        if res.get("reservation_id") == res_id and res.get("user_id") == user_id:
            res["status"] = "cancelled"
            save_json("reservations.json", reservations)
            
            now = now_msk()
            message = f"❌ *ОТМЕНА БРОНИ #{res_id}*\n\n⏰ Отменено: {now.strftime('%d.%m.%Y %H:%M')} (МСК)\n\n📅 Была бронь: {res['date']} в {res['time']}\n👥 Гостей: {res['guests']}\n👤 На имя: {res['guest_name']}\n📱 {res.get('phone', 'нет')}"
            
            try:
                owner_ids = OWNERS.get(res.get("business_id"), OWNERS.get("pink_purple", [736051965]))
                for owner_id in owner_ids:
                    await send_telegram_message(owner_id, message)
            except Exception as e:
                print(f"Failed to send cancel notification: {e}")
            
            return {"status": "cancelled"}
    
    raise HTTPException(status_code=404, detail="Бронь не найдена")

# === ГРУППОВЫЕ ЗАКАЗЫ ===

class GroupOrderItem(BaseModel):
    id: str
    name: str
    price: int
    qty: int

class GroupMember(BaseModel):
    user_id: int
    name: str
    items: List[GroupOrderItem] = []
    total: int = 0

class CreateGroupOrder(BaseModel):
    owner_id: int
    owner_name: str

class JoinGroupOrder(BaseModel):
    user_id: int
    user_name: str

class AddItemsToGroup(BaseModel):
    user_id: int
    items: List[GroupOrderItem]
    total: int

@app.post("/api/group-orders")
async def create_group_order(data: CreateGroupOrder):
    """Создать групповой заказ"""
    groups = load_json("group_orders.json")
    if "items" not in groups:
        groups["items"] = {}
    
    # Генерируем ID
    import random
    import string
    group_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    groups["items"][group_id] = {
        "id": group_id,
        "owner_id": data.owner_id,
        "owner_name": data.owner_name,
        "members": [
            {
                "user_id": data.owner_id,
                "name": data.owner_name,
                "items": [],
                "total": 0,
                "is_owner": True
            }
        ],
        "status": "open",
        "created_at": now_msk().isoformat()
    }
    
    save_json("group_orders.json", groups)
    return {"group_id": group_id}

@app.get("/api/group-orders/{group_id}")
async def get_group_order(group_id: str):
    """Получить групповой заказ"""
    groups = load_json("group_orders.json")
    group = groups.get("items", {}).get(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Групповой заказ не найден")
    return group

@app.post("/api/group-orders/{group_id}/join")
async def join_group_order(group_id: str, data: JoinGroupOrder):
    """Присоединиться к групповому заказу"""
    groups = load_json("group_orders.json")
    group = groups.get("items", {}).get(group_id)
    
    if not group:
        raise HTTPException(status_code=404, detail="Групповой заказ не найден")
    
    if group["status"] != "open":
        raise HTTPException(status_code=400, detail="Заказ уже закрыт")
    
    # Проверяем, не присоединился ли уже
    for member in group["members"]:
        if member["user_id"] == data.user_id:
            return {"status": "already_joined", "group": group}
    
    group["members"].append({
        "user_id": data.user_id,
        "name": data.user_name,
        "items": [],
        "total": 0,
        "is_owner": False
    })
    
    save_json("group_orders.json", groups)
    return {"status": "joined", "group": group}

@app.post("/api/group-orders/{group_id}/items")
async def add_items_to_group(group_id: str, data: AddItemsToGroup):
    """Добавить товары в групповой заказ"""
    groups = load_json("group_orders.json")
    group = groups.get("items", {}).get(group_id)
    
    if not group:
        raise HTTPException(status_code=404, detail="Групповой заказ не найден")
    
    if group["status"] != "open":
        raise HTTPException(status_code=400, detail="Заказ уже закрыт")
    
    for member in group["members"]:
        if member["user_id"] == data.user_id:
            member["items"] = [item.dict() for item in data.items]
            member["total"] = data.total
            break
    
    save_json("group_orders.json", groups)
    return {"status": "updated", "group": group}

@app.post("/api/group-orders/{group_id}/submit")
async def submit_group_order(group_id: str, user_id: int):
    """Оформить групповой заказ (только владелец)"""
    groups = load_json("group_orders.json")
    group = groups.get("items", {}).get(group_id)
    
    if not group:
        raise HTTPException(status_code=404, detail="Групповой заказ не найден")
    
    if group["owner_id"] != user_id:
        raise HTTPException(status_code=403, detail="Только организатор может оформить заказ")
    
    if group["status"] != "open":
        raise HTTPException(status_code=400, detail="Заказ уже оформлен")
    
    # Собираем все товары
    all_items = []
    grand_total = 0
    members_info = []
    
    for member in group["members"]:
        if member["items"]:
            members_info.append(f"{member['name']}: {member['total']}₽")
            grand_total += member["total"]
            for item in member["items"]:
                # Объединяем одинаковые товары
                existing = next((i for i in all_items if i["id"] == item["id"]), None)
                if existing:
                    existing["qty"] += item["qty"]
                else:
                    all_items.append(item.copy())
    
    if not all_items:
        raise HTTPException(status_code=400, detail="Корзина пуста")
    
    # Создаем обычный заказ
    orders = load_json("orders.json")
    if "items" not in orders:
        orders["items"] = []
    
    now = now_msk()
    order_id = f"GRP{len(orders['items']) + 1:05d}"
    
    order_data = {
        "order_id": order_id,
        "user_id": user_id,
        "business_id": "pink_purple",
        "items": all_items,
        "total": grand_total,
        "status": "new",
        "is_group_order": True,
        "group_id": group_id,
        "members_count": len([m for m in group["members"] if m["items"]]),
        "created_at": now.isoformat()
    }
    
    orders["items"].append(order_data)
    save_json("orders.json", orders)
    
    # Закрываем групповой заказ
    group["status"] = "completed"
    group["order_id"] = order_id
    save_json("group_orders.json", groups)
    
    # Отправляем уведомление владельцу бизнеса
    items_text = "\n".join([f"• {item['name']} x{item['qty']} — {item['price'] * item['qty']}₽" for item in all_items])
    members_text = "\n".join([f"👤 {m}" for m in members_info])
    
    message = f"🎉 *ГРУППОВОЙ ЗАКАЗ #{order_id}*\n\n📅 {now.strftime('%d.%m.%Y %H:%M')} (МСК)\n\n*Участники:*\n{members_text}\n\n*Заказ:*\n{items_text}\n\n💰 *Итого: {grand_total}₽*"
    
    try:
        await send_telegram_message(OWNERS.get("pink_purple"), message)
    except Exception as e:
        print(f"Failed to send group order notification: {e}")
    
    return {"order_id": order_id, "total": grand_total}

# === TELEGRAM PAYMENTS ===

class CreateInvoiceRequest(BaseModel):
    user_id: int
    title: str
    description: str
    amount: int  # в копейках/центах
    order_id: Optional[str] = None
    items: Optional[List[dict]] = None

@app.post("/api/payments/create-invoice")
async def create_invoice(data: CreateInvoiceRequest):
    """Создать инвойс для оплаты через Telegram Payments"""
    logger.info(f"Creating invoice: user={data.user_id}, amount={data.amount}, order={data.order_id}")
    
    if not PAYMENT_TOKEN:
        logger.error("Payment token not configured!")
        raise HTTPException(status_code=500, detail="Payment token not configured")
    
    # Формируем payload для отслеживания заказа
    payload = json.dumps({
        "order_id": data.order_id,
        "user_id": data.user_id,
        "amount": data.amount
    })
    
    logger.info(f"Calling Telegram API with token: {BOT_TOKEN[:20]}...")
    
    # Создаём инвойс через Telegram Bot API
    async with httpx.AsyncClient() as client:
        request_data = {
            "title": data.title,
            "description": data.description,
            "payload": payload,
            "provider_token": PAYMENT_TOKEN,
            "currency": "RUB",
            "prices": [
                {"label": data.title, "amount": data.amount}  # amount в копейках
            ]
        }
        logger.info(f"Request data: {request_data}")
        
        response = await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/createInvoiceLink",
            json=request_data
        )
        
        result = response.json()
        logger.info(f"Telegram API response: {result}")
        
        if result.get("ok"):
            return {"invoice_url": result["result"]}
        else:
            error_msg = result.get("description", "Failed to create invoice")
            logger.error(f"Invoice creation failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

@app.post("/api/payments/send-invoice")
async def send_invoice(data: CreateInvoiceRequest):
    """Отправить инвойс пользователю в чат (альтернативный метод)"""
    if not PAYMENT_TOKEN:
        raise HTTPException(status_code=500, detail="Payment token not configured")
    
    payload = json.dumps({
        "order_id": data.order_id,
        "user_id": data.user_id,
        "amount": data.amount
    })
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendInvoice",
            json={
                "chat_id": data.user_id,
                "title": data.title,
                "description": data.description,
                "payload": payload,
                "provider_token": PAYMENT_TOKEN,
                "currency": "RUB",
                "prices": [
                    {"label": data.title, "amount": data.amount}
                ],
                "start_parameter": f"pay_{data.order_id}" if data.order_id else "pay"
            }
        )
        
        result = response.json()
        if result.get("ok"):
            return {"success": True, "message_id": result["result"]["message_id"]}
        else:
            raise HTTPException(status_code=400, detail=result.get("description", "Failed to send invoice"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
