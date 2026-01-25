from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
import asyncio

from config import EMOJI, CARDS, RARITY_COLORS, RARITY_NAMES
from database import DatabaseManager

router = Router()


# Определяем состояния для FSM
class SellCardStates(StatesGroup):
    waiting_for_price = State()
    waiting_for_confirmation = State()


def is_group_chat(message: Message) -> bool:
    return message.chat.type in ["group", "supergroup"]


def get_db(message_or_callback):
    """Получить БД для чата"""
    if isinstance(message_or_callback, Message):
        return DatabaseManager.get_db(message_or_callback.chat.id)
    elif isinstance(message_or_callback, CallbackQuery):
        return DatabaseManager.get_db(message_or_callback.message.chat.id)
    return None


async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None):
    """Безопасное редактирование сообщения с обработкой ошибок"""
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # Сообщение не изменилось - просто игнорируем
            pass
        else:
            raise
    except TelegramRetryAfter as e:
        # Ждём указанное время и пробуем снова
        await asyncio.sleep(e.retry_after)
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
        except:
            pass


# Товары магазина
SHOP_ITEMS = {
    "shield_1": {
        "name": "🛡️ Малый щит",
        "description": "Защита от 1 поражения",
        "price": 50,
        "type": "shield",
        "value": 1
    },
    "shield_3": {
        "name": "🛡️ Средний щит",
        "description": "Защита от 3 поражений",
        "price": 120,
        "type": "shield",
        "value": 3
    },
    "shield_5": {
        "name": "🛡️ Большой щит",
        "description": "Защита от 5 поражений",
        "price": 180,
        "type": "shield",
        "value": 5
    },
    "ticket_1": {
        "name": "🎫 Билет x1",
        "description": "1 билет на прокрутку",
        "price": 30,
        "type": "ticket",
        "value": 1
    },
    "ticket_5": {
        "name": "🎫 Билет x5",
        "description": "5 билетов на прокрутку",
        "price": 130,
        "type": "ticket",
        "value": 5
    },
    "ticket_10": {
        "name": "🎫 Билет x10",
        "description": "10 билетов на прокрутку",
        "price": 240,
        "type": "ticket",
        "value": 10
    },
}


# Комиссия за продажу на рынке (процент)
MARKET_FEE_PERCENTAGE = 10


def get_market_keyboard(db, user_id):
    """Создать клавиатуру главного меню магазина"""
    keyboard_buttons = []
    
    # Карты игроков (рынок)
    all_listings = db.get_all_listings()
    listings_count = len(all_listings) if all_listings else 0
    listings_text = f" ({listings_count})" if listings_count > 0 else ""
    keyboard_buttons.append([
        InlineKeyboardButton(text=f"🃏 Карты игроков{listings_text}", callback_data="market_cards")
    ])
    
    # Билеты
    keyboard_buttons.append([
        InlineKeyboardButton(text="🎫 Билеты", callback_data="market_category:tickets")
    ])
    
    # Щиты
    keyboard_buttons.append([
        InlineKeyboardButton(text="🛡️ Щиты", callback_data="market_category:shields")
    ])
    
    # Мои объявления
    my_listings = db.get_my_listings(user_id)
    my_listings_text = f" ({len(my_listings)})" if my_listings else ""
    keyboard_buttons.append([
        InlineKeyboardButton(text=f"📝 Мои объявления{my_listings_text}", callback_data="market_my_listings")
    ])
    
    # Продать карту
    keyboard_buttons.append([
        InlineKeyboardButton(text="📤 Продать карту", callback_data="market_sell_card")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


@router.message(Command("market"))
@router.message(Command("shop"))
async def show_market(message: Message):
    """Показать магазин"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    user_id = message.from_user.id
    db = get_db(message)
    
    if not db.get_user(user_id):
        db.create_user(user_id, message.from_user.username, message.from_user.first_name)
    
    user = db.get_user(user_id)
    coins = user.get("coins", 0)
    
    keyboard = get_market_keyboard(db, user_id)
    
    await message.reply(
        f"🛒 <b>МАГАЗИН</b>\n\n"
        f"💰 Твой баланс: <b>{coins}</b> 🪙\n\n"
        f"Выбери действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "market_cards")
async def show_market_cards(callback: CallbackQuery):
    """Показать карты на продажу от игроков"""
    db = get_db(callback)
    user_id = callback.from_user.id
    
    user = db.get_user(user_id)
    coins = user.get("coins", 0) if user else 0
    
    # Получаем все объявления (кроме своих)
    all_listings = db.get_all_listings()
    
    # Фильтруем свои объявления
    listings = [l for l in all_listings if l.get("seller_id") != user_id] if all_listings else []
    
    if not listings:
        text = "🃏 <b>КАРТЫ ИГРОКОВ</b>\n\n"
        text += "Пока никто не выставил карты на продажу.\n\n"
        text += "💡 Ты можешь продать свои карты через «📤 Продать карту»"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Продать карту", callback_data="market_sell_card")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="market_back")]
        ])
        
        await safe_edit_message(callback, text, keyboard)
        return await callback.answer()
    
    text = f"🃏 <b>КАРТЫ ИГРОКОВ</b>\n\n"
    text += f"💰 Твой баланс: <b>{coins}</b> 🪙\n\n"
    text += f"Доступно карт: <b>{len(listings)}</b>\n\n"
    
    keyboard_buttons = []
    
    # Сортируем по цене
    listings = sorted(listings, key=lambda x: x.get("price", 0))
    
    # Показываем максимум 10 карт
    for listing in listings[:10]:
        card_name = listing.get("card_name", "Unknown")
        price = listing.get("price", 0)
        listing_id = listing.get("id", 0)
        
        # Находим карту
        card = None
        for c in CARDS:
            if c["name"] == card_name:
                card = c
                break
        
        if card:
            rarity_color = RARITY_COLORS.get(card["rarity"], "⚪")
            power = card["attack"] + card["defense"]
            can_buy = coins >= price
            emoji_status = "✅" if can_buy else "❌"
            
            text += f"{rarity_color} {card['emoji']} <b>{card['name']}</b>\n"
            text += f"   💪{power} | 💰{price} 🪙\n"
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{emoji_status} {card['emoji']} {card['name']} — {price} 🪙",
                    callback_data=f"market_buy_card:{listing_id}"
                )
            ])
        else:
            text += f"❓ <b>{card_name}</b> — {price} 🪙\n"
    
    if len(listings) > 10:
        text += f"\n<i>...и ещё {len(listings) - 10} карт</i>"
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data="market_cards_refresh")
    ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="market_back")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await safe_edit_message(callback, text, keyboard)
    await callback.answer()


@router.callback_query(F.data == "market_cards_refresh")
async def refresh_market_cards(callback: CallbackQuery):
    """Обновить список карт (с другим callback_data чтобы избежать ошибки)"""
    await callback.answer("🔄 Обновляю...")
    await show_market_cards(callback)


@router.callback_query(F.data.startswith("market_buy_card:"))
async def buy_card_from_market(callback: CallbackQuery):
    """Купить карту у другого игрока"""
    try:
        listing_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return await callback.answer("❌ Ошибка данных", show_alert=True)
    
    db = get_db(callback)
    user_id = callback.from_user.id
    
    # Получаем объявление
    listing = db.get_listing_by_id(listing_id)
    
    if not listing:
        return await callback.answer("❌ Объявление не найдено или уже продано!", show_alert=True)
    
    card_name = listing.get("card_name")
    price = listing.get("price", 0)
    seller_id = listing.get("seller_id")
    
    # Проверяем, что это не своё объявление
    if seller_id == user_id:
        return await callback.answer("❌ Нельзя купить свою карту!", show_alert=True)
    
    # Проверяем баланс покупателя
    user = db.get_user(user_id)
    if not user:
        return await callback.answer("❌ Ошибка! Попробуй /market заново", show_alert=True)
    
    coins = user.get("coins", 0)
    if coins < price:
        return await callback.answer(f"❌ Недостаточно монет! Нужно {price} 🪙", show_alert=True)
    
    # Находим карту
    card = None
    for c in CARDS:
        if c["name"] == card_name:
            card = c
            break
    
    if not card:
        return await callback.answer("❌ Карта не найдена!", show_alert=True)
    
    # Рассчитываем комиссию
    fee = int(price * MARKET_FEE_PERCENTAGE / 100)
    seller_gets = price - fee
    
    # Выполняем транзакцию
    # 1. Списываем монеты у покупателя
    db.remove_coins(user_id, price)
    
    # 2. Начисляем монеты продавцу (за вычетом комиссии)
    db.add_coins(seller_id, seller_gets)
    
    # 3. Выдаём карту покупателю
    card_to_save = {
        "name": card["name"],
        "rarity": card["rarity"],
        "attack": card["attack"],
        "defense": card["defense"],
        "emoji": card["emoji"]
    }
    db.add_card(user_id, card_to_save)
    
    # 4. Удаляем объявление
    db.remove_listing(listing_id)
    
    # Получаем обновлённый баланс
    new_balance = db.get_coins(user_id)
    
    # Получаем имя продавца
    seller = db.get_user(seller_id)
    seller_name = seller.get("first_name") or seller.get("username") or "Игрок" if seller else "Игрок"
    
    rarity_color = RARITY_COLORS.get(card["rarity"], "⚪")
    power = card["attack"] + card["defense"]
    
    text = "✅ <b>ПОКУПКА УСПЕШНА!</b>\n\n"
    text += f"{rarity_color} {card['emoji']} <b>{card['name']}</b>\n"
    text += f"💪 Сила: {power}\n\n"
    text += f"💰 Цена: <b>{price}</b> 🪙\n"
    text += f"👤 Продавец: {seller_name}\n"
    text += f"💵 Твой остаток: <b>{new_balance}</b> 🪙"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🃏 Ещё карты", callback_data="market_cards")],
        [InlineKeyboardButton(text="🛒 В магазин", callback_data="market_back")]
    ])
    
    await safe_edit_message(callback, text, keyboard)
    await callback.answer("✅ Карта куплена!", show_alert=True)


@router.callback_query(F.data.startswith("market_category:"))
async def show_category(callback: CallbackQuery):
    """Показать категорию товаров"""
    category = callback.data.split(":")[1]
    db = get_db(callback)
    
    user = db.get_user(callback.from_user.id)
    coins = user.get("coins", 0) if user else 0
    
    keyboard_buttons = []
    
    if category == "tickets":
        items = ["ticket_1", "ticket_5", "ticket_10"]
        title = "🎫 БИЛЕТЫ"
    elif category == "shields":
        items = ["shield_1", "shield_3", "shield_5"]
        title = "🛡️ ЩИТЫ"
    else:
        items = []
        title = "Категория"
    
    text = f"🛒 <b>{title}</b>\n\n"
    text += f"💰 Баланс: <b>{coins}</b> 🪙\n\n"
    
    for item_id in items:
        item = SHOP_ITEMS.get(item_id)
        if item:
            text += f"{item['name']} — <b>{item['price']}</b> 🪙\n"
            text += f"   <i>{item['description']}</i>\n\n"
            
            can_buy = coins >= item['price']
            emoji = "✅" if can_buy else "❌"
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{emoji} {item['name']} ({item['price']} 🪙)",
                    callback_data=f"market_buy:{item_id}"
                )
            ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="market_back")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await safe_edit_message(callback, text, keyboard)
    await callback.answer()


@router.callback_query(F.data == "market_my_listings")
async def show_my_listings(callback: CallbackQuery):
    """Показать мои объявления"""
    db = get_db(callback)
    user_id = callback.from_user.id
    
    listings = db.get_my_listings(user_id)
    
    if not listings:
        text = "📝 <b>МОИ ОБЪЯВЛЕНИЯ</b>\n\n"
        text += "У тебя нет активных объявлений.\n\n"
        text += "📤 Используй «Продать карту» чтобы выставить карту на продажу."
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Продать карту", callback_data="market_sell_card")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="market_back")]
        ])
        
        await safe_edit_message(callback, text, keyboard)
        return await callback.answer()
    
    text = "📝 <b>МОИ ОБЪЯВЛЕНИЯ</b>\n\n"
    
    keyboard_buttons = []
    
    for listing in listings:
        listing_id = listing.get("id", 0)
        card_name = listing.get("card_name", "Unknown")
        price = listing.get("price", 0)
        
        # Находим карту по имени
        card = None
        for c in CARDS:
            if c["name"] == card_name:
                card = c
                break
        
        if card:
            rarity_color = RARITY_COLORS.get(card["rarity"], "⚪")
            power = card["attack"] + card["defense"]
            text += f"{rarity_color} {card['emoji']} <b>{card['name']}</b>\n"
            text += f"   💪{power} | 💰{price} 🪙\n"
            text += f"   📅 {listing['created_at'][:10]}\n\n"
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"❌ Снять {card['emoji']} {card['name']}",
                    callback_data=f"market_cancel_listing:{listing_id}"
                )
            ])
        else:
            text += f"❓ <b>{card_name}</b> — {price} 🪙\n\n"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"❌ Снять {card_name}",
                    callback_data=f"market_cancel_listing:{listing_id}"
                )
            ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="📤 Продать карту", callback_data="market_sell_card")
    ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="market_back")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await safe_edit_message(callback, text, keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("market_cancel_listing:"))
async def cancel_listing(callback: CallbackQuery):
    """Отменить объявление и вернуть карту"""
    try:
        listing_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return await callback.answer("❌ Ошибка данных", show_alert=True)
    
    db = get_db(callback)
    user_id = callback.from_user.id
    
    # Получаем объявление
    listing = db.get_listing_by_id(listing_id)
    
    if not listing:
        return await callback.answer("❌ Объявление не найдено!", show_alert=True)
    
    # Проверяем, что это объявление пользователя
    if listing.get("seller_id") != user_id:
        return await callback.answer("❌ Это не твоё объявление!", show_alert=True)
    
    card_name = listing.get("card_name")
    
    # Находим карту
    card = None
    for c in CARDS:
        if c["name"] == card_name:
            card = c
            break
    
    if not card:
        return await callback.answer("❌ Карта не найдена!", show_alert=True)
    
    # Возвращаем карту пользователю
    card_to_save = {
        "name": card["name"],
        "rarity": card["rarity"],
        "attack": card["attack"],
        "defense": card["defense"],
        "emoji": card["emoji"]
    }
    db.add_card(user_id, card_to_save)
    
    # Удаляем объявление
    db.remove_listing(listing_id)
    
    await callback.answer(f"✅ Объявление снято! {card['emoji']} {card['name']} возвращена", show_alert=True)
    
    # Обновляем список объявлений
    await show_my_listings(callback)


@router.callback_query(F.data == "market_sell_card")
async def sell_card_start(callback: CallbackQuery):
    """Начать продажу карты"""
    db = get_db(callback)
    user_id = callback.from_user.id
    
    user = db.get_user(user_id)
    if not user:
        return await callback.answer("Ошибка! Попробуй /market заново", show_alert=True)
    
    cards = user.get("cards", [])
    if not cards:
        return await callback.answer("У тебя нет карт для продажи!", show_alert=True)
    
    # Группируем карты по имени и считаем количество
    card_groups = {}
    for card in cards:
        name = card["name"]
        if name not in card_groups:
            card_groups[name] = {"card": card, "count": 0}
        card_groups[name]["count"] += 1
    
    # Сортируем по редкости
    rarity_order = {"special": 0, "mythic": 1, "legendary": 2, "epic": 3, "rare": 4, "common": 5}
    sorted_cards = sorted(
        card_groups.values(),
        key=lambda x: (rarity_order.get(x["card"]["rarity"], 99), -(x["card"]["attack"] + x["card"]["defense"]))
    )
    
    keyboard_buttons = []
    
    for item in sorted_cards[:15]:  # Максимум 15 карт
        card = item["card"]
        count = item["count"]
        rarity_color = RARITY_COLORS.get(card["rarity"], "⚪")
        dupe = f" x{count}" if count > 1 else ""
        power = card["attack"] + card["defense"]
        
        # Создаем callback_data с именем карты
        callback_data = f"market_sell_select:{card['name']}"
        # Ограничиваем длину callback_data до 64 символов
        if len(callback_data) > 64:
            callback_data = callback_data[:64]
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{rarity_color} {card['emoji']} {card['name']} (💪{power}){dupe}",
                callback_data=callback_data
            )
        ])
    
    if len(sorted_cards) > 15:
        keyboard_buttons.append([
            InlineKeyboardButton(text=f"...и ещё {len(sorted_cards) - 15} карт", callback_data="market_sell_more")
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="market_back")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    text = "📤 <b>ПРОДАЖА КАРТЫ</b>\n\n"
    text += f"📉 Комиссия рынка: <b>{MARKET_FEE_PERCENTAGE}%</b>\n\n"
    text += "Выбери карту для продажи:"
    
    await safe_edit_message(callback, text, keyboard)
    await callback.answer()


@router.callback_query(F.data == "market_sell_more")
async def sell_card_more(callback: CallbackQuery):
    """Показать больше карт для продажи"""
    await callback.answer("Показаны первые 15 карт. Продай некоторые, чтобы увидеть остальные.", show_alert=True)


@router.callback_query(F.data.startswith("market_sell_select:"))
async def sell_card_select(callback: CallbackQuery, state: FSMContext):
    """Выбор карты для продажи"""
    card_name = callback.data.split(":", 1)[1]
    db = get_db(callback)
    user_id = callback.from_user.id
    
    user = db.get_user(user_id)
    if not user:
        return await callback.answer("Ошибка! Попробуй /market заново", show_alert=True)
    
    # Находим карту по имени
    card = None
    for c in CARDS:
        if c["name"] == card_name:
            card = c
            break
    
    if not card:
        return await callback.answer("Карта не найдена!", show_alert=True)
    
    # Проверяем, есть ли такая карта у пользователя
    user_cards = user.get("cards", [])
    card_count = sum(1 for c in user_cards if c["name"] == card_name)
    
    if card_count == 0:
        return await callback.answer("У тебя нет этой карты!", show_alert=True)
    
    # Определяем рекомендуемую цену на основе редкости и силы
    power = card["attack"] + card["defense"]
    base_price = 0
    
    if card["rarity"] == "common":
        base_price = power * 2
    elif card["rarity"] == "rare":
        base_price = power * 4
    elif card["rarity"] == "epic":
        base_price = power * 8
    elif card["rarity"] == "legendary":
        base_price = power * 15
    elif card["rarity"] == "mythic":
        base_price = power * 25
    elif card["rarity"] == "special":
        base_price = power * 50
    else:
        base_price = power * 2
    
    # Минимальная цена 1 монета
    base_price = max(1, base_price)
    
    # Если у пользователя несколько таких карт, показываем количество
    count_text = f" (у тебя {card_count} шт.)" if card_count > 1 else ""
    
    rarity_color = RARITY_COLORS.get(card["rarity"], "⚪")
    rarity_name = RARITY_NAMES.get(card["rarity"], card["rarity"])
    
    text = "📤 <b>ПРОДАЖА КАРТЫ</b>\n\n"
    text += f"{card['emoji']} <b>{card['name']}</b>{count_text}\n"
    text += f"Редкость: {rarity_color} {rarity_name}\n"
    text += f"Сила: 💪{power}\n\n"
    text += f"💰 Рекомендуемая цена: <b>{base_price}</b> 🪙\n"
    text += f"📉 Комиссия рынка: <b>{MARKET_FEE_PERCENTAGE}%</b>\n\n"
    text += "Введи цену для выставления на продажу:"
    
    # Сохраняем данные в FSM
    await state.set_state(SellCardStates.waiting_for_price)
    await state.update_data(
        card_name=card_name, 
        base_price=base_price,
        chat_id=callback.message.chat.id
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="market_sell_cancel")]
    ])
    
    await safe_edit_message(callback, text, keyboard)
    await callback.answer()


@router.callback_query(F.data == "market_sell_cancel")
async def cancel_sell(callback: CallbackQuery, state: FSMContext):
    """Отмена продажи"""
    await state.clear()
    await callback.answer("Продажа отменена")
    await back_to_market(callback)


@router.callback_query(F.data.startswith("market_buy:"))
async def buy_item(callback: CallbackQuery):
    """Купить товар"""
    item_id = callback.data.split(":")[1]
    item = SHOP_ITEMS.get(item_id)
    
    if not item:
        return await callback.answer("Товар не найден!", show_alert=True)
    
    db = get_db(callback)
    user_id = callback.from_user.id
    
    user = db.get_user(user_id)
    if not user:
        return await callback.answer("Ошибка! Попробуй /market заново", show_alert=True)
    
    coins = user.get("coins", 0)
    
    if coins < item["price"]:
        return await callback.answer(
            f"Недостаточно монет! Нужно {item['price']} 🪙",
            show_alert=True
        )
    
    # Списываем монеты
    db.remove_coins(user_id, item["price"])
    
    # Выдаём товар
    if item["type"] == "ticket":
        db.add_spin_tickets(user_id, item["value"])
        result_text = f"Получено билетов: {item['value']}"
    elif item["type"] == "shield":
        db.add_shields(user_id, item["value"])
        result_text = f"Получено щитов: {item['value']}"
    else:
        result_text = "Товар получен"
    
    new_balance = db.get_coins(user_id)
    
    await callback.answer(f"✅ Куплено! {result_text}", show_alert=True)
    
    # Обновляем сообщение
    text = (
        f"✅ <b>ПОКУПКА УСПЕШНА!</b>\n\n"
        f"🛒 {item['name']}\n"
        f"💰 Списано: {item['price']} 🪙\n"
        f"💵 Остаток: {new_balance} 🪙\n\n"
        f"{result_text}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 В магазин", callback_data="market_back")]
    ])
    
    await safe_edit_message(callback, text, keyboard)


@router.callback_query(F.data == "market_back")
async def back_to_market(callback: CallbackQuery):
    """Вернуться в главное меню магазина"""
    db = get_db(callback)
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    coins = user.get("coins", 0) if user else 0
    
    keyboard = get_market_keyboard(db, user_id)
    
    text = (
        f"🛒 <b>МАГАЗИН</b>\n\n"
        f"💰 Твой баланс: <b>{coins}</b> 🪙\n\n"
        f"Выбери действие:"
    )
    
    await safe_edit_message(callback, text, keyboard)
    await callback.answer()


@router.message(StateFilter(SellCardStates.waiting_for_price))
async def sell_card_price_input(message: Message, state: FSMContext):
    """Обработка ввода цены для продажи карты"""
    # Проверяем, что вводится число
    try:
        price = int(message.text)
        if price <= 0:
            raise ValueError("Цена должна быть положительным числом")
        if price > 1000000:
            raise ValueError("Слишком высокая цена")
    except ValueError:
        await message.reply("❌ Введи корректную цену (целое число от 1 до 1,000,000)")
        return
    
    # Получаем данные из FSM
    data = await state.get_data()
    card_name = data.get("card_name")
    base_price = data.get("base_price")
    
    # Находим карту
    card = None
    for c in CARDS:
        if c["name"] == card_name:
            card = c
            break
    
    if not card:
        await state.clear()
        return await message.reply("❌ Карта не найдена")
    
    # Получаем пользователя и проверяем наличие карты
    db = DatabaseManager.get_db(message.chat.id)
    user = db.get_user(message.from_user.id)
    if not user:
        await state.clear()
        return await message.reply("❌ Ошибка! Попробуй /market заново")
    
    user_cards = user.get("cards", [])
    card_count = sum(1 for c in user_cards if c["name"] == card_name)
    
    if card_count == 0:
        await state.clear()
        return await message.reply("❌ У тебя нет этой карты!")
    
    # Рассчитываем комиссию
    fee = int(price * MARKET_FEE_PERCENTAGE / 100)
    net_price = price - fee
    
    rarity_color = RARITY_COLORS.get(card["rarity"], "⚪")
    rarity_name = RARITY_NAMES.get(card["rarity"], card["rarity"])
    power = card["attack"] + card["defense"]
    
    # Подготовка текста подтверждения
    text = "📤 <b>ПОДТВЕРЖДЕНИЕ ПРОДАЖИ</b>\n\n"
    text += f"{card['emoji']} <b>{card['name']}</b>\n"
    text += f"Редкость: {rarity_color} {rarity_name}\n"
    text += f"Сила: 💪{power}\n\n"
    text += f"💰 Цена: <b>{price}</b> 🪙\n"
    text += f"📉 Комиссия рынка ({MARKET_FEE_PERCENTAGE}%): <b>-{fee}</b> 🪙\n"
    text += f"💳 Ты получишь: <b>{net_price}</b> 🪙\n\n"
    text += "Подтвердить продажу?"
    
    # Клавиатура с кнопками подтверждения
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"market_sell_confirm:{card_name}:{price}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="market_back")
        ]
    ])
    
    # Сохраняем цену в FSM
    await state.set_state(SellCardStates.waiting_for_confirmation)
    await state.update_data(price=price)
    
    await message.reply(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("market_sell_confirm:"))
async def sell_card_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение продажи карты"""
    try:
        _, card_name, price_str = callback.data.split(":", 2)
        price = int(price_str)
    except ValueError:
        return await callback.answer("❌ Ошибка данных", show_alert=True)
    
    db = get_db(callback)
    user_id = callback.from_user.id
    
    # Получаем пользователя
    user = db.get_user(user_id)
    if not user:
        await state.clear()
        return await callback.answer("❌ Ошибка! Попробуй /market заново", show_alert=True)
    
    # Проверяем наличие карты у пользователя
    user_cards = user.get("cards", [])
    card_count = sum(1 for c in user_cards if c["name"] == card_name)
    
    if card_count == 0:
        await state.clear()
        return await callback.answer("❌ У тебя нет этой карты!", show_alert=True)
    
    # Находим карту
    card = None
    for c in CARDS:
        if c["name"] == card_name:
            card = c
            break
    
    if not card:
        await state.clear()
        return await callback.answer("❌ Карта не найдена!", show_alert=True)
    
    # Рассчитываем комиссию и добавляем объявление на рынок
    fee = int(price * MARKET_FEE_PERCENTAGE / 100)
    net_price = price - fee
    
    # Удаляем одну карту у пользователя
    db.remove_card_from_user(user_id, card_name)
    
    # Добавляем объявление на рынок
    db.add_listing(user_id, card_name, price)
    
    # Очищаем FSM
    await state.clear()
    
    rarity_color = RARITY_COLORS.get(card["rarity"], "⚪")
    
    # Сообщаем пользователю об успешной продаже
    text = "✅ <b>КАРТА ВЫСТАВЛЕНА НА ПРОДАЖУ!</b>\n\n"
    text += f"{rarity_color} {card['emoji']} <b>{card['name']}</b>\n\n"
    text += f"💰 Цена: <b>{price}</b> 🪙\n"
    text += f"📉 Комиссия: <b>-{fee}</b> 🪙\n"
    text += f"💳 После продажи ты получишь: <b>{net_price}</b> 🪙\n\n"
    text += "💡 Карта появится в разделе «🃏 Карты игроков»"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Мои объявления", callback_data="market_my_listings")],
        [InlineKeyboardButton(text="🛒 В магазин", callback_data="market_back")]
    ])
    
    await safe_edit_message(callback, text, keyboard)
    await callback.answer("✅ Карта выставлена на продажу!", show_alert=True)