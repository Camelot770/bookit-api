# Конфигурация платформы
import os

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "7731397363:AAE7-L0anyBwzFmbYP_fYQnE2pP4SilBLPs")

# Платёжный токен ЮKassa (получить у @BotFather -> Payments)
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN", "390540012:LIVE:83691")

# URL Mini App (заполнится после деплоя фронтенда)
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-webapp.vercel.app")

# Настройки балльной системы
POINTS_PERCENT = 10
MAX_POINTS_USAGE_PERCENT = 50

# ===== БИЗНЕСЫ =====

BUSINESSES = {
    "pink_purple": {
        "id": "pink_purple",
        "name": "Pink Purple",
        "type": "cafe",
        "emoji": "🧋",
        "description": "Бабл ти, смузи и гонконгские вафли",
        "short_desc": "Бабл ти и вафли",
        "address": "г. Казань, ул. Бутлерова 45",
        "phone": "+7 (999) 123-45-67",
        "working_hours": "10:00 - 22:00",
        "owner_telegram_id": 736051965,
        "color": "#9C27B0",
        "gradient": "linear-gradient(135deg, #9C27B0 0%, #E91E63 100%)",
        "image": "/images/pink_purple.jpg",
    },
    "portos": {
        "id": "portos",
        "name": "PORTOS",
        "type": "barbershop",
        "emoji": "💈",
        "description": "Мужские стрижки, бритьё и уход за бородой",
        "short_desc": "Мужской барбершоп",
        "address": "г. Казань, ул. Баумана 52",
        "phone": "+7 (999) 765-43-21",
        "working_hours": "10:00 - 21:00",
        "owner_telegram_id": 736051965,
        "color": "#1a1a2e",
        "gradient": "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)",
        "image": "/images/portos.jpg",
    },
    "health_family": {
        "id": "health_family",
        "name": "Здоровье семьи",
        "type": "clinic",
        "emoji": "🏥",
        "description": "Сеть клиник — терапевты, кардиологи, неврологи и другие специалисты",
        "short_desc": "Сеть клиник",
        "address": "г. Казань",
        "phone": "+7 (999) 888-77-66",
        "working_hours": "08:00 - 20:00",
        "owner_telegram_id": 736051965,
        "color": "#00b894",
        "gradient": "linear-gradient(135deg, #00b894 0%, #00cec9 100%)",
        "image": "/images/clinic.jpg",
    }
}

# ===== МЕНЮ PINK PURPLE =====

PINK_PURPLE_MENU = {
    "top": {
        "name": "⭐ Наш топ",
        "emoji": "⭐",
        "items": [
            {"id": "pink_matcha_500", "name": "Пинк Матча", "volume": "500мл", "price": 459, "image": "/images/pink_matcha.jpg"},
            {"id": "pina_colada_500", "name": "Пина Колада", "volume": "500мл", "price": 399, "image": "/images/pina_colada.jpg"},
            {"id": "coco_pink_500", "name": "Коко Пинк", "volume": "500мл", "price": 499, "image": "/images/coco_pink.jpg"},
            {"id": "dubai_chocolate_500", "name": "Дубайский шоколад", "volume": "500мл", "price": 599, "image": "/images/dubai.jpg"},
        ]
    },
    "smoothie": {
        "name": "🥤 Смузи",
        "emoji": "🥤",
        "items": [
            {"id": "berry_smoothie", "name": "Ягодный", "volume": "500мл", "price": 489, "image": "/images/berry.jpg"},
            {"id": "mango_banana", "name": "Манго-Банан", "volume": "500мл", "price": 489, "image": "/images/mango.jpg"},
            {"id": "strawberry_banana", "name": "Клубника-Банан", "volume": "500мл", "price": 489, "image": "/images/strawberry.jpg"},
            {"id": "blueberry_banana", "name": "Черника-Банан", "volume": "500мл", "price": 489, "image": "/images/blueberry.jpg"},
        ]
    },
    "milky": {
        "name": "🥛 Милки",
        "emoji": "🥛",
        "items": [
            {"id": "original_milk_500", "name": "Милк Оригинал", "volume": "500мл", "price": 379, "image": "/images/milk.jpg"},
            {"id": "taro_milk_500", "name": "Таро Милк", "volume": "500мл", "price": 459, "image": "/images/taro.jpg"},
            {"id": "matcha_milk_500", "name": "Матча Милк", "volume": "500мл", "price": 459, "image": "/images/matcha_milk.jpg"},
        ]
    },
    "waffles": {
        "name": "🧇 Вафли",
        "emoji": "🧇",
        "items": [
            {"id": "chocolate_waffle", "name": "Шоколадная", "price": 449, "image": "/images/waffle1.jpg"},
            {"id": "nutella_waffle", "name": "Нутелла", "price": 489, "image": "/images/waffle2.jpg"},
            {"id": "oreo_waffle", "name": "Орео", "price": 509, "image": "/images/waffle3.jpg"},
        ]
    },
    "coffee": {
        "name": "☕ Кофе",
        "emoji": "☕",
        "items": [
            {"id": "cappuccino", "name": "Капучино", "price": 249, "image": "/images/cappuccino.jpg"},
            {"id": "latte", "name": "Латте", "price": 249, "image": "/images/latte.jpg"},
            {"id": "raf", "name": "Раф", "price": 279, "image": "/images/raf.jpg"},
        ]
    },
}

# ===== УСЛУГИ PORTOS =====

PORTOS_SERVICES = {
    "haircut": {
        "name": "✂️ Стрижки",
        "emoji": "✂️",
        "items": [
            {"id": "mens_haircut", "name": "Мужская стрижка", "price": 1200, "duration": 45, "image": "/images/haircut.jpg"},
            {"id": "kids_haircut", "name": "Детская стрижка", "desc": "до 12 лет", "price": 800, "duration": 30, "image": "/images/kids.jpg"},
            {"id": "buzz_cut", "name": "Под машинку", "price": 600, "duration": 20, "image": "/images/buzz.jpg"},
        ]
    },
    "beard": {
        "name": "🧔 Борода",
        "emoji": "🧔",
        "items": [
            {"id": "beard_trim", "name": "Моделирование бороды", "price": 700, "duration": 30, "image": "/images/beard.jpg"},
            {"id": "beard_shave", "name": "Королевское бритьё", "price": 900, "duration": 40, "image": "/images/shave.jpg"},
        ]
    },
    "combo": {
        "name": "🎯 Комбо",
        "emoji": "🎯",
        "items": [
            {"id": "haircut_beard", "name": "Стрижка + Борода", "price": 1700, "duration": 75, "popular": True, "image": "/images/combo.jpg"},
            {"id": "full_service", "name": "Полный уход", "desc": "стрижка + борода + укладка", "price": 2200, "duration": 90, "image": "/images/full.jpg"},
        ]
    },
}

# ===== МАСТЕРА PORTOS =====

PORTOS_MASTERS = [
    {"id": "artem", "name": "Артём", "rating": 4.9, "reviews": 142, "experience": "5 лет", "photo": "/images/artem.jpg", "specialization": "Классические стрижки"},
    {"id": "dmitry", "name": "Дмитрий", "rating": 4.8, "reviews": 98, "experience": "3 года", "photo": "/images/dmitry.jpg", "specialization": "Fade, андеркат"},
    {"id": "rustam", "name": "Рустам", "rating": 4.9, "reviews": 215, "experience": "7 лет", "photo": "/images/rustam.jpg", "specialization": "Борода и усы"},
    {"id": "vlad", "name": "Владислав", "rating": 4.7, "reviews": 64, "experience": "2 года", "photo": "/images/vlad.jpg", "specialization": "Креативные стрижки"},
]

# Слоты времени
WORKING_SLOTS = [
    "10:00", "10:30", "11:00", "11:30", "12:00", "12:30",
    "13:00", "13:30", "14:00", "14:30", "15:00", "15:30",
    "16:00", "16:30", "17:00", "17:30", "18:00", "18:30",
    "19:00", "19:30", "20:00", "20:30"
]
