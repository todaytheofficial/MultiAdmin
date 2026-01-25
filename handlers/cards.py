import random
import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, ChatMemberOwner
from aiogram.filters import Command

from config import EMOJI, CARDS, RARITY_CHANCES, RARITY_NAMES, RARITY_COLORS, CARDS_IMAGES_PATH, BOT_CREATORS
from database import DatabaseManager

router = Router()

Coins_reward = {
    "common": (1, 3),
    "rare": (3, 6),
    "epic": (6, 12),
    "legendary": (12, 25),
    "mythic": (25, 50),
    "special": (50, 100),
}


def get_coin_reward(rarity: str) -> int:
    min_coins, max_coins = Coins_reward.get(rarity, (1, 3))
    return random.randint(min_coins, max_coins)


def get_random_card(boost_multiplier: float = 1.0) -> dict:
    # Применяем буст к шансам получения карт
    adjusted_chances = {}
    for rarity, chance in RARITY_CHANCES.items():
        # Увеличиваем шанс получения более редких карт
        if rarity in ["special", "mythic", "legendary"]:
            adjusted_chances[rarity] = min(100.0, chance * boost_multiplier)
        else:
            adjusted_chances[rarity] = chance
    
    roll = random.uniform(0, 100)
    cumulative = 0
    selected_rarity = "common"
    
    for rarity in ["special", "mythic", "legendary", "epic", "rare", "common"]:
        cumulative += adjusted_chances.get(rarity, 0)
        if roll <= cumulative:
            selected_rarity = rarity
            break
    
    available = [c for c in CARDS if c["rarity"] == selected_rarity]
    if not available:
        available = [c for c in CARDS if c["rarity"] == "common"]
    
    return random.choice(available)


def find_card_by_name(name: str) -> dict | None:
    name_lower = name.lower().strip()
    for card in CARDS:
        if card["name"].lower() == name_lower:
            return card
    return None


def format_card(card: dict, show_details: bool = True) -> str:
    rarity_display = RARITY_NAMES.get(card["rarity"], card["rarity"])
    power = card["attack"] + card["defense"]
    
    text = f"{card['emoji']} <b>{card['name']}</b>\n"
    text += f"├ {rarity_display}\n"
    text += f"├ ⚔️ Атака: <b>{card['attack']}</b>\n"
    text += f"├ 🛡️ Защита: <b>{card['defense']}</b>\n"
    text += f"└ 💪 Сила: <b>{power}</b>"
    
    if show_details:
        if card.get("anime"):
            text += f"\n\n🎬 <i>{card['anime']}</i>"
        if card.get("description"):
            text += f"\n📝 <i>{card['description']}</i>"
    
    return text


def get_card_image_path(card: dict) -> str | None:
    if not card.get("image"):
        return None
    image_path = os.path.join(CARDS_IMAGES_PATH, card["image"])
    if os.path.exists(image_path):
        return image_path
    return None


async def send_card(message: Message, card: dict, caption: str, reply: bool = False):
    """Отправить карточку с картинкой или без"""
    image_path = get_card_image_path(card)
    
    if image_path:
        try:
            photo = FSInputFile(image_path)
            if reply:
                try:
                    await message.reply_photo(photo=photo, caption=caption, parse_mode="HTML")
                except:
                    await message.answer_photo(photo=photo, caption=caption, parse_mode="HTML")
            else:
                await message.answer_photo(photo=photo, caption=caption, parse_mode="HTML")
            return
        except Exception as e:
            print(f"Ошибка отправки изображения: {e}")
    
    # Если картинка не отправилась или её нет - отправляем текст
    if reply:
        try:
            await message.reply(caption, parse_mode="HTML")
        except:
            await message.answer(caption, parse_mode="HTML")
    else:
        await message.answer(caption, parse_mode="HTML")


async def is_owner_or_creator(message: Message, bot: Bot) -> bool:
    if message.from_user.username in BOT_CREATORS:
        return True
    
    if message.chat.type in ["group", "supergroup"]:
        try:
            member = await bot.get_chat_member(message.chat.id, message.from_user.id)
            if isinstance(member, ChatMemberOwner):
                return True
        except:
            pass
    
    return False


def is_group_chat(message: Message) -> bool:
    return message.chat.type in ["group", "supergroup"]


def get_db(message: Message):
    """Получить БД для текущего чата"""
    return DatabaseManager.get_db(message.chat.id)


async def get_target_user(message: Message, bot: Bot) -> tuple:
    """Получить цель из реплая или @username"""
    args = message.text.split()
    db = get_db(message)
    global_db = DatabaseManager.get_global_db()
    
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        return target.id, target.first_name, target.username, None
    
    if len(args) > 1:
        arg = args[1]
        
        if arg.startswith("@"):
            username = arg[1:]
            # Ищем в глобальной БД
            user_data = global_db.find_by_username(username)
            if user_data:
                return user_data['user_id'], user_data.get('first_name') or username, username, None
            return None, None, None, f"@{username} не найден!"
        
        elif arg.isdigit():
            user_id = int(arg)
            user = db.get_user(user_id)
            if user:
                return user_id, user.get("first_name", str(user_id)), user.get("username"), None
            return user_id, str(user_id), None, None
    
    return message.from_user.id, message.from_user.first_name, message.from_user.username, None


# ================== КОМАНДА ПОЛУЧЕНИЯ БИЛЕТА ==================

@router.message(Command("ticket"))
@router.message(Command("getticket"))
async def get_free_ticket(message: Message):
    """Получить бесплатный билет раз в 30 минут"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    user_id = message.from_user.id
    db = get_db(message)
    
    if not db.get_user(user_id):
        db.create_user(user_id, message.from_user.username, message.from_user.first_name)
    
    # Обновляем глобальную БД
    DatabaseManager.get_global_db().update_user(
        user_id, message.from_user.username, message.from_user.first_name
    )
    
    can_get, remaining = db.check_and_give_free_ticket(user_id)
    
    if can_get:
        tickets = db.get_spin_tickets(user_id)
        await message.reply(
            f"🎫 <b>Билет получен!</b>\n\n"
            f"🎟️ У тебя билетов: <b>{tickets}</b>\n\n"
            f"💡 Используй /spin для прокрутки",
            parse_mode="HTML"
        )
    else:
        tickets = db.get_spin_tickets(user_id)
        await message.reply(
            f"⏰ <b>Подожди!</b>\n\n"
            f"Следующий бесплатный билет через: <b>{remaining}</b> мин.\n\n"
            f"🎟️ У тебя билетов: <b>{tickets}</b>",
            parse_mode="HTML"
        )


@router.message(Command("tickets"))
async def show_tickets(message: Message):
    """Показать количество билетов"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    user_id = message.from_user.id
    db = get_db(message)
    
    if not db.get_user(user_id):
        db.create_user(user_id, message.from_user.username, message.from_user.first_name)
    
    tickets = db.get_spin_tickets(user_id)
    remaining = db.get_time_until_free_ticket(user_id)
    
    text = f"🎟️ <b>Твои билеты</b>\n\n"
    text += f"🎫 Билетов: <b>{tickets}</b>\n\n"
    
    if remaining > 0:
        text += f"⏰ Бесплатный билет через: <b>{remaining}</b> мин.\n"
    else:
        text += f"✅ Можешь получить бесплатный билет! /ticket\n"
    
    text += f"\n💡 /spin — использовать билет"
    
    await message.reply(text, parse_mode="HTML")


# ================== ВЫДАЧА БИЛЕТОВ (АДМИН) ==================

@router.message(Command("givetickets"))
@router.message(Command("giveticket"))
async def give_tickets(message: Message, bot: Bot):
    """Выдать билеты пользователю"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    if not await is_owner_or_creator(message, bot):
        return await message.reply(f"{EMOJI['cross']} Только владелец группы или создатель бота!")
    
    args = message.text.split()
    db = get_db(message)
    
    # Парсим аргументы
    target_id = None
    first_name = None
    username = None
    amount = 1
    
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        target_id = target.id
        first_name = target.first_name
        username = target.username
        
        if len(args) > 1:
            try:
                amount = int(args[1])
            except:
                amount = 1
    else:
        if len(args) < 2:
            return await message.reply(
                f"🎫 <b>Выдача билетов</b>\n\n"
                f"<code>/givetickets @user [кол-во]</code>\n"
                f"<code>/givetickets [кол-во]</code> (реплай)\n\n"
                f"<b>Примеры:</b>\n"
                f"<code>/givetickets @user 5</code>\n"
                f"<code>/givetickets 10</code> (реплай)",
                parse_mode="HTML"
            )
        
        if args[1].startswith("@"):
            # @username
            global_db = DatabaseManager.get_global_db()
            user_data = global_db.find_by_username(args[1][1:])
            if not user_data:
                return await message.reply(f"{EMOJI['cross']} Пользователь не найден!")
            target_id = user_data['user_id']
            first_name = user_data.get('first_name', args[1])
            username = args[1][1:]
            
            if len(args) > 2:
                try:
                    amount = int(args[2])
                except:
                    amount = 1
        elif args[1].isdigit():
            # Это может быть ID или количество
            if len(args) > 2:
                # Первый аргумент - ID
                target_id = int(args[1])
                first_name = str(target_id)
                try:
                    amount = int(args[2])
                except:
                    amount = 1
            else:
                return await message.reply(
                    f"{EMOJI['cross']} Укажи @username или ответь на сообщение",
                    parse_mode="HTML"
                )
    
    if not target_id:
        return await message.reply(f"{EMOJI['cross']} Не удалось определить пользователя!")
    
    amount = max(1, min(100, amount))
    
    # Создаём юзера если нет
    if not db.get_user(target_id):
        db.create_user(target_id, username, first_name)
    
    db.add_spin_tickets(target_id, amount)
    new_tickets = db.get_spin_tickets(target_id)
    
    mention = f'<a href="tg://user?id={target_id}">{first_name}</a>'
    
    await message.reply(
        f"🎫 <b>Билеты выданы!</b>\n\n"
        f"👤 {mention}\n"
        f"➕ Выдано: <b>{amount}</b> билетов\n"
        f"🎟️ Всего: <b>{new_tickets}</b>\n\n"
        f"👮 Выдал: {message.from_user.mention_html()}",
        parse_mode="HTML"
    )


# ================== SPIN С БИЛЕТАМИ ==================

@router.message(Command("spin"))
async def spin_card(message: Message):
    """Использовать билет для прокрутки"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    user_id = message.from_user.id
    db = get_db(message)
    
    if not db.get_user(user_id):
        db.create_user(user_id, message.from_user.username, message.from_user.first_name)
    
    # Обновляем глобальную БД
    DatabaseManager.get_global_db().update_user(
        user_id, message.from_user.username, message.from_user.first_name
    )
    
    # Получаем буст шанса спина
    global_db = DatabaseManager.get_global_db()
    spin_boost = global_db.get_spin_boost(user_id)
    
    # Проверяем билеты
    tickets = db.get_spin_tickets(user_id)
    
    if tickets <= 0:
        remaining = db.get_time_until_free_ticket(user_id)
        if remaining > 0:
            return await message.reply(
                f"🎟️ <b>Нет билетов!</b>\n\n"
                f"⏰ Бесплатный билет через: <b>{remaining}</b> мин.\n\n"
                f"💡 Или попроси админа выдать билеты",
                parse_mode="HTML"
            )
        else:
            # Можно получить бесплатный
            return await message.reply(
                f"🎟️ <b>Нет билетов!</b>\n\n"
                f"✅ Но можешь получить бесплатный: /ticket",
                parse_mode="HTML"
            )
    
    # Используем билет
    if not db.use_spin_ticket(user_id):
        return await message.reply(f"{EMOJI['cross']} Ошибка использования билета!")
    
    card = get_random_card(spin_boost)
    
    user = db.get_user(user_id)
    user_cards = user.get("cards", [])
    is_duplicate = any(c["name"] == card["name"] for c in user_cards)
    
    card_to_save = {
        "name": card["name"],
        "rarity": card["rarity"],
        "attack": card["attack"],
        "defense": card["defense"],
        "emoji": card["emoji"]
    }
    db.add_card(user_id, card_to_save)
    
    # Монеты
    coins_earned = get_coin_reward(card["rarity"])
    if is_duplicate:
        coins_earned += coins_earned // 2
    db.add_coins(user_id, coins_earned)
    
    # Оставшиеся билеты
    remaining_tickets = db.get_spin_tickets(user_id)
    
    headers = {
        "special": "💎💎💎 <b>SPECIAL!!!</b> 💎💎💎\n\n",
        "mythic": "🔴🔴🔴 <b>MYTHIC!!</b> 🔴🔴🔴\n\n",
        "legendary": "🟡🟡🟡 <b>LEGENDARY!</b> 🟡🟡🟡\n\n",
        "epic": "🟣🟣 <b>EPIC!</b> 🟣🟣\n\n",
        "rare": "🔵 <b>RARE!</b> 🔵\n\n",
        "common": "🎰 <b>Прокрутка!</b>\n\n",
    }
    
    header = headers.get(card["rarity"], headers["common"])
    caption = header + format_card(card)
    
    caption += f"\n\n🪙 <b>+{coins_earned}</b> монет"
    if is_duplicate:
        caption += f" <i>(+бонус за дубликат!)</i>"
    
    # Показываем буст, если он есть
    if spin_boost > 1.0:
        caption += f"\n✨ Буст шанса: x{spin_boost}"
    
    caption += f"\n🎟️ Билетов: <b>{remaining_tickets}</b>"
    
    await send_card(message, card, caption)


# ================== СБРОС КД (переделан) ==================

@router.message(Command("resetcd"))
async def reset_cooldown(message: Message, bot: Bot):
    """Сбросить время получения бесплатного билета"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    if not await is_owner_or_creator(message, bot):
        return await message.reply(f"{EMOJI['cross']} Только владелец группы или создатель бота!")
    
    target_id, first_name, username, error = await get_target_user(message, bot)
    
    if error:
        return await message.reply(f"{EMOJI['cross']} {error}")
    
    db = get_db(message)
    
    if not db.get_user(target_id):
        return await message.reply(f"{EMOJI['cross']} Пользователь не найден в базе!")
    
    # Сбрасываем время бесплатного билета
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET last_free_ticket = NULL WHERE user_id = ?', (target_id,))
    conn.commit()
    conn.close()
    
    mention = f'<a href="tg://user?id={target_id}">{first_name}</a>'
    
    await message.reply(
        f"{EMOJI['check']} <b>Время сброшено!</b>\n\n"
        f"👤 {mention} может получить бесплатный билет через /ticket",
        parse_mode="HTML"
    )


# ================== TOP (с учётом группы) ==================

@router.message(Command("top"))
async def show_top_menu(message: Message):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🃏 У кого больше карт", callback_data="top_cards")],
        [InlineKeyboardButton(text="🪙 У кого больше монет", callback_data="top_coins")],
        [InlineKeyboardButton(text="💪 Самые сильные карты", callback_data="top_power")],
        [InlineKeyboardButton(text="⚔️ Лучшие бойцы арены", callback_data="top_arena")],
    ])
    
    await message.reply(
        f"🏆 <b>РЕЙТИНГИ</b>\n\n"
        f"Выбери что посмотреть:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "top_cards")
async def top_by_cards(callback: CallbackQuery):
    db = DatabaseManager.get_db(callback.message.chat.id)
    top_users = db.get_top_by_cards(10)
    
    if not top_users:
        await callback.answer("Пока никто не собрал карты!", show_alert=True)
        return
    
    text = f"🃏 <b>У КОГО БОЛЬШЕ КАРТ</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for i, user in enumerate(top_users):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = user.get("first_name") or user.get("username") or "Аноним"
        cards_count = user.get("cards_count", 0)
        unique_count = user.get("unique_count", 0)
        text += f"{medal} <b>{name}</b> — {cards_count} карт ({unique_count} разных)\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="top_menu")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "top_coins")
async def top_by_coins(callback: CallbackQuery):
    db = DatabaseManager.get_db(callback.message.chat.id)
    top_users = db.get_top_by_coins(10)
    
    if not top_users:
        await callback.answer("Пока никто не заработал монеты!", show_alert=True)
        return
    
    text = f"🪙 <b>У КОГО БОЛЬШЕ МОНЕТ</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for i, user in enumerate(top_users):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = user.get("first_name") or user.get("username") or "Аноним"
        coins = user.get("coins", 0)
        text += f"{medal} <b>{name}</b> — {coins} 🪙\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="top_menu")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "top_power")
async def top_by_power(callback: CallbackQuery):
    sorted_cards = sorted(CARDS, key=lambda x: x["attack"] + x["defense"], reverse=True)[:10]
    
    text = f"💪 <b>САМЫЕ СИЛЬНЫЕ КАРТЫ</b>\n\n"
    text += f"<i>Это карты которые можно выбить в /spin</i>\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, card in enumerate(sorted_cards):
        medal = medals[i] if i < 3 else f"{i+1}."
        power = card["attack"] + card["defense"]
        rarity_color = RARITY_COLORS.get(card["rarity"], "⚪")
        text += f"{medal} {card['emoji']} <b>{card['name']}</b>\n"
        text += f"     {rarity_color} ⚔️{card['attack']} 🛡️{card['defense']} = 💪{power}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="top_menu")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "top_arena")
async def top_arena(callback: CallbackQuery):
    db = DatabaseManager.get_db(callback.message.chat.id)
    top_players = db.get_top_players(10)
    
    if not top_players:
        await callback.answer("Ещё никто не сражался на арене!", show_alert=True)
        return
    
    text = f"⚔️ <b>ЛУЧШИЕ БОЙЦЫ АРЕНЫ</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for i, player in enumerate(top_players):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = player.get("first_name") or player.get("username") or "Аноним"
        rating = player.get("rating", 0)
        wins = player.get("wins", 0)
        losses = player.get("losses", 0)
        text += f"{medal} <b>{name}</b>\n"
        text += f"     ⭐{rating} очков | ✅{wins} побед | ❌{losses} поражений\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="top_menu")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "top_menu")
async def back_to_top_menu(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🃏 У кого больше карт", callback_data="top_cards")],
        [InlineKeyboardButton(text="🪙 У кого больше монет", callback_data="top_coins")],
        [InlineKeyboardButton(text="💪 Самые сильные карты", callback_data="top_power")],
        [InlineKeyboardButton(text="⚔️ Лучшие бойцы арены", callback_data="top_arena")],
    ])
    
    await callback.message.edit_text(
        f"🏆 <b>РЕЙТИНГИ</b>\n\nВыбери что посмотреть:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


# ================== ОСТАЛЬНЫЕ КОМАНДЫ ==================

@router.message(Command("mycards"))
async def my_cards(message: Message):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    user_id = message.from_user.id
    db = get_db(message)
    user = db.get_user(user_id)
    
    if not user or not user.get("cards"):
        return await message.reply(
            f"{EMOJI['card']} У тебя пока нет карточек!\n"
            f"/ticket — получить билет\n"
            f"/spin — получить карту!",
            parse_mode="HTML"
        )
    
    cards = user["cards"]
    
    unique_cards = {}
    for card in cards:
        key = card["name"]
        if key not in unique_cards:
            unique_cards[key] = {"card": card, "count": 0}
        unique_cards[key]["count"] += 1
    
    rarity_order = {"special": 0, "mythic": 1, "legendary": 2, "epic": 3, "rare": 4, "common": 5}
    sorted_cards = sorted(
        unique_cards.values(),
        key=lambda x: (rarity_order.get(x["card"]["rarity"], 99), -(x["card"]["attack"] + x["card"]["defense"]))
    )
    
    text = f"{EMOJI['card']} <b>Твои карточки ({len(cards)}):</b>\n\n"
    
    for item in sorted_cards[:25]:
        card = item["card"]
        count = item["count"]
        rarity_color = RARITY_COLORS.get(card["rarity"], "⚪")
        dupe = f" x{count}" if count > 1 else ""
        power = card["attack"] + card["defense"]
        text += f"{rarity_color} {card['emoji']} <b>{card['name']}</b> (💪{power}){dupe}\n"
    
    if len(sorted_cards) > 25:
        text += f"\n<i>...и ещё {len(sorted_cards) - 25}</i>"
    
    text += f"\n\n💡 /card [название] — подробнее"
    
    await message.reply(text, parse_mode="HTML")


@router.message(Command("card"))
async def show_card(message: Message):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        return await message.reply(
            f"{EMOJI['info']} <code>/card название</code>\n"
            f"Пример: <code>/card Gojo Satoru</code>",
            parse_mode="HTML"
        )
    
    card_name = args[1].strip()
    db = get_db(message)
    user = db.get_user(message.from_user.id)
    
    found_card = find_card_by_name(card_name)
    
    if not found_card:
        card_name_lower = card_name.lower()
        for c in CARDS:
            if card_name_lower in c["name"].lower():
                found_card = c
                break
    
    if not found_card:
        return await message.reply(
            f"{EMOJI['cross']} Карта не найдена!\n/cards — список",
            parse_mode="HTML"
        )
    
    count = 0
    if user and user.get("cards"):
        count = sum(1 for c in user["cards"] if c["name"] == found_card["name"])
    
    caption = f"{EMOJI['gem']} <b>Информация о карте</b>\n\n"
    caption += format_card(found_card, show_details=True)
    caption += f"\n\n📦 У тебя: <b>{count}</b> шт."
    
    await send_card(message, found_card, caption)


@router.message(Command("cards"))
@router.message(Command("allcards"))
async def all_cards(message: Message):
    text = f"{EMOJI['card']} <b>ВСЕ КАРТЫ ({len(CARDS)})</b>\n\n"
    
    for rarity in ["special", "mythic", "legendary", "epic", "rare", "common"]:
        cards_list = [c for c in CARDS if c["rarity"] == rarity]
        if cards_list:
            chance = RARITY_CHANCES.get(rarity, 0)
            text += f"<b>{RARITY_NAMES[rarity]}</b> ({chance}%):\n"
            
            for card in sorted(cards_list, key=lambda x: -(x["attack"] + x["defense"])):
                power = card["attack"] + card["defense"]
                img = "🖼" if card.get("image") else ""
                text += f"  {card['emoji']} {card['name']} (💪{power}) {img}\n"
            text += "\n"
    
    text += f"🖼 = есть картинка"
    
    await message.reply(text, parse_mode="HTML")


@router.message(Command("collection"))
async def collection_stats(message: Message):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    db = get_db(message)
    user = db.get_user(message.from_user.id)
    
    if not user:
        return await message.reply(f"{EMOJI['card']} Сначала /spin!")
    
    cards = user.get("cards", [])
    total_cards = len(CARDS)
    
    unique_names = set(c["name"] for c in cards)
    
    all_rarities = ["special", "mythic", "legendary", "epic", "rare", "common"]
    
    user_by_rarity = {r: 0 for r in all_rarities}
    for card in cards:
        user_by_rarity[card["rarity"]] = user_by_rarity.get(card["rarity"], 0) + 1
    
    total_by_rarity = {r: 0 for r in all_rarities}
    for card in CARDS:
        total_by_rarity[card["rarity"]] += 1
    
    unique_by_rarity = {r: 0 for r in all_rarities}
    for name in unique_names:
        for card in CARDS:
            if card["name"] == name:
                unique_by_rarity[card["rarity"]] += 1
                break
    
    progress = len(unique_names) / total_cards * 100 if total_cards > 0 else 0
    
    text = f"{EMOJI['trophy']} <b>КОЛЛЕКЦИЯ</b>\n\n"
    text += f"📊 Прогресс: <b>{len(unique_names)}/{total_cards}</b> ({progress:.1f}%)\n"
    text += f"📦 Всего карт: <b>{len(cards)}</b>\n\n"
    
    text += "<b>По редкости:</b>\n"
    for rarity in all_rarities:
        if total_by_rarity[rarity] > 0:
            color = RARITY_COLORS[rarity]
            unique = unique_by_rarity[rarity]
            total = total_by_rarity[rarity]
            count = user_by_rarity[rarity]
            text += f"{color} {unique}/{total} уник. ({count} шт.)\n"
    
    if cards:
        best = max(cards, key=lambda x: x["attack"] + x["defense"])
        power = best["attack"] + best["defense"]
        text += f"\n👑 <b>Лучшая:</b> {best['emoji']} {best['name']} (💪{power})"
    
    await message.reply(text, parse_mode="HTML")


@router.message(Command("topcards"))
async def top_cards(message: Message):
    sorted_cards = sorted(CARDS, key=lambda x: x["attack"] + x["defense"], reverse=True)[:10]
    
    text = f"{EMOJI['trophy']} <b>ТОП-10 СИЛЬНЕЙШИХ КАРТ</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for i, card in enumerate(sorted_cards):
        medal = medals[i] if i < 3 else f"{i+1}."
        power = card["attack"] + card["defense"]
        rarity_color = RARITY_COLORS[card["rarity"]]
        text += f"{medal} {rarity_color} {card['emoji']} <b>{card['name']}</b>\n"
        text += f"    ⚔️{card['attack']} 🛡️{card['defense']} = 💪{power}\n"
    
    await message.reply(text, parse_mode="HTML")


@router.message(Command("balance"))
@router.message(Command("coins"))
@router.message(Command("bal"))
async def show_balance(message: Message):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    user_id = message.from_user.id
    db = get_db(message)
    
    if not db.get_user(user_id):
        db.create_user(user_id, message.from_user.username, message.from_user.first_name)
    
    user = db.get_user(user_id)
    coins = user.get("coins", 0)
    cards_count = len(user.get("cards", []))
    tickets = db.get_spin_tickets(user_id)
    
    await message.reply(
        f"💰 <b>Баланс</b>\n\n"
        f"👤 {message.from_user.first_name}\n"
        f"🪙 Монеты: <b>{coins}</b>\n"
        f"🃏 Карт: <b>{cards_count}</b>\n"
        f"🎟️ Билетов: <b>{tickets}</b>\n\n"
        f"<i>Монеты получаются за прокрутку карт!</i>",
        parse_mode="HTML"
    )


# ================== GIVECARD (с учётом группы) ==================

async def get_target_for_givecard(message: Message, bot: Bot) -> tuple:
    args = message.text.split()
    global_db = DatabaseManager.get_global_db()
    
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        card_name = " ".join(args[1:]) if len(args) > 1 else None
        return target.id, target.first_name, target.username, card_name, None
    
    if len(args) > 1:
        first_arg = args[1]
        
        if first_arg.startswith("@"):
            username = first_arg[1:]
            user_data = global_db.find_by_username(username)
            if user_data:
                card_name = " ".join(args[2:]) if len(args) > 2 else None
                return user_data['user_id'], user_data.get('first_name') or username, username, card_name, None
            else:
                return None, None, None, None, f"@{username} не найден!"
        
        elif first_arg.isdigit():
            user_id = int(first_arg)
            card_name = " ".join(args[2:]) if len(args) > 2 else None
            return user_id, str(user_id), None, card_name, None
        
        else:
            card_name = " ".join(args[1:])
            return message.from_user.id, message.from_user.first_name, message.from_user.username, card_name, None
    
    return None, None, None, None, "Укажи название карты!"


@router.message(Command("givecard"))
async def give_card(message: Message, bot: Bot):
    """Выдать карту пользователю"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    if not await is_owner_or_creator(message, bot):
        return await message.reply(f"{EMOJI['cross']} Только владелец группы или создатель бота!")
    
    target_id, first_name, username, card_name, error = await get_target_for_givecard(message, bot)
    
    if error:
        return await message.reply(f"{EMOJI['cross']} {error}")
    
    if not card_name:
        text = f"{EMOJI['card']} <b>Выдача карты</b>\n\n"
        text += f"<code>/givecard [карта]</code> — себе\n"
        text += f"<code>/givecard @user [карта]</code>\n\n"
        text += f"<b>Карты:</b>\n"
        
        for rarity in ["special", "mythic", "legendary", "epic", "rare", "common"]:
            cards_of_rarity = [c for c in CARDS if c["rarity"] == rarity]
            if cards_of_rarity:
                text += f"\n{RARITY_NAMES[rarity]}:\n"
                for c in cards_of_rarity:
                    text += f"  {c['emoji']} {c['name']}\n"
        
        return await message.reply(text, parse_mode="HTML")
    
    card = find_card_by_name(card_name)
    
    if not card:
        card_name_lower = card_name.lower()
        for c in CARDS:
            if card_name_lower in c["name"].lower():
                card = c
                break
    
    if not card:
        return await message.reply(
            f"{EMOJI['cross']} Карта '<b>{card_name}</b>' не найдена!\n/cards — список",
            parse_mode="HTML"
        )
    
    db = get_db(message)
    
    if not db.get_user(target_id):
        db.create_user(target_id, username, first_name)
    
    card_to_save = {
        "name": card["name"],
        "rarity": card["rarity"],
        "attack": card["attack"],
        "defense": card["defense"],
        "emoji": card["emoji"]
    }
    db.add_card(target_id, card_to_save)
    
    mention = f'<a href="tg://user?id={target_id}">{first_name}</a>'
    
    caption = (
        f"🎁 <b>КАРТА ВЫДАНА!</b>\n\n"
        f"👤 Получатель: {mention}\n"
        f"👮 Выдал: {message.from_user.mention_html()}\n\n"
        f"{format_card(card)}"
    )
    
    await send_card(message, card, caption)


@router.message(Command("boostspin"))
async def boost_spin(message: Message, bot: Bot):
    """Выдать буст шанса спина пользователю"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    if not await is_owner_or_creator(message, bot):
        return await message.reply(f"{EMOJI['cross']} Только владелец группы или создатель бота!")
    
    args = message.text.split()
    
    # Парсим аргументы
    target_id = None
    first_name = None
    username = None
    multiplier = 2.0  # По умолчанию 2x буст
    duration = 24  # По умолчанию 24 часа
    
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        target_id = target.id
        first_name = target.first_name
        username = target.username
        
        # Проверяем дополнительные аргументы
        if len(args) > 1:
            try:
                multiplier = float(args[1])
            except:
                pass
                
        if len(args) > 2:
            try:
                duration = int(args[2])
            except:
                pass
    else:
        if len(args) < 2:
            return await message.reply(
                f"✨ <b>Буст шанса спина</b>\n\n"
                f"<code>/boostspin @user [множитель] [часы]</code>\n"
                f"<code>/boostspin [множитель] [часы]</code> (реплай)\n\n"
                f"<b>Примеры:</b>\n"
                f"<code>/boostspin @user 2.5 48</code> — 2.5x буст на 48 часов\n"
                f"<code>/boostspin 3.0</code> — 3x буст на 24 часа (реплай)",
                parse_mode="HTML"
            )
        
        if args[1].startswith("@"):
            # @username
            global_db = DatabaseManager.get_global_db()
            user_data = global_db.find_by_username(args[1][1:])
            if not user_data:
                return await message.reply(f"{EMOJI['cross']} Пользователь не найден!")
            target_id = user_data['user_id']
            first_name = user_data.get('first_name', args[1])
            username = args[1][1:]
            
            if len(args) > 2:
                try:
                    multiplier = float(args[2])
                except:
                    pass
                    
            if len(args) > 3:
                try:
                    duration = int(args[3])
                except:
                    pass
        elif args[1].isdigit() or args[1].replace('.', '').isdigit():
            # Это может быть множитель или ID
            if len(args) > 2:
                # Первый аргумент - множитель
                try:
                    multiplier = float(args[1])
                except:
                    pass
                    
                # Второй аргумент - ID
                try:
                    target_id = int(args[2])
                    first_name = str(target_id)
                except:
                    return await message.reply(f"{EMOJI['cross']} Укажи @username или ответь на сообщение!")
                
                if len(args) > 3:
                    try:
                        duration = int(args[3])
                    except:
                        pass
            else:
                return await message.reply(f"{EMOJI['cross']} Укажи @username или ответь на сообщение!")
    
    if not target_id:
        return await message.reply(f"{EMOJI['cross']} Не удалось определить пользователя!")
    
    multiplier = max(1.0, min(10.0, multiplier))  # Ограничиваем множитель от 1.0 до 10.0
    duration = max(1, min(720, duration))  # Ограничиваем длительность от 1 до 720 часов
    
    # Устанавливаем буст
    global_db = DatabaseManager.get_global_db()
    global_db.set_spin_boost(target_id, multiplier, duration)
    
    mention = f'<a href="tg://user?id={target_id}">{first_name}</a>'
    
    await message.reply(
        f"✨ <b>БУСТ УДАЧИ ВЫДАН!</b>\n\n"
        f"👤 {mention}\n"
        f"📈 Множитель: <b>x{multiplier}</b>\n"
        f"⏱️ Длительность: <b>{duration}</b> часов\n\n"
        f"👮 Выдал: {message.from_user.mention_html()}",
        parse_mode="HTML"
    )


@router.message(Command("givecoins"))
async def give_coins(message: Message, bot: Bot):
    """Выдать монеты"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    if not await is_owner_or_creator(message, bot):
        return await message.reply(f"{EMOJI['cross']} Только владелец группы или создатель бота!")
    
    args = message.text.split()
    db = get_db(message)
    
    target_id = None
    first_name = None
    username = None
    amount = 100
    
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        target_id = target.id
        first_name = target.first_name
        username = target.username
        
        if len(args) > 1:
            try:
                amount = int(args[1])
            except:
                amount = 100
    else:
        if len(args) < 2:
            return await message.reply(
                f"🪙 <b>Выдача монет</b>\n\n"
                f"<code>/givecoins @user [кол-во]</code>\n"
                f"<code>/givecoins [кол-во]</code> (реплай)",
                parse_mode="HTML"
            )
        
        if args[1].startswith("@"):
            global_db = DatabaseManager.get_global_db()
            user_data = global_db.find_by_username(args[1][1:])
            if not user_data:
                return await message.reply(f"{EMOJI['cross']} Пользователь не найден!")
            target_id = user_data['user_id']
            first_name = user_data.get('first_name', args[1])
            username = args[1][1:]
            
            if len(args) > 2:
                try:
                    amount = int(args[2])
                except:
                    amount = 100
        elif args[1].isdigit():
            # Может быть ID пользователя
            if len(args) > 2:
                target_id = int(args[1])
                first_name = str(target_id)
                try:
                    amount = int(args[2])
                except:
                    amount = 100
            else:
                return await message.reply(f"{EMOJI['cross']} Укажи @username или ответь на сообщение!")
    
    if not target_id:
        return await message.reply(f"{EMOJI['cross']} Укажи пользователя!")
    
    amount = max(1, min(1000000, amount))
    
    if not db.get_user(target_id):
        db.create_user(target_id, username, first_name)
    
    db.add_coins(target_id, amount)
    new_balance = db.get_coins(target_id)
    
    mention = f'<a href="tg://user?id={target_id}">{first_name}</a>'
    
    await message.reply(
        f"🪙 <b>Монеты выданы!</b>\n\n"
        f"👤 {mention}\n"
        f"➕ Выдано: <b>{amount}</b> 🪙\n"
        f"💰 Баланс: <b>{new_balance}</b> 🪙\n\n"
        f"👮 Выдал: {message.from_user.mention_html()}",
        parse_mode="HTML"
    )