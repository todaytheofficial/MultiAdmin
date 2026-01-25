import os

# Токен бота
BOT_TOKEN = "8285867368:AAGZkS-hMQ-22WHCQkDzh8t0JF5aqssg5-g"

# Создатели бота
BOT_CREATORS = [
    "Idkkkkktd",
    "rumsfeldddd"
]

# Путь к папке с картинками карточек
CARDS_IMAGES_PATH = "cards_images"

# Premium эмодзи
EMOJI = {
    "fire": "🔥",
    "star": "⭐",
    "crown": "👑",
    "sword": "⚔️",
    "shield": "🛡️",
    "trophy": "🏆",
    "gem": "💎",
    "lightning": "⚡",
    "skull": "💀",
    "heart": "❤️‍🔥",
    "magic": "✨",
    "dragon": "🐉",
    "cool": "😎",
    "rage": "🤬",
    "win": "🎉",
    "lose": "😭",
    "card": "🃏",
    "spin": "🎰",
    "arena": "🏟️",
    "rating": "📊",
    "mute": "🔇",
    "ban": "🚫",
    "warn": "⚠️",
    "rules": "📜",
    "rank": "🎖️",
    "promote": "⬆️",
    "demote": "⬇️",
    "info": "ℹ️",
    "settings": "⚙️",
    "delete": "🗑️",
    "pin": "📌",
    "user": "👤",
    "admin": "👮",
    "mod": "🛡️",
    "time": "⏰",
    "check": "✅",
    "cross": "❌",
    "link": "🔗",
    "stats": "📈",
    "creator": "💠",
}

# Система рангов
RANKS = {
    0: {
        "name": "Участник",
        "emoji": "👤",
        "color": "⚪",
        "permissions": [],
        "description": "Обычный участник чата"
    },
    1: {
        "name": "Мл.Модератор",
        "emoji": "🔰",
        "color": "🟢",
        "permissions": ["mute", "warn", "delete_messages", "view_warns"],
        "description": "Младший модератор"
    },
    2: {
        "name": "Ст.Модератор",
        "emoji": "🛡️",
        "color": "🔵",
        "permissions": ["mute", "unmute", "warn", "unwarn", "delete_messages", "view_warns", "pin_messages", "slow_mode"],
        "description": "Старший модератор"
    },
    3: {
        "name": "Мл.Админ",
        "emoji": "⚔️",
        "color": "🟣",
        "permissions": ["mute", "unmute", "warn", "unwarn", "ban", "kick", "delete_messages", "view_warns", "pin_messages", "slow_mode", "set_rules", "invite_users"],
        "description": "Младший администратор"
    },
    4: {
        "name": "Гл.Админ",
        "emoji": "🔱",
        "color": "🟡",
        "permissions": ["mute", "unmute", "warn", "unwarn", "ban", "unban", "kick", "delete_messages", "view_warns", "pin_messages", "slow_mode", "set_rules", "invite_users", "promote_1", "promote_2", "change_info", "manage_voice"],
        "description": "Главный администратор"
    },
    5: {
        "name": "Со-Владелец",
        "emoji": "👑",
        "color": "🟠",
        "permissions": ["mute", "unmute", "warn", "unwarn", "ban", "unban", "kick", "delete_messages", "view_warns", "pin_messages", "slow_mode", "set_rules", "invite_users", "promote_1", "promote_2", "promote_3", "promote_4", "demote", "change_info", "manage_voice", "add_admins", "manage_chat"],
        "description": "Со-владелец"
    },
    6: {
        "name": "Владелец",
        "emoji": "🏆",
        "color": "🔴",
        "permissions": ["all"],
        "description": "Владелец чата"
    },
    99: {
        "name": "Создатель бота",
        "emoji": "💠",
        "color": "🔷",
        "permissions": ["all"],
        "description": "Создатель бота"
    },
}

# Описания прав
PERMISSION_DESCRIPTIONS = {
    "mute": "🔇 Мутить пользователей",
    "unmute": "🔊 Размучивать пользователей",
    "warn": "⚠️ Выдавать предупреждения",
    "unwarn": "✅ Снимать предупреждения",
    "ban": "🚫 Банить пользователей",
    "unban": "♻️ Разбанивать пользователей",
    "kick": "👢 Кикать пользователей",
    "delete_messages": "🗑️ Удалять сообщения",
    "view_warns": "👁️ Смотреть предупреждения",
    "pin_messages": "📌 Закреплять сообщения",
    "slow_mode": "🐌 Управлять медленным режимом",
    "set_rules": "📜 Устанавливать правила",
    "invite_users": "📨 Приглашать пользователей",
    "change_info": "✏️ Менять информацию чата",
    "manage_voice": "🎙️ Управлять голосовыми чатами",
    "add_admins": "👮 Добавлять админов Telegram",
    "manage_chat": "⚙️ Управлять настройками чата",
    "promote_1": "⬆️ Повышать до Мл.Модератора",
    "promote_2": "⬆️ Повышать до Ст.Модератора",
    "promote_3": "⬆️ Повышать до Мл.Админа",
    "promote_4": "⬆️ Повышать до Гл.Админа",
    "demote": "⬇️ Понижать пользователей",
    "all": "👑 ВСЕ ПРАВА",
}


# ================== КАРТОЧКИ JUJUTSU KAISEN ==================

CARDS = [
    # ============ COMMON (50% шанс) ============
    {
        "name": "Panda",
        "rarity": "common",
        "attack": 12,
        "defense": 14,
        "emoji": "🐼",
        "image": "Panda.png",  # Есть картинка
        "anime": "Jujutsu Kaisen",
        "description": "Проклятый труп, созданный Ягой"
    },
    {
        "name": "Kechizu",
        "rarity": "common",
        "attack": 10,
        "defense": 10,
        "emoji": "👹",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Младший из братьев Призрачной Утробы"
    },
    {
        "name": "Ui Ui",
        "rarity": "common",
        "attack": 8,
        "defense": 12,
        "emoji": "👦",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Младший брат Мэй Мэй"
    },
    {
        "name": "Mai Zenin",
        "rarity": "common",
        "attack": 11,
        "defense": 9,
        "emoji": "🔫",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Близнец Маки, владеет техникой Создания"
    },

    # ============ RARE (25% шанс) ============
    {
        "name": "Nobara",
        "rarity": "rare",
        "attack": 18,
        "defense": 14,
        "emoji": "🔨",
        "image": "Nobara.png",  # Есть картинка
        "anime": "Jujutsu Kaisen",
        "description": "Мастер техники Соломенной Куклы"
    },
    {
        "name": "Mei Mei",
        "rarity": "rare",
        "attack": 20,
        "defense": 16,
        "emoji": "🐦",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Маг 1-го класса, повелительница воронов"
    },
    {
        "name": "Naobito",
        "rarity": "rare",
        "attack": 22,
        "defense": 14,
        "emoji": "⚡",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Глава клана Дзэнин, мастер Проекции"
    },
    {
        "name": "Eso",
        "rarity": "rare",
        "attack": 19,
        "defense": 17,
        "emoji": "🩸",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Средний брат Призрачной Утробы"
    },

    # ============ EPIC (15% шанс) ============
    {
        "name": "Finger Bearer",
        "rarity": "epic",
        "attack": 28,
        "defense": 24,
        "emoji": "👆",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Проклятие, поглотившее палец Сукуны"
    },
    {
        "name": "Miguel",
        "rarity": "epic",
        "attack": 30,
        "defense": 22,
        "emoji": "⚔️",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Африканский маг с легендарной верёвкой"
    },
    {
        "name": "Megumi",
        "rarity": "epic",
        "attack": 32,
        "defense": 26,
        "emoji": "🐕",
        "image": "Megumi.png",  # Есть картинка
        "anime": "Jujutsu Kaisen",
        "description": "Наследник техники Десяти Теней"
    },
    {
        "name": "Dagon",
        "rarity": "epic",
        "attack": 35,
        "defense": 28,
        "emoji": "🐙",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Проклятие Особого класса, мастер воды"
    },
    {
        "name": "Naoya Zenin",
        "rarity": "epic",
        "attack": 33,
        "defense": 23,
        "emoji": "💨",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Наследник клана Дзэнин, техника Проекции"
    },
    {
        "name": "Choso",
        "rarity": "epic",
        "attack": 34,
        "defense": 27,
        "emoji": "🩸",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Старший брат Призрачной Утробы, мастер крови"
    },

    # ============ LEGENDARY (7% шанс) ============
    {
        "name": "Aoi Todo",
        "rarity": "legendary",
        "attack": 45,
        "defense": 38,
        "emoji": "👏",
        "image": "Aoi_Todo.png",  # Есть картинка
        "anime": "Jujutsu Kaisen",
        "description": "Мой лучший друг! Техника Буги-Вуги"
    },
    {
        "name": "Maki Zenin",
        "rarity": "legendary",
        "attack": 48,
        "defense": 35,
        "emoji": "🗡️",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Достигла уровня Тодзи, мастер оружия"
    },
    {
        "name": "Yuji Itadori",
        "rarity": "legendary",
        "attack": 50,
        "defense": 42,
        "emoji": "👊",
        "image": "Yuji_Itadori.png",  # Есть картинка
        "anime": "Jujutsu Kaisen",
        "description": "Сосуд Сукуны, мастер рукопашного боя"
    },
    {
        "name": "Nanami",
        "rarity": "legendary",
        "attack": 46,
        "defense": 40,
        "emoji": "📏",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Маг 1-го класса, техника Соотношения"
    },
    {
        "name": "Geto",
        "rarity": "legendary",
        "attack": 52,
        "defense": 44,
        "emoji": "👻",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Мастер техники Поглощения Проклятий"
    },
    {
        "name": "Jogo",
        "rarity": "legendary",
        "attack": 55,
        "defense": 38,
        "emoji": "🌋",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Проклятие Особого класса, повелитель огня"
    },
    {
        "name": "Yuki Tsukumo",
        "rarity": "legendary",
        "attack": 53,
        "defense": 45,
        "emoji": "⭐",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Один из 4-х Магов Особого класса"
    },

    # ============ MYTHIC (2.5% шанс) ============
    {
        "name": "Mahito",
        "rarity": "mythic",
        "attack": 62,
        "defense": 50,
        "emoji": "🎭",
        "image": "Mahito.png",  # Есть картинка
        "anime": "Jujutsu Kaisen",
        "description": "Проклятие, рождённое из ненависти людей"
    },
    {
        "name": "Sukuna",
        "rarity": "mythic",
        "attack": 75,
        "defense": 60,
        "emoji": "👹",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Король Проклятий, непревзойдённый"
    },
    {
        "name": "Meguna",
        "rarity": "mythic",
        "attack": 70,
        "defense": 58,
        "emoji": "😈",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Мегуми, захваченный Сукуной"
    },
    {
        "name": "Gojo Satoru",
        "rarity": "mythic",
        "attack": 80,
        "defense": 65,
        "emoji": "👁️",
        "image": "Gojo_Satoru.png",  # Есть картинка
        "anime": "Jujutsu Kaisen",
        "description": "Сильнейший маг современности, Безграничность"
    },
    {
        "name": "Shinjuku Yuji",
        "rarity": "mythic",
        "attack": 72,
        "defense": 55,
        "emoji": "🔥",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Юджи в финальной битве Синдзюку"
    },
    {
        "name": "Yuta Okkotsu",
        "rarity": "mythic",
        "attack": 78,
        "defense": 62,
        "emoji": "💀",
        "image": None,
        "anime": "Jujutsu Kaisen",
        "description": "Маг Особого класса, связанный с Рикой"
    },

    # ============ SPECIAL (0.5% шанс) ============
    {
        "name": "Gojo Tea",
        "rarity": "special",
        "attack": 85,
        "defense": 70,
        "emoji": "🍵",
        "image": None,
        "anime": "Idku Log",
        "description": "Чай - это наш всеми любимый СоВладелец моих проектов, она любит чай кстати!"
    },
    {
        "name": "Rumsukuna",
        "rarity": "special",
        "attack": 88,
        "defense": 72,
        "emoji": "🍺",
        "image": None,
        "anime": "Idku Log",
        "description": "Румс - Владелец канала RumteZz! Но его тело было захвачено Сукуной..."
    },
    {
        "name": "Idkyuji",
        "rarity": "special",
        "attack": 92,
        "defense": 78,
        "emoji": "💠",
        "image": None,
        "anime": "Idku Log",
        "description": "Создатель этого бота, Спасибо ему!"
    },
    {
        "name": "SaserHakari",
        "rarity": "special",
        "attack": 90,
        "defense": 75,
        "emoji": "🎰",
        "image": None,
        "anime": "Sasers Kaisen",
        "description": "Сасер лучший друг Арбуза и мой тоже! Он любит депать..."
    },
    {
        "name": "ArbuzMegumi",
        "rarity": "special",
        "attack": 86,
        "defense": 74,
        "emoji": "🍉",
        "image": None,
        "anime": "Arbuz Kaisen",
        "description": "Арбуз мой лучший дружбан и в целом он крутой, поиграйте как нибудь в его игру: Sword Fighting. Призывает вместо Махораги Деп Мобиль"
    },

    # Rare
    {"name": "Takuma Ino", "rarity": "rare", "attack": 19, "defense": 17, "emoji": "🦊", "image": None, "anime": "Jujutsu Kaisen"},

    # Legendary
    {"name": "Utahime Iori", "rarity": "legendary", "attack": 44, "defense": 41, "emoji": "🎤", "image": None, "anime": "Jujutsu Kaisen"},
    {"name": "Toge Inumaki", "rarity": "legendary", "attack": 47, "defense": 39, "emoji": "🍙", "image": None, "anime": "Jujutsu Kaisen"},
    {"name": "Hajime Kashimo", "rarity": "legendary", "attack": 51, "defense": 37, "emoji": "⚡", "image": None, "anime": "Jujutsu Kaisen"},

    # Mythic
    {"name": "Kinji Hakari", "rarity": "mythic", "attack": 76, "defense": 64, "emoji": "🎲", "image": None, "anime": "Jujutsu Kaisen"},
    {"name": "Mahoraga",     "rarity": "mythic", "attack": 82, "defense": 68, "emoji": "🗡️", "image": "Mahoraga.png", "anime": "Jujutsu Kaisen"},

    # MEGA (0.1%)
    {
        "name": "Heian Sukuna",
        "rarity": "mega",
        "attack": 105,
        "defense": 88,
        "emoji": "👑",
        "image": "Heian_Sukuna.png",          # ← только здесь картинка
        "anime": "Jujutsu Kaisen",
        "description": "Сукуна в своей истинной форме эпохи Хэйан — Король Проклятий в пике мощи"
    },
]

ALL_RARITIES = ["common", "rare", "epic", "legendary", "mythic", "special", "mega"]

RARITY_CHANCES = {
    "common":   40.0,
    "rare":     30.0,
    "epic":     10.0,
    "legendary": 2.0,
    "mythic":    0.9,
    "special":   0.25,
    "mega":      0.1,
}

RARITY_NAMES = {
    "common":    "⚪ Common",
    "rare":      "🔵 Rare",
    "epic":      "🟣 Epic",
    "legendary": "🟡 Legendary",
    "mythic":    "🔴 Mythic",
    "special":   "💎 Special",
    "mega":      "🌌 MEGA",
}

# Цвета редкостей
RARITY_COLORS = {
    "common": "⚪",
    "rare": "🔵",
    "epic": "🟣",
    "legendary": "🟡",
    "mythic": "🔴",
    "special": "💎",
    'mega': "🌌",
}

# Щиты для рынка (дорогие!)
SHIELDS = {
    "wooden":     {"name": "Деревянный щит",      "price": 180,  "block_chance": 18,  "damage_reduction": 25,  "emoji": "🪵🛡️"},
    "iron":       {"name": "Железный щит",        "price": 420,  "block_chance": 26,  "damage_reduction": 35,  "emoji": "⚒️🛡️"},
    "steel":      {"name": "Стальной щит",        "price": 950,  "block_chance": 34,  "damage_reduction": 45,  "emoji": "🛠️🛡️"},
    "cursed":     {"name": "Проклятый щит",       "price": 2400, "block_chance": 42,  "damage_reduction": 55,  "emoji": "🖤🛡️"},
    "divine":     {"name": "Божественный щит",    "price": 5800, "block_chance": 55,  "damage_reduction": 70,  "emoji": "✨🛡️"},
}