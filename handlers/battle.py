import asyncio
import random
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from config import EMOJI, CARDS, RARITY_COLORS
from database import DatabaseManager

router = Router()


def is_group_chat(message: Message) -> bool:
    return message.chat.type in ["group", "supergroup"]


def get_db(message_or_chat_id):
    """Получить БД для чата"""
    if isinstance(message_or_chat_id, Message):
        return DatabaseManager.get_db(message_or_chat_id.chat.id)
    elif isinstance(message_or_chat_id, CallbackQuery):
        return DatabaseManager.get_db(message_or_chat_id.message.chat.id)
    return DatabaseManager.get_db(message_or_chat_id)


def find_card_in_collection(cards: list, card_name: str) -> dict | None:
    """Найти карту в коллекции пользователя"""
    for card in cards:
        if card["name"].lower() == card_name.lower():
            return card
    return None


def calculate_battle_result(card1: dict, card2: dict) -> tuple:
    """
    Рассчитать результат боя
    Возвращает (winner: 1 или 2, damage: int, is_critical: bool)
    """
    power1 = card1["attack"] + card1["defense"]
    power2 = card2["attack"] + card2["defense"]
    
    # Добавляем случайность (±20%)
    roll1 = power1 * random.uniform(0.8, 1.2)
    roll2 = power2 * random.uniform(0.8, 1.2)
    
    # Шанс критического удара (10%)
    is_critical = random.random() < 0.10
    
    if is_critical:
        # Критический удар увеличивает силу на 50%
        if random.choice([1, 2]) == 1:
            roll1 *= 1.5
        else:
            roll2 *= 1.5
    
    if roll1 > roll2:
        winner = 1
        damage = int(roll1 - roll2)
    elif roll2 > roll1:
        winner = 2
        damage = int(roll2 - roll1)
    else:
        # Ничья - случайный победитель
        winner = random.choice([1, 2])
        damage = 1
    
    return winner, damage, is_critical


def get_rating_change(winner_rating: int, loser_rating: int, is_win: bool) -> int:
    """Рассчитать изменение рейтинга (ELO-подобная система)"""
    diff = loser_rating - winner_rating
    expected = 1 / (1 + 10 ** (diff / 400))
    
    k_factor = 32  # Базовый коэффициент
    
    if is_win:
        change = int(k_factor * (1 - expected))
        return max(5, min(50, change))  # От 5 до 50 очков
    else:
        change = int(k_factor * expected)
        return -max(5, min(30, change))  # От -5 до -30 очков


# Хранение активных очередей для каждого чата
active_queues = {}  # {chat_id: {user_id: {...}}}

# Хранение запросов на бой
battle_requests = {}  # {chat_id: {initiator_id: {target_id: {...}}}}

@router.message(Command("arena"))
async def arena_command(message: Message):
    """Войти на арену"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Арена доступна только в группах!")
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    db = get_db(message)
    
    user = db.get_user(user_id)
    
    if not user:
        db.create_user(user_id, message.from_user.username, message.from_user.first_name)
        user = db.get_user(user_id)
    
    # Обновляем глобальную БД
    DatabaseManager.get_global_db().update_user(
        user_id, message.from_user.username, message.from_user.first_name
    )
    
    cards = user.get("cards", [])
    
    if not cards:
        return await message.reply(
            f"⚔️ <b>АРЕНА</b>\n\n"
            f"У тебя нет карт для боя!\n\n"
            f"💡 Используй /spin чтобы получить карты",
            parse_mode="HTML"
        )
    
    # Проверяем, не в очереди ли уже
    if db.is_in_queue(user_id):
        return await message.reply(
            f"⏳ Ты уже в очереди!\n\n"
            f"Используй /leave чтобы выйти",
            parse_mode="HTML"
        )
    
    # Проверяем, нет ли активных запросов на бой
    if chat_id in battle_requests and user_id in battle_requests[chat_id]:
        return await message.reply(
            f"⏳ У тебя уже есть активный запрос на бой!\n\n"
            f"Подожди ответа соперника или используй /leave_battle_request чтобы отменить",
            parse_mode="HTML"
        )
    
    # Сортируем карты по силе
    sorted_cards = sorted(cards, key=lambda x: x["attack"] + x["defense"], reverse=True)
    
    # Показываем топ-5 карт для выбора
    keyboard_buttons = []
    
    for i, card in enumerate(sorted_cards[:5]):
        power = card["attack"] + card["defense"]
        rarity_color = RARITY_COLORS.get(card["rarity"], "⚪")
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{rarity_color} {card['emoji']} {card['name']} (💪{power})",
                callback_data=f"arena_select:{card['name'][:30]}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="arena_cancel")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.reply(
        f"⚔️ <b>АРЕНА</b>\n\n"
        f"Выбери карту для боя:\n"
        f"<i>(показаны 5 сильнейших)</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("arena_select_opponent:"))
async def arena_select_opponent(callback: CallbackQuery):
    """Выбор противника для боя"""
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    db = get_db(callback)
    
    # Получаем данные из callback_data
    try:
        _, card_name, target_id = callback.data.split(":", 2)
        target_id = int(target_id)
    except ValueError:
        return await callback.answer("Ошибка данных!", show_alert=True)
    
    # Проверяем, что пользователь еще не в очереди
    if db.is_in_queue(user_id):
        return await callback.answer("Ты уже в очереди!", show_alert=True)
    
    # Проверяем, что цель еще не в очереди
    if db.is_in_queue(target_id):
        return await callback.answer("Этот игрок уже в очереди!", show_alert=True)
    
    # Проверяем, что цель не является инициатором
    if user_id == target_id:
        return await callback.answer("Нельзя вызвать себя на бой!", show_alert=True)
    
    # Получаем данные пользователей
    initiator = db.get_user(user_id)
    target = db.get_user(target_id)
    
    if not initiator or not target:
        return await callback.answer("Ошибка! Игрок не найден.", show_alert=True)
    
    # Находим карту инициатора
    initiator_card = find_card_in_collection(initiator.get("cards", []), card_name)
    
    if not initiator_card:
        return await callback.answer("Карта не найдена!", show_alert=True)
    
    # Проверяем наличие карт у цели
    target_cards = target.get("cards", [])
    if not target_cards:
        return await callback.answer("У этого игрока нет карт!", show_alert=True)
    
    # Сортируем карты цели по силе
    sorted_target_cards = sorted(target_cards, key=lambda x: x["attack"] + x["defense"], reverse=True)
    
    # Показываем топ-5 карт цели для выбора
    keyboard_buttons = []
    
    for i, card in enumerate(sorted_target_cards[:5]):
        power = card["attack"] + card["defense"]
        rarity_color = RARITY_COLORS.get(card["rarity"], "⚪")
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{rarity_color} {card['emoji']} {card['name']} (💪{power})",
                callback_data=f"arena_challenge:{card_name}:{target_id}:{card['name'][:30]}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="❌ Назад", callback_data="arena_cancel")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    target_name = target.get("first_name", "Игрок")
    
    await callback.message.edit_text(
        f"⚔️ <b>ВЫЗОВ НА БОЙ</b>\n\n"
        f"👤 Вызываешь: <b>{target_name}</b>\n"
        f"🃏 Твоя карта: {initiator_card['emoji']} <b>{initiator_card['name']}</b>\n\n"
        f"Выбери карту соперника для боя:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("arena_challenge:"))
async def arena_challenge(callback: CallbackQuery):
    """Отправка вызова на бой"""
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    db = get_db(callback)
    
    # Получаем данные из callback_data
    try:
        _, initiator_card_name, target_id_str, target_card_name = callback.data.split(":", 3)
        target_id = int(target_id_str)
    except ValueError:
        return await callback.answer("Ошибка данных!", show_alert=True)
    
    # Проверяем, что пользователь еще не в очереди
    if db.is_in_queue(user_id):
        return await callback.answer("Ты уже в очереди!", show_alert=True)
    
    # Проверяем, что цель еще не в очереди
    if db.is_in_queue(target_id):
        return await callback.answer("Этот игрок уже в очереди!", show_alert=True)
    
    # Проверяем, что цель не является инициатором
    if user_id == target_id:
        return await callback.answer("Нельзя вызвать себя на бой!", show_alert=True)
    
    # Получаем данные пользователей
    initiator = db.get_user(user_id)
    target = db.get_user(target_id)
    
    if not initiator or not target:
        return await callback.answer("Ошибка! Игрок не найден.", show_alert=True)
    
    # Находим карты
    initiator_card = find_card_in_collection(initiator.get("cards", []), initiator_card_name)
    target_card = find_card_in_collection(target.get("cards", []), target_card_name)
    
    if not initiator_card or not target_card:
        return await callback.answer("Карта не найдена!", show_alert=True)
    
    # Сохраняем запрос на бой
    if chat_id not in battle_requests:
        battle_requests[chat_id] = {}
    
    if user_id not in battle_requests[chat_id]:
        battle_requests[chat_id][user_id] = {}
    
    battle_requests[chat_id][user_id][target_id] = {
        "initiator_card": initiator_card_name,
        "target_card": target_card_name,
        "timestamp": callback.message.date
    }
    
    # Отправляем запрос на бой цели
    initiator_name = initiator.get("first_name", "Игрок")
    target_name = target.get("first_name", "Игрок")
    
    # Сообщение для инициатора
    await callback.message.edit_text(
        f"⚔️ <b>ВЫЗОВ НА БОЙ ОТПРАВЛЕН</b>\n\n"
        f"👤 Соперник: <b>{target_name}</b>\n"
        f"🃏 Твоя карта: {initiator_card['emoji']} <b>{initiator_card['name']}</b>\n"
        f"🃏 Карта соперника: {target_card['emoji']} <b>{target_card['name']}</b>\n\n"
        f"⏳ Ожидание ответа...",
        parse_mode="HTML"
    )
    
    # Сообщение для цели с кнопками принять/отклонить
    target_power = target_card["attack"] + target_card["defense"]
    initiator_power = initiator_card["attack"] + initiator_card["defense"]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"arena_accept:{user_id}:{initiator_card_name}:{target_card_name}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"arena_decline:{user_id}")
        ]
    ])
    
    try:
        await callback.bot.send_message(
            target_id,
            f"⚔️ <b>ВЫЗОВ НА БОЙ!</b>\n\n"
            f"👤 {initiator_name} вызывает тебя на бой!\n"
            f"🃏 Его карта: {initiator_card['emoji']} <b>{initiator_card['name']}</b> (💪{initiator_power})\n"
            f"🃏 Твоя карта: {target_card['emoji']} <b>{target_card['name']}</b> (💪{target_power})\n\n"
            f"Принять вызов?",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except:
        # Если не удалось отправить ЛС, удаляем запрос
        if chat_id in battle_requests and user_id in battle_requests[chat_id]:
            if target_id in battle_requests[chat_id][user_id]:
                del battle_requests[chat_id][user_id][target_id]
                if not battle_requests[chat_id][user_id]:
                    del battle_requests[chat_id][user_id]
                    if not battle_requests[chat_id]:
                        del battle_requests[chat_id]
        
        await callback.message.edit_text(
            f"⚔️ <b>ОШИБКА</b>\n\n"
            f"Не удалось отправить вызов игроку {target_name}.\n"
            f"Возможно, он ограничил получение сообщений.",
            parse_mode="HTML"
        )
        return
    
    await callback.answer("Вызов отправлен!")


@router.callback_query(F.data.startswith("arena_accept:"))
async def arena_accept(callback: CallbackQuery):
    """Принятие вызова на бой"""
    target_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    # Получаем данные из callback_data
    try:
        _, initiator_id_str, initiator_card_name, target_card_name = callback.data.split(":", 3)
        initiator_id = int(initiator_id_str)
    except ValueError:
        return await callback.answer("Ошибка данных!", show_alert=True)
    
    # Проверяем существование запроса
    if (chat_id not in battle_requests or
        initiator_id not in battle_requests[chat_id] or
        target_id not in battle_requests[chat_id][initiator_id]):
        return await callback.answer("Запрос на бой уже отменен!", show_alert=True)
    
    # Удаляем запрос
    del battle_requests[chat_id][initiator_id][target_id]
    if not battle_requests[chat_id][initiator_id]:
        del battle_requests[chat_id][initiator_id]
        if not battle_requests[chat_id]:
            del battle_requests[chat_id]
    
    db = get_db(chat_id)
    
    # Проверяем, что оба игрока еще не в очереди
    if db.is_in_queue(initiator_id) or db.is_in_queue(target_id):
        return await callback.message.edit_text(
            f"⚔️ <b>ВЫЗОВ ОТМЕНЕН</b>\n\n"
            f"Один из игроков уже в очереди!",
            parse_mode="HTML"
        )
    
    # Получаем данные пользователей
    initiator = db.get_user(initiator_id)
    target = db.get_user(target_id)
    
    if not initiator or not target:
        return await callback.message.edit_text(
            f"⚔️ <b>ОШИБКА</b>\n\n"
            f"Один из игроков не найден!",
            parse_mode="HTML"
        )
    
    # Находим карты
    initiator_card = find_card_in_collection(initiator.get("cards", []), initiator_card_name)
    target_card = find_card_in_collection(target.get("cards", []), target_card_name)
    
    if not initiator_card or not target_card:
        return await callback.message.edit_text(
            f"⚔️ <b>ОШИБКА</b>\n\n"
            f"Одна из карт не найдена!",
            parse_mode="HTML"
        )
    
    # Добавляем обоих игроков в очередь
    db.join_arena_queue(initiator_id, initiator_card_name)
    db.join_arena_queue(target_id, target_card_name)
    
    # Сообщаем об успешном начале боя
    initiator_name = initiator.get("first_name", "Игрок")
    target_name = target.get("first_name", "Игрок")
    
    await callback.message.edit_text(
        f"⚔️ <b>БОЙ НАЧАЛСЯ!</b>\n\n"
        f"👤 {initiator_name} vs {target_name}\n"
        f"🃏 {initiator_card['emoji']} <b>{initiator_card['name']}</b> vs {target_card['emoji']} <b>{target_card['name']}</b>\n\n"
        f"⏳ Бой начнется в ближайшее время...",
        parse_mode="HTML"
    )
    
    # Проверяем, есть ли соперник и запускаем бой
    await check_for_match(chat_id, callback.bot)


@router.callback_query(F.data.startswith("arena_decline:"))
async def arena_decline(callback: CallbackQuery):
    """Отклонение вызова на бой"""
    target_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    # Получаем данные из callback_data
    try:
        _, initiator_id_str = callback.data.split(":", 1)
        initiator_id = int(initiator_id_str)
    except ValueError:
        return await callback.answer("Ошибка данных!", show_alert=True)
    
    # Удаляем запрос если он существует
    if (chat_id in battle_requests and
        initiator_id in battle_requests[chat_id] and
        target_id in battle_requests[chat_id][initiator_id]):
        del battle_requests[chat_id][initiator_id][target_id]
        if not battle_requests[chat_id][initiator_id]:
            del battle_requests[chat_id][initiator_id]
            if not battle_requests[chat_id]:
                del battle_requests[chat_id]
    
    # Сообщаем инициатору об отклонении
    try:
        target_name = callback.from_user.first_name
        await callback.bot.send_message(
            initiator_id,
            f"⚔️ <b>ВЫЗОВ ОТКЛОНЕН</b>\n\n"
            f"Игрок {target_name} отклонил твой вызов на бой.",
            parse_mode="HTML"
        )
    except:
        pass  # Не удалось отправить сообщение инициатору
    
    await callback.message.edit_text(
        f"⚔️ <b>ВЫЗОВ ОТКЛОНЕН</b>\n\n"
        f"Ты отклонил вызов на бой.",
        parse_mode="HTML"
    )
    await callback.answer("Вызов отклонен")


@router.message(Command("leave_battle_request"))
async def leave_battle_request(message: Message):
    """Отменить запрос на бой"""
    if not is_group_chat(message):
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Удаляем запрос если он существует
    if (chat_id in battle_requests and
        user_id in battle_requests[chat_id]):
        del battle_requests[chat_id][user_id]
        if not battle_requests[chat_id]:
            del battle_requests[chat_id]
        
        await message.reply(f"{EMOJI['check']} Запрос на бой отменен")
    else:
        await message.reply("У тебя нет активных запросов на бой")


@router.callback_query(F.data.startswith("arena_select:"))
async def arena_select_card(callback: CallbackQuery):
    """Выбор карты и выбор противника"""
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    db = get_db(callback)
    
    card_name = callback.data.split(":", 1)[1]
    
    user = db.get_user(user_id)
    if not user:
        return await callback.answer("Ошибка! Попробуй /arena заново", show_alert=True)
    
    cards = user.get("cards", [])
    selected_card = find_card_in_collection(cards, card_name)
    
    if not selected_card:
        return await callback.answer("Карта не найдена!", show_alert=True)
    
    # Проверяем очередь
    if db.is_in_queue(user_id):
        return await callback.answer("Ты уже в очереди!", show_alert=True)
    
    # Получаем список других игроков в чате
    all_users = []
    try:
        # Получаем участников чата (это может не работать в больших чатах)
        chat_members = await callback.bot.get_chat_member(chat_id, user_id)
        # Вместо этого просто покажем активных игроков из БД
        pass
    except:
        pass
    
    # Получаем всех пользователей из БД этого чата
    # Для простоты покажем всех пользователей с картами
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, first_name
        FROM users
        WHERE user_id != ? AND cards != '[]' AND cards IS NOT NULL
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    opponents = []
    for row in rows:
        opponent_id, opponent_name = row
        # Проверяем, что у противника есть карты
        opponent = db.get_user(opponent_id)
        if opponent and opponent.get("cards"):
            opponents.append({"id": opponent_id, "name": opponent_name or "Игрок"})
    
    # Если есть противники, показываем выбор
    if opponents:
        keyboard_buttons = []
        
        # Показываем до 10 противников
        for opponent in opponents[:10]:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"👤 {opponent['name']}",
                    callback_data=f"arena_select_opponent:{card_name}:{opponent['id']}"
                )
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="👥 В очередь (случайный противник)", callback_data=f"arena_queue:{card_name}")
        ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="❌ Отмена", callback_data="arena_cancel")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        power = selected_card["attack"] + selected_card["defense"]
        
        await callback.message.edit_text(
            f"⚔️ <b>ВЫБОР ПРОТИВНИКА</b>\n\n"
            f"🃏 Твоя карта: {selected_card['emoji']} <b>{selected_card['name']}</b>\n"
            f"💪 Сила: {power}\n\n"
            f"Выбери противника для боя:",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        # Если нет противников, сразу в очередь
        db.join_arena_queue(user_id, selected_card["name"])
        
        power = selected_card["attack"] + selected_card["defense"]
        
        await callback.message.edit_text(
            f"⚔️ <b>В ОЧЕРЕДИ!</b>\n\n"
            f"👤 {callback.from_user.first_name}\n"
            f"🃏 {selected_card['emoji']} <b>{selected_card['name']}</b>\n"
            f"💪 Сила: {power}\n\n"
            f"⏳ Ожидание соперника...\n\n"
            f"<i>Используй /leave чтобы выйти</i>",
            parse_mode="HTML"
        )
        
        await callback.answer("Ты в очереди!")
        
        # Проверяем, есть ли соперник
        await check_for_match(callback.message.chat.id, callback.bot)
    
    await callback.answer()


@router.callback_query(F.data.startswith("arena_queue:"))
async def arena_join_queue(callback: CallbackQuery):
    """Вход в очередь для случайного противника"""
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    db = get_db(callback)
    
    card_name = callback.data.split(":", 1)[1]
    
    user = db.get_user(user_id)
    if not user:
        return await callback.answer("Ошибка! Попробуй /arena заново", show_alert=True)
    
    cards = user.get("cards", [])
    selected_card = find_card_in_collection(cards, card_name)
    
    if not selected_card:
        return await callback.answer("Карта не найдена!", show_alert=True)
    
    # Проверяем очередь
    if db.is_in_queue(user_id):
        return await callback.answer("Ты уже в очереди!", show_alert=True)
    
    # Добавляем в очередь
    db.join_arena_queue(user_id, selected_card["name"])
    
    power = selected_card["attack"] + selected_card["defense"]
    
    await callback.message.edit_text(
        f"⚔️ <b>В ОЧЕРЕДИ!</b>\n\n"
        f"👤 {callback.from_user.first_name}\n"
        f"🃏 {selected_card['emoji']} <b>{selected_card['name']}</b>\n"
        f"💪 Сила: {power}\n\n"
        f"⏳ Ожидание соперника...\n\n"
        f"<i>Используй /leave чтобы выйти</i>",
        parse_mode="HTML"
    )
    
    await callback.answer("Ты в очереди!")
    
    # Проверяем, есть ли соперник
    await check_for_match(callback.message.chat.id, callback.bot)


@router.callback_query(F.data == "arena_cancel")
async def arena_cancel(callback: CallbackQuery):
    """Отмена входа на арену"""
    await callback.message.edit_text(
        f"⚔️ Вход на арену отменён",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(Command("leave"))
async def leave_queue(message: Message):
    """Выйти из очереди"""
    if not is_group_chat(message):
        return
    
    user_id = message.from_user.id
    db = get_db(message)
    
    if not db.is_in_queue(user_id):
        return await message.reply("Ты не в очереди!")
    
    db.leave_arena_queue(user_id)
    await message.reply(f"{EMOJI['check']} Ты вышел из очереди")


async def check_for_match(chat_id: int, bot: Bot):
    """Проверить и создать матч если есть 2+ игрока"""
    db = DatabaseManager.get_db(chat_id)
    queue = db.get_arena_queue()
    
    if len(queue) >= 2:
        # Берём первых двух игроков
        player1_data = queue[0]
        player2_data = queue[1]
        
        # Удаляем из очереди
        db.leave_arena_queue(player1_data["user_id"])
        db.leave_arena_queue(player2_data["user_id"])
        
        # Запускаем бой
        await start_battle(
            chat_id, bot,
            player1_data["user_id"], player1_data["card_name"],
            player2_data["user_id"], player2_data["card_name"]
        )


async def start_battle(chat_id: int, bot: Bot, 
                       player1_id: int, player1_card_name: str,
                       player2_id: int, player2_card_name: str):
    """Запустить бой между двумя игроками"""
    db = DatabaseManager.get_db(chat_id)
    
    # Получаем данные игроков
    player1 = db.get_user(player1_id)
    player2 = db.get_user(player2_id)
    
    if not player1 or not player2:
        return
    
    # Находим карты
    player1_card = find_card_in_collection(player1.get("cards", []), player1_card_name)
    player2_card = find_card_in_collection(player2.get("cards", []), player2_card_name)
    
    if not player1_card or not player2_card:
        await bot.send_message(chat_id, "⚠️ Ошибка боя: карты не найдены")
        return
    
    # Рассчитываем результат
    winner_num, damage, is_critical = calculate_battle_result(player1_card, player2_card)
    
    if winner_num == 1:
        winner_id = player1_id
        loser_id = player2_id
        winner_card = player1_card
        loser_card = player2_card
        winner_name = player1.get("first_name", "Игрок 1")
        loser_name = player2.get("first_name", "Игрок 2")
    else:
        winner_id = player2_id
        loser_id = player1_id
        winner_card = player2_card
        loser_card = player1_card
        winner_name = player2.get("first_name", "Игрок 2")
        loser_name = player1.get("first_name", "Игрок 1")
    
    # Рассчитываем изменение рейтинга
    winner_rating = db.get_user(winner_id).get("rating", 0)
    loser_rating = db.get_user(loser_id).get("rating", 0)
    
    winner_change = get_rating_change(winner_rating, loser_rating, True)
    loser_change = get_rating_change(loser_rating, winner_rating, False)
    
    # Проверяем, есть ли у проигравшего щиты
    loser_shields = db.get_shields(loser_id)
    shield_used = False
    
    if loser_shields > 0:
        # Используем щит вместо понижения рейтинга
        db.use_shield(loser_id)
        loser_change = 0  # Не теряем рейтинг при использовании щита
        shield_used = True
    
    # Обновляем рейтинг
    db.update_rating(winner_id, winner_change, True)
    db.update_rating(loser_id, loser_change, False)
    
    # Сохраняем бой
    db.add_battle(player1_id, player2_id, winner_id, player1_card_name, player2_card_name)
    
    # Бонус монет победителю
    coins_reward = random.randint(5, 15)
    db.add_coins(winner_id, coins_reward)
    
    # Формируем сообщение
    p1_power = player1_card["attack"] + player1_card["defense"]
    p2_power = player2_card["attack"] + player2_card["defense"]
    
    p1_color = RARITY_COLORS.get(player1_card["rarity"], "⚪")
    p2_color = RARITY_COLORS.get(player2_card["rarity"], "⚪")
    
    critical_text = "\n💥 <b>КРИТИЧЕСКИЙ УДАР!</b>" if is_critical else ""
    
    # Проверяем использование щита
    shield_text = ""
    if shield_used:
        shield_text = f"\n🛡️ {loser_name} использовал щит! Рейтинг сохранен."
    
    battle_text = (
        f"⚔️ <b>БОЙ НА АРЕНЕ!</b>\n"
        f"{'━' * 25}\n\n"
        
        f"🔴 <b>{player1.get('first_name', 'Игрок 1')}</b>\n"
        f"   {p1_color} {player1_card['emoji']} {player1_card['name']}\n"
        f"   ⚔️{player1_card['attack']} 🛡️{player1_card['defense']} = 💪{p1_power}\n\n"
        
        f"<b>VS</b>\n\n"
        
        f"🔵 <b>{player2.get('first_name', 'Игрок 2')}</b>\n"
        f"   {p2_color} {player2_card['emoji']} {player2_card['name']}\n"
        f"   ⚔️{player2_card['attack']} 🛡️{player2_card['defense']} = 💪{p2_power}\n\n"
        
        f"{'━' * 25}\n"
        f"{critical_text}"
        f"{shield_text}\n"
        f"🏆 <b>ПОБЕДИТЕЛЬ:</b> {winner_name}!\n\n"
        
        f"📊 <b>Рейтинг:</b>\n"
        f"   ✅ {winner_name}: +{winner_change} ⭐\n"
        f"   ❌ {loser_name}: {loser_change} ⭐\n\n"
        
        f"🪙 Награда: +{coins_reward} монет"
    )
    
    await bot.send_message(chat_id, battle_text, parse_mode="HTML")


@router.message(Command("rating"))
async def show_rating(message: Message):
    """Показать рейтинг арены"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    db = get_db(message)
    top_players = db.get_top_players(10)
    
    if not top_players:
        return await message.reply(
            f"🏆 <b>РЕЙТИНГ АРЕНЫ</b>\n\n"
            f"Пока никто не сражался!\n\n"
            f"💡 Используй /arena для боя",
            parse_mode="HTML"
        )
    
    text = f"🏆 <b>РЕЙТИНГ АРЕНЫ</b>\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, player in enumerate(top_players):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = player.get("first_name") or player.get("username") or "Аноним"
        rating = player.get("rating", 0)
        wins = player.get("wins", 0)
        losses = player.get("losses", 0)
        
        winrate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        
        text += f"{medal} <b>{name}</b>\n"
        text += f"    ⭐ {rating} | ✅ {wins} | ❌ {losses} | 📊 {winrate:.0f}%\n"
    
    await message.reply(text, parse_mode="HTML")


@router.message(Command("profile"))
async def show_profile(message: Message):
    """Показать профиль игрока"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    db = get_db(message)
    
    # Определяем чей профиль показывать
    target_id = message.from_user.id
    target_name = message.from_user.first_name
    
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name
    else:
        args = message.text.split()
        if len(args) > 1:
            if args[1].startswith("@"):
                global_db = DatabaseManager.get_global_db()
                user_data = global_db.find_by_username(args[1][1:])
                if user_data:
                    target_id = user_data["user_id"]
                    target_name = user_data.get("first_name", args[1])
                else:
                    return await message.reply(f"{EMOJI['cross']} Пользователь не найден!")
            elif args[1].isdigit():
                target_id = int(args[1])
    
    user = db.get_user(target_id)
    
    if not user:
        return await message.reply(
            f"👤 Профиль не найден!\n\n"
            f"<i>Этот пользователь ещё не использовал бота в этой группе</i>",
            parse_mode="HTML"
        )
    
    # Статистика
    cards = user.get("cards", [])
    coins = user.get("coins", 0)
    rating = user.get("rating", 0)
    wins = user.get("wins", 0)
    losses = user.get("losses", 0)
    bio = user.get("bio", "")
    
    total_games = wins + losses
    winrate = (wins / total_games * 100) if total_games > 0 else 0
    
    # Лучшая карта
    best_card = None
    if cards:
        best_card = max(cards, key=lambda x: x["attack"] + x["defense"])
    
    # Уникальные карты
    unique_cards = len(set(c["name"] for c in cards))
    
    # Ранг на основе рейтинга
    if rating >= 2000:
        rank_title = "👑 Легенда"
    elif rating >= 1500:
        rank_title = "💎 Мастер"
    elif rating >= 1000:
        rank_title = "🥇 Эксперт"
    elif rating >= 500:
        rank_title = "🥈 Ветеран"
    elif rating >= 100:
        rank_title = "🥉 Боец"
    else:
        rank_title = "⚪ Новичок"
    
    text = f"👤 <b>ПРОФИЛЬ</b>\n"
    text += f"{'━' * 25}\n\n"
    
    text += f"🏷️ <b>{target_name}</b>\n"
    text += f"🎖️ {rank_title}\n"
    
    if bio:
        text += f"\n📝 <i>{bio}</i>\n"
    
    text += f"\n<b>📊 Статистика арены:</b>\n"
    text += f"   ⭐ Рейтинг: <b>{rating}</b>\n"
    text += f"   ✅ Побед: <b>{wins}</b>\n"
    text += f"   ❌ Поражений: <b>{losses}</b>\n"
    text += f"   📈 Винрейт: <b>{winrate:.1f}%</b>\n"
    
    text += f"\n<b>🃏 Коллекция:</b>\n"
    text += f"   📦 Всего карт: <b>{len(cards)}</b>\n"
    text += f"   ✨ Уникальных: <b>{unique_cards}</b>\n"
    text += f"   🪙 Монет: <b>{coins}</b>\n"
    
    if best_card:
        power = best_card["attack"] + best_card["defense"]
        color = RARITY_COLORS.get(best_card["rarity"], "⚪")
        text += f"\n<b>👑 Лучшая карта:</b>\n"
        text += f"   {color} {best_card['emoji']} {best_card['name']} (💪{power})\n"
    
    # Отправляем с фото профиля если есть
    photo_id = user.get("profile_photo_id")
    if photo_id:
        try:
            await message.reply_photo(photo=photo_id, caption=text, parse_mode="HTML")
            return
        except:
            pass
    
    await message.reply(text, parse_mode="HTML")


@router.message(Command("setbio"))
async def set_bio(message: Message):
    """Установить описание профиля"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        return await message.reply(
            f"✏️ <b>Описание профиля</b>\n\n"
            f"<code>/setbio твой текст</code>\n\n"
            f"Максимум 200 символов",
            parse_mode="HTML"
        )
    
    bio = args[1][:200]
    
    user_id = message.from_user.id
    db = get_db(message)
    
    if not db.get_user(user_id):
        db.create_user(user_id, message.from_user.username, message.from_user.first_name)
    
    db.set_bio(user_id, bio)
    
    await message.reply(
        f"{EMOJI['check']} Описание установлено!\n\n"
        f"📝 <i>{bio}</i>",
        parse_mode="HTML"
    )


@router.message(Command("setphoto"))
async def set_photo(message: Message):
    """Установить фото профиля"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply(
            f"📷 <b>Фото профиля</b>\n\n"
            f"Ответь на фото командой /setphoto",
            parse_mode="HTML"
        )
    
    photo_id = message.reply_to_message.photo[-1].file_id
    user_id = message.from_user.id
    db = get_db(message)
    
    if not db.get_user(user_id):
        db.create_user(user_id, message.from_user.username, message.from_user.first_name)
    
    db.set_profile_photo(user_id, photo_id)
    
    await message.reply(f"{EMOJI['check']} Фото профиля установлено!")


@router.message(Command("removephoto"))
async def remove_photo(message: Message):
    """Удалить фото профиля"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    user_id = message.from_user.id
    db = get_db(message)
    
    if not db.get_user(user_id):
        return await message.reply("У тебя нет профиля!")
    
    db.remove_profile_photo(user_id)
    
    await message.reply(f"{EMOJI['check']} Фото профиля удалено!")


@router.message(Command("queue"))
async def show_queue(message: Message):
    """Показать очередь на арену"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    db = get_db(message)
    queue = db.get_arena_queue()
    
    if not queue:
        return await message.reply(
            f"⚔️ <b>Очередь арены</b>\n\n"
            f"Пусто! Используй /arena чтобы войти",
            parse_mode="HTML"
        )
    
    text = f"⚔️ <b>Очередь арены ({len(queue)})</b>\n\n"
    
    for i, player in enumerate(queue, 1):
        user = db.get_user(player["user_id"])
        name = user.get("first_name", "Игрок") if user else "Игрок"
        text += f"{i}. {name} — {player['card_name']}\n"
    
    await message.reply(text, parse_mode="HTML")


async def check_queue_periodically(bot: Bot):
    """Периодическая проверка очередей во всех группах"""
    while True:
        try:
            for group_db in DatabaseManager.get_all_group_dbs():
                queue = group_db.get_arena_queue()
                if len(queue) >= 2:
                    await check_for_match(group_db.chat_id, bot)
        except Exception as e:
            print(f"Error in queue check: {e}")
        
        await asyncio.sleep(5)


@router.message(Command("shields"))
async def show_shields(message: Message):
    """Показать количество щитов у игрока"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    user_id = message.from_user.id
    db = get_db(message)
    
    # Создаем пользователя если его нет
    if not db.get_user(user_id):
        db.create_user(user_id, message.from_user.username, message.from_user.first_name)
    
    shields = db.get_shields(user_id)
    
    await message.reply(
        f"🛡️ <b>ТВОИ ЩИТЫ</b>\n\n"
        f"У тебя: <b>{shields}</b> щитов\n\n"
        f"Щиты защищают от потери рейтинга при поражении на арене.\n"
        f"Купить щиты можно в /market",
        parse_mode="HTML"
    )