import random
import json
import uuid
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from config import EMOJI, CARDS, RARITY_COLORS
from database import DatabaseManager

router = Router()

# Определяем состояния для FSM
class TradeStates(StatesGroup):
    waiting_for_target = State()
    waiting_for_card_selection = State()
    waiting_for_confirmation = State()

# Хранилище активных обменов
active_trades = {}

def is_group_chat(message: Message) -> bool:
    return message.chat.type in ["group", "supergroup"]

def get_db(message_or_callback):
    """Получить БД для чата"""
    if isinstance(message_or_callback, Message):
        return DatabaseManager.get_db(message_or_callback.chat.id)
    elif isinstance(message_or_callback, CallbackQuery):
        return DatabaseManager.get_db(message_or_callback.message.chat.id)
    return None

@router.message(Command("trade"))
async def trade_start(message: Message, state: FSMContext):
    """Начало торговли"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Торговать можно только в группах!")
    
    user_id = message.from_user.id
    db = get_db(message)
    
    # Создаем пользователя если его нет
    if not db.get_user(user_id):
        db.create_user(user_id, message.from_user.username, message.from_user.first_name)
    
    user = db.get_user(user_id)
    cards = user.get("cards", [])
    
    if not cards:
        return await message.reply(
            f"🔁 <b>ТОРГОВЛЯ</b>\n\n"
            f"У тебя нет карт для обмена!\n\n"
            f"💡 Используй /spin чтобы получить карты",
            parse_mode="HTML"
        )
    
    # Сортируем карты по редкости и силе
    rarity_order = {"special": 0, "mythic": 1, "legendary": 2, "epic": 3, "rare": 4, "common": 5}
    sorted_cards = sorted(
        cards,
        key=lambda x: (rarity_order.get(x["rarity"], 99), -(x["attack"] + x["defense"]))
    )
    
    # Показываем карты для выбора
    keyboard_buttons = []
    
    for i, card in enumerate(sorted_cards[:10]):  # Показываем до 10 карт
        power = card["attack"] + card["defense"]
        rarity_color = RARITY_COLORS.get(card["rarity"], "⚪")
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{rarity_color} {card['emoji']} {card['name']} (💪{power})",
                callback_data=f"trade_select_card:{i}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="trade_cancel")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    # Сохраняем карты пользователя в состоянии
    await state.set_state(TradeStates.waiting_for_card_selection)
    await state.update_data(user_cards=cards)
    
    await message.reply(
        f"🔁 <b>ТОРГОВЛЯ</b>\n\n"
        f"Выбери карту для обмена:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("trade_select_card:"))
async def trade_select_card(callback: CallbackQuery, state: FSMContext):
    """Выбор карты для обмена"""
    try:
        _, index_str = callback.data.split(":", 1)
        index = int(index_str)
    except ValueError:
        return await callback.answer("Ошибка данных!", show_alert=True)
    
    data = await state.get_data()
    user_cards = data.get("user_cards", [])
    
    if index >= len(user_cards):
        return await callback.answer("Карта не найдена!", show_alert=True)
    
    selected_card = user_cards[index]
    
    # Сохраняем выбранную карту
    await state.update_data(selected_card=selected_card)
    
    # Запрашиваем у пользователя, с кем он хочет обменяться
    await callback.message.edit_text(
        f"🔁 <b>ТОРГОВЛЯ</b>\n\n"
        f"Выбрана карта: {selected_card['emoji']} <b>{selected_card['name']}</b>\n\n"
        f"Введите @username или ID пользователя, с которым хотите обменяться:",
        parse_mode="HTML"
    )
    
    await state.set_state(TradeStates.waiting_for_target)
    await callback.answer()

@router.message(TradeStates.waiting_for_target)
async def trade_select_target(message: Message, state: FSMContext):
    """Выбор цели для обмена"""
    target_identifier = message.text.strip()
    
    if not target_identifier:
        return await message.reply("❌ Введите @username или ID пользователя!")
    
    db = get_db(message)
    target_user = None
    target_id = None
    
    # Проверяем, является ли это ID
    if target_identifier.isdigit():
        target_id = int(target_identifier)
        target_user = db.get_user(target_id)
    # Проверяем, является ли это username
    elif target_identifier.startswith("@"):
        global_db = DatabaseManager.get_global_db()
        user_data = global_db.find_by_username(target_identifier[1:])
        if user_data:
            target_id = user_data["user_id"]
            target_user = db.get_user(target_id)
    
    if not target_user or not target_id:
        return await message.reply("❌ Пользователь не найден! Проверьте username или ID.")
    
    if target_id == message.from_user.id:
        return await message.reply("❌ Нельзя обменяться с самим собой!")
    
    # Проверяем, есть ли у цели карты
    target_cards = target_user.get("cards", [])
    if not target_cards:
        return await message.reply("❌ У этого пользователя нет карт для обмена!")
    
    # Сохраняем цель
    await state.update_data(target_id=target_id)
    
    # Показываем карты цели для выбора
    rarity_order = {"special": 0, "mythic": 1, "legendary": 2, "epic": 3, "rare": 4, "common": 5}
    sorted_target_cards = sorted(
        target_cards,
        key=lambda x: (rarity_order.get(x["rarity"], 99), -(x["attack"] + x["defense"]))
    )
    
    data = await state.get_data()
    selected_card = data.get("selected_card")
    
    keyboard_buttons = []
    
    for i, card in enumerate(sorted_target_cards[:10]):  # Показываем до 10 карт
        power = card["attack"] + card["defense"]
        rarity_color = RARITY_COLORS.get(card["rarity"], "⚪")
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{rarity_color} {card['emoji']} {card['name']} (💪{power})",
                callback_data=f"trade_confirm:{i}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="trade_cancel")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    target_name = target_user.get("first_name", "Пользователь")
    
    await message.reply(
        f"🔁 <b>ТОРГОВЛЯ С {target_name}</b>\n\n"
        f"Твоя карта: {selected_card['emoji']} <b>{selected_card['name']}</b>\n\n"
        f"Выбери карту от {target_name} для обмена:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    await state.set_state(TradeStates.waiting_for_confirmation)

@router.callback_query(F.data.startswith("trade_confirm:"))
async def trade_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение обмена"""
    try:
        _, index_str = callback.data.split(":", 1)
        index = int(index_str)
    except ValueError:
        return await callback.answer("Ошибка данных!", show_alert=True)
    
    data = await state.get_data()
    selected_card = data.get("selected_card")
    target_id = data.get("target_id")
    
    if not selected_card or not target_id:
        return await callback.answer("Ошибка данных!", show_alert=True)
    
    # Получаем данные пользователей
    db = get_db(callback)
    initiator = db.get_user(callback.from_user.id)
    target = db.get_user(target_id)
    
    if not initiator or not target:
        return await callback.answer("Ошибка! Один из пользователей не найден.", show_alert=True)
    
    # Получаем карту цели
    target_cards = target.get("cards", [])
    rarity_order = {"special": 0, "mythic": 1, "legendary": 2, "epic": 3, "rare": 4, "common": 5}
    sorted_target_cards = sorted(
        target_cards,
        key=lambda x: (rarity_order.get(x["rarity"], 99), -(x["attack"] + x["defense"]))
    )
    
    if index >= len(sorted_target_cards):
        return await callback.answer("Карта не найдена!", show_alert=True)
    
    target_card = sorted_target_cards[index]
    
    # Создаем уникальный ID для обмена
    trade_id = str(uuid.uuid4())
    
    # Сохраняем данные обмена
    active_trades[trade_id] = {
        "initiator_id": callback.from_user.id,
        "target_id": target_id,
        "initiator_card": selected_card,
        "target_card": target_card,
        "initiator_name": initiator.get("first_name", "Пользователь"),
        "target_name": target.get("first_name", "Пользователь")
    }
    
    # Отправляем запрос на обмен цели
    initiator_name = initiator.get("first_name", "Пользователь")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"trade_accept:{trade_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"trade_decline:{trade_id}")
        ]
    ])
    
    try:
        await bot.send_message(
            target_id,
            f"🔁 <b>ПРЕДЛОЖЕНИЕ ОБМЕНА</b>\n\n"
            f"Пользователь {initiator_name} предлагает обмен:\n\n"
            f"🔄 Его карта: {selected_card['emoji']} <b>{selected_card['name']}</b>\n"
            f"🔄 Твоя карта: {target_card['emoji']} <b>{target_card['name']}</b>\n\n"
            f"Принять обмен?",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        # Сообщаем инициатору, что запрос отправлен
        target_name = target.get("first_name", "Пользователь")
        await callback.message.edit_text(
            f"🔁 <b>ЗАПРОС НА ОБМЕН ОТПРАВЛЕН</b>\n\n"
            f"Пользователю {target_name} отправлен запрос на обмен:\n\n"
            f"🔄 Твоя карта: {selected_card['emoji']} <b>{selected_card['name']}</b>\n"
            f"🔄 Его карта: {target_card['emoji']} <b>{target_card['name']}</b>\n\n"
            f"⏳ Ожидание ответа...",
            parse_mode="HTML"
        )
    except Exception as e:
        # Удаляем данные обмена при ошибке
        if trade_id in active_trades:
            del active_trades[trade_id]
            
        await callback.message.edit_text(
            f"❌ <b>ОШИБКА</b>\n\n"
            f"Не удалось отправить запрос на обмен: {str(e)}",
            parse_mode="HTML"
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("trade_accept:"))
async def trade_accept(callback: CallbackQuery, bot: Bot):
    """Принятие предложения обмена"""
    try:
        _, trade_id = callback.data.split(":", 1)
    except ValueError:
        return await callback.answer("Ошибка данных!", show_alert=True)
    
    # Проверяем, существует ли обмен
    if trade_id not in active_trades:
        return await callback.message.edit_text(
            f"❌ <b>ОШИБКА</b>\n\n"
            f"Обмен не найден или уже завершен!",
            parse_mode="HTML"
        )
    
    trade_info = active_trades[trade_id]
    initiator_id = trade_info["initiator_id"]
    target_id = trade_info["target_id"]
    initiator_card = trade_info["initiator_card"]
    target_card = trade_info["target_card"]
    
    # Проверяем, что пользователь, принимающий обмен, является целью
    if callback.from_user.id != target_id:
        return await callback.answer("Этот обмен не для вас!", show_alert=True)
    
    db = get_db(callback)
    
    # Получаем данные пользователей
    initiator = db.get_user(initiator_id)
    target = db.get_user(target_id)
    
    if not initiator or not target:
        # Удаляем обмен из активных
        del active_trades[trade_id]
        return await callback.message.edit_text(
            f"❌ <b>ОШИБКА</b>\n\n"
            f"Один из пользователей не найден!",
            parse_mode="HTML"
        )
    
    # Проверяем, что у пользователей все еще есть карты
    initiator_cards = initiator.get("cards", [])
    target_cards = target.get("cards", [])
    
    # Проверяем наличие карт для обмена
    initiator_has_card = any(c["name"] == initiator_card["name"] for c in initiator_cards)
    target_has_card = any(c["name"] == target_card["name"] for c in target_cards)
    
    if not initiator_has_card:
        # Удаляем обмен из активных
        del active_trades[trade_id]
        await callback.message.edit_text(
            f"❌ <b>ОШИБКА</b>\n\n"
            f"У инициатора больше нет карты {initiator_card['name']}!",
            parse_mode="HTML"
        )
        return
    
    if not target_has_card:
        # Удаляем обмен из активных
        del active_trades[trade_id]
        await callback.message.edit_text(
            f"❌ <b>ОШИБКА</b>\n\n"
            f"У вас больше нет карты {target_card['name']}!",
            parse_mode="HTML"
        )
        return
    
    # Выполняем обмен картами
    # Удаляем карты у оригинальных владельцев
    initiator_cards = [c for c in initiator_cards if c["name"] != initiator_card["name"]]
    target_cards = [c for c in target_cards if c["name"] != target_card["name"]]
    
    # Добавляем карты новым владельцам
    initiator_cards.append(target_card)
    target_cards.append(initiator_card)
    
    # Обновляем данные пользователей в БД
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE users SET cards = ? WHERE user_id = ?", 
                   (json.dumps(initiator_cards), initiator_id))
    cursor.execute("UPDATE users SET cards = ? WHERE user_id = ?", 
                   (json.dumps(target_cards), target_id))
    
    conn.commit()
    conn.close()
    
    # Удаляем обмен из активных
    del active_trades[trade_id]
    
    # Отправляем подтверждение обоим сторонам
    initiator_name = trade_info["initiator_name"]
    target_name = trade_info["target_name"]
    
    await callback.message.edit_text(
        f"✅ <b>ОБМЕН ЗАВЕРШЕН</b>\n\n"
        f"Обмен между {initiator_name} и {target_name} успешно завершен!\n\n"
        f"🔄 {initiator_name} получил: {target_card['emoji']} {target_card['name']}\n"
        f"🔄 {target_name} получил: {initiator_card['emoji']} {initiator_card['name']}",
        parse_mode="HTML"
    )
    
    try:
        await bot.send_message(
            initiator_id,
            f"✅ <b>ОБМЕН ЗАВЕРШЕН</b>\n\n"
            f"Обмен с {target_name} успешно завершен!\n\n"
            f"🔄 Ты получил: {target_card['emoji']} {target_card['name']}\n"
            f"🔄 Ты отдал: {initiator_card['emoji']} {initiator_card['name']}",
            parse_mode="HTML"
        )
    except:
        pass  # Не удалось отправить сообщение инициатору

@router.callback_query(F.data.startswith("trade_decline:"))
async def trade_decline(callback: CallbackQuery, bot: Bot):
    """Отклонение предложения обмена"""
    try:
        _, trade_id = callback.data.split(":", 1)
    except ValueError:
        return await callback.answer("Ошибка данных!", show_alert=True)
    
    # Проверяем, существует ли обмен
    if trade_id not in active_trades:
        return await callback.message.edit_text(
            f"❌ <b>ОШИБКА</b>\n\n"
            f"Обмен не найден или уже завершен!",
            parse_mode="HTML"
        )
    
    trade_info = active_trades[trade_id]
    initiator_id = trade_info["initiator_id"]
    
    # Проверяем, что пользователь, отклоняющий обмен, является целью
    if callback.from_user.id != trade_info["target_id"]:
        return await callback.answer("Этот обмен не для вас!", show_alert=True)
    
    # Удаляем обмен из активных
    del active_trades[trade_id]
    
    # Сообщаем инициатору об отказе
    target_name = callback.from_user.first_name
    
    try:
        await bot.send_message(
            initiator_id,
            f"❌ <b>ОБМЕН ОТКЛОНЕН</b>\n\n"
            f"Пользователь {target_name} отклонил ваше предложение обмена.",
            parse_mode="HTML"
        )
    except:
        pass  # Не удалось отправить сообщение инициатору
    
    await callback.message.edit_text(
        f"❌ <b>ОБМЕН ОТКЛОНЕН</b>\n\n"
        f"Вы отклонили предложение обмена.",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "trade_cancel")
async def trade_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена торговли"""
    await state.clear()
    await callback.message.edit_text(
        f"❌ <b>ТОРГОВЛЯ ОТМЕНЕНА</b>",
        parse_mode="HTML"
    )
    await callback.answer()