from aiogram import Router, F, Bot
from aiogram.types import Message, ChatMemberAdministrator, ChatMemberOwner, ChatPermissions
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime, timedelta
import re

from config import EMOJI, BOT_CREATORS, RANKS, PERMISSION_DESCRIPTIONS
from database import DatabaseManager

router = Router()


def is_group_chat(message: Message) -> bool:
    return message.chat.type in ["group", "supergroup"]


def get_db(message: Message):
    """Получить БД для текущего чата"""
    return DatabaseManager.get_db(message.chat.id)


async def is_owner_or_creator(message: Message, bot: Bot) -> bool:
    """Проверка на создателя бота или владельца группы"""
    if message.from_user.username and message.from_user.username in BOT_CREATORS:
        return True
    
    if message.chat.type in ["group", "supergroup"]:
        try:
            member = await bot.get_chat_member(message.chat.id, message.from_user.id)
            if isinstance(member, ChatMemberOwner):
                return True
        except:
            pass
    
    return False


async def get_target_user(message: Message, bot: Bot) -> tuple:
    """
    Получить целевого пользователя из реплая или @username/ID
    Возвращает (user_id, first_name, username, remaining_args, error_message)
    """
    args = message.text.split()
    global_db = DatabaseManager.get_global_db()
    
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        remaining = " ".join(args[1:]) if len(args) > 1 else ""
        return target.id, target.first_name, target.username, remaining, None
    
    if len(args) > 1:
        arg = args[1]
        
        if arg.startswith("@"):
            username = arg[1:]
            user_data = global_db.find_by_username(username)
            
            if user_data:
                remaining = " ".join(args[2:]) if len(args) > 2 else ""
                return user_data['user_id'], user_data.get('first_name') or username, username, remaining, None
            else:
                return None, None, None, None, f"Пользователь @{username} не найден в базе!\nОн должен хотя бы раз написать в чат с ботом."
        
        try:
            user_id = int(arg)
            try:
                chat = await bot.get_chat(user_id)
                remaining = " ".join(args[2:]) if len(args) > 2 else ""
                return user_id, chat.first_name or str(user_id), chat.username, remaining, None
            except:
                db = get_db(message)
                user = db.get_user(user_id)
                if user:
                    remaining = " ".join(args[2:]) if len(args) > 2 else ""
                    return user_id, user.get("first_name", str(user_id)), user.get("username"), remaining, None
                remaining = " ".join(args[2:]) if len(args) > 2 else ""
                return user_id, str(user_id), None, remaining, None
        except ValueError:
            pass
    
    return None, None, None, None, "Ответь на сообщение или укажи @username / ID"


def parse_duration(text: str) -> tuple:
    """Парсит длительность из начала текста"""
    if not text:
        return None, None
    
    patterns = [
        (r'^(\d+)\s*d\b', 1440, 'дн.'),
        (r'^(\d+)\s*д\b', 1440, 'дн.'),
        (r'^(\d+)\s*h\b', 60, 'ч.'),
        (r'^(\d+)\s*ч\b', 60, 'ч.'),
        (r'^(\d+)\s*m\b', 1, 'мин.'),
        (r'^(\d+)\s*м\b', 1, 'мин.'),
        (r'^(\d+)\s*min\b', 1, 'мин.'),
        (r'^(\d+)\s*мин\b', 1, 'мин.'),
    ]
    
    for pattern, multiplier, suffix in patterns:
        match = re.search(pattern, text.lower())
        if match:
            value = int(match.group(1))
            minutes = value * multiplier
            time_str = f"{value} {suffix}"
            return minutes, time_str
    
    return None, None


def parse_args_after_target(message: Message, remaining_args: str) -> tuple:
    """Парсит аргументы после цели"""
    duration = None
    duration_str = None
    reason = "Не указана"
    
    if remaining_args:
        minutes, time_str = parse_duration(remaining_args)
        
        if minutes:
            duration = minutes
            duration_str = time_str
            parts = remaining_args.split(maxsplit=1)
            if len(parts) > 1:
                reason = parts[1]
        else:
            reason = remaining_args
    
    return duration, duration_str, reason


async def try_restrict_member(bot: Bot, chat_id: int, user_id: int, until_date: datetime = None) -> tuple:
    """Попытка замутить пользователя"""
    try:
        await bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        return True, None
    except TelegramBadRequest as e:
        error = str(e).lower()
        if "not enough rights" in error:
            return False, "Боту нужны права администратора!"
        elif "supergroup" in error:
            return False, "Включи историю чата в настройках группы"
        elif "can't restrict self" in error:
            return False, "Нельзя ограничить бота!"
        elif "user is an administrator" in error:
            return False, "Нельзя ограничить администратора!"
        elif "user_not_participant" in error:
            return False, "Пользователь не в чате!"
        else:
            return False, str(e)
    except Exception as e:
        return False, str(e)


async def try_unrestrict_member(bot: Bot, chat_id: int, user_id: int) -> tuple:
    """Попытка размутить пользователя"""
    try:
        await bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        return True, None
    except Exception as e:
        return False, str(e)


async def try_ban_member(bot: Bot, chat_id: int, user_id: int, until_date: datetime = None) -> tuple:
    """Попытка забанить пользователя"""
    try:
        if until_date:
            await bot.ban_chat_member(chat_id, user_id, until_date=until_date)
        else:
            await bot.ban_chat_member(chat_id, user_id)
        return True, None
    except TelegramBadRequest as e:
        error = str(e).lower()
        if "not enough rights" in error:
            return False, "Боту нужны права администратора!"
        elif "supergroup" in error:
            return False, "Включи историю чата в настройках группы"
        elif "can't remove chat owner" in error:
            return False, "Нельзя забанить владельца!"
        elif "user is an administrator" in error:
            return False, "Нельзя забанить администратора!"
        elif "user_not_participant" in error:
            return False, "Пользователь не в чате!"
        else:
            return False, str(e)
    except Exception as e:
        return False, str(e)


async def try_unban_member(bot: Bot, chat_id: int, user_id: int) -> tuple:
    """Попытка разбанить пользователя"""
    try:
        await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        return True, None
    except Exception as e:
        return False, str(e)


async def try_kick_member(bot: Bot, chat_id: int, user_id: int) -> tuple:
    """Попытка кикнуть пользователя"""
    try:
        await bot.ban_chat_member(chat_id, user_id)
        await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        return True, None
    except TelegramBadRequest as e:
        error = str(e).lower()
        if "not enough rights" in error:
            return False, "Боту нужны права администратора!"
        elif "user is an administrator" in error:
            return False, "Нельзя кикнуть администратора!"
        else:
            return False, str(e)
    except Exception as e:
        return False, str(e)


async def get_user_permissions(message: Message, bot: Bot, user_id: int = None) -> dict:
    """Получить права пользователя"""
    if user_id is None:
        user_id = message.from_user.id
    
    username = None
    try:
        if user_id == message.from_user.id:
            username = message.from_user.username
        else:
            db = get_db(message)
            user_data = db.get_user(user_id)
            if user_data:
                username = user_data.get("username")
    except:
        pass
    
    # Создатели бота
    if username and username.lower() in [c.lower() for c in BOT_CREATORS]:
        return {
            "level": 99,
            "permissions": ["all"],
            "is_bot_creator": True,
            "rank_name": "Создатель бота",
            "rank_emoji": "💠"
        }
    
    # В группах проверяем статус
    if is_group_chat(message):
        try:
            member = await bot.get_chat_member(message.chat.id, user_id)
            db = get_db(message)
            
            if isinstance(member, ChatMemberOwner):
                rank = db.get_user_rank(user_id)
                if rank["rank_level"] < 6:
                    db.set_user_rank(user_id, 6, "Владелец")
                return {
                    "level": 6,
                    "permissions": ["all"],
                    "is_owner": True,
                    "rank_name": RANKS[6]["name"],
                    "rank_emoji": RANKS[6]["emoji"]
                }
            elif isinstance(member, ChatMemberAdministrator):
                rank = db.get_user_rank(user_id)
                if rank["rank_level"] < 3:
                    return {
                        "level": 3,
                        "permissions": RANKS[3]["permissions"],
                        "is_tg_admin": True,
                        "rank_name": RANKS[3]["name"],
                        "rank_emoji": RANKS[3]["emoji"]
                    }
        except:
            pass
    
    db = get_db(message)
    rank = db.get_user_rank(user_id)
    rank_level = rank["rank_level"]
    rank_data = RANKS.get(rank_level, RANKS[0])
    
    return {
        "level": rank_level,
        "permissions": rank_data["permissions"],
        "is_bot_creator": False,
        "is_owner": False,
        "rank_name": rank_data["name"],
        "rank_emoji": rank_data["emoji"]
    }


def has_permission(permissions: dict, required: str) -> bool:
    perms = permissions.get("permissions", [])
    if "all" in perms:
        return True
    return required in perms


def can_promote_to(permissions: dict, target_rank: int) -> bool:
    if has_permission(permissions, "all"):
        return True
    for i in range(target_rank, 0, -1):
        if has_permission(permissions, f"promote_{i}"):
            return target_rank <= i
    return False


def mention_user(user_id: int, first_name: str, username: str = None) -> str:
    """Создать упоминание пользователя"""
    name = first_name or username or str(user_id)
    return f'<a href="tg://user?id={user_id}">{name}</a>'


def parse_rank_from_text(text: str) -> tuple:
    """Парсит ранг и титул из текста"""
    if not text:
        return 1, ""
    
    text = text.strip()
    
    rank_names = {
        "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
        "мл.модератор": 1, "млмодератор": 1, "мл модератор": 1,
        "младший модератор": 1, "junior mod": 1, "jmod": 1,
        "ст.модератор": 2, "стмодератор": 2, "ст модератор": 2,
        "старший модератор": 2, "модератор": 2, "модер": 2, "mod": 2,
        "мл.админ": 3, "младмин": 3, "мл админ": 3,
        "младший админ": 3, "младший администратор": 3, "jadmin": 3,
        "гл.админ": 4, "главадмин": 4, "гл админ": 4,
        "главный админ": 4, "главный администратор": 4, "админ": 4, "admin": 4,
        "со-владелец": 5, "совладелец": 5, "со владелец": 5,
        "соовнер": 5, "co-owner": 5, "coowner": 5, "owner": 5, "владелец": 5,
    }
    
    parts = text.split(maxsplit=1)
    first_part = parts[0].lower()
    
    if first_part in rank_names:
        rank_level = rank_names[first_part]
        custom_title = parts[1] if len(parts) > 1 else ""
        return rank_level, custom_title
    
    try:
        rank_level = int(first_part)
        if 1 <= rank_level <= 5:
            custom_title = parts[1] if len(parts) > 1 else ""
            return rank_level, custom_title
    except ValueError:
        pass
    
    for rank_name, rank_level in rank_names.items():
        if text.lower().startswith(rank_name):
            remaining = text[len(rank_name):].strip()
            return rank_level, remaining
    
    return 1, text


# === ОБЪЯВЛЕНИЯ ===

@router.message(Command("announce"))
@router.message(Command("ann"))
@router.message(Command("объявление"))
async def announce_message(message: Message, bot: Bot):
    """Создать объявление и закрепить его"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    
    if perms["level"] < 5 and not has_permission(perms, "all"):
        return await message.reply(
            f"{EMOJI['cross']} Команда доступна только:\n"
            f"• 👑 Со-Владельцам\n"
            f"• 🏆 Владельцам\n"
            f"• 💠 Создателям бота"
        )
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        return await message.reply(
            f"📢 <b>Объявление</b>\n\n"
            f"<b>Использование:</b>\n"
            f"<code>/announce текст объявления</code>\n\n"
            f"<b>Пример:</b>\n"
            f"<code>/announce Внимание! Завтра в 18:00 турнир!</code>",
            parse_mode="HTML"
        )
    
    announcement_text = args[1]
    
    formatted_announcement = (
        f"📢 <b>ОБЪЯВЛЕНИЕ</b>\n"
        f"{'━' * 25}\n\n"
        f"{announcement_text}\n\n"
        f"{'━' * 25}\n"
        f"👤 <i>От: {message.from_user.first_name}</i>\n"
        f"📅 <i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"
    )
    
    try:
        announcement_msg = await bot.send_message(
            chat_id=message.chat.id,
            text=formatted_announcement,
            parse_mode="HTML"
        )
        
        try:
            await bot.pin_chat_message(
                chat_id=message.chat.id,
                message_id=announcement_msg.message_id,
                disable_notification=False
            )
            
            try:
                await message.delete()
            except:
                pass
            
        except TelegramBadRequest as e:
            error = str(e).lower()
            if "not enough rights" in error:
                await message.reply(
                    f"⚠️ Объявление отправлено, но закрепить не удалось!\n"
                    f"<i>Боту нужны права на закрепление сообщений</i>",
                    parse_mode="HTML"
                )
            else:
                await message.reply(f"⚠️ Ошибка закрепления: {e}")
                
    except Exception as e:
        await message.reply(f"{EMOJI['cross']} Ошибка: {e}")


@router.message(Command("unpin"))
async def unpin_message(message: Message, bot: Bot):
    """Открепить сообщение"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    
    if perms["level"] < 5 and not has_permission(perms, "all"):
        return await message.reply(f"{EMOJI['cross']} Недостаточно прав!")
    
    try:
        if message.reply_to_message:
            await bot.unpin_chat_message(
                chat_id=message.chat.id,
                message_id=message.reply_to_message.message_id
            )
            await message.reply(f"{EMOJI['check']} Сообщение откреплено!")
        else:
            args = message.text.split()
            if len(args) > 1 and args[1].lower() == "all":
                await bot.unpin_all_chat_messages(chat_id=message.chat.id)
                await message.reply(f"{EMOJI['check']} Все сообщения откреплены!")
            else:
                await bot.unpin_chat_message(chat_id=message.chat.id)
                await message.reply(f"{EMOJI['check']} Последнее закреплённое сообщение откреплено!")
    except TelegramBadRequest as e:
        await message.reply(f"{EMOJI['cross']} Ошибка: {e}")


@router.message(Command("pin"))
async def pin_message(message: Message, bot: Bot):
    """Закрепить сообщение"""
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    
    if not has_permission(perms, "pin_messages") and not has_permission(perms, "all"):
        return await message.reply(f"{EMOJI['cross']} Недостаточно прав!")
    
    if not message.reply_to_message:
        return await message.reply(
            f"📌 <b>Закрепление</b>\n\n"
            f"Ответь на сообщение, которое хочешь закрепить:\n"
            f"<code>/pin</code> — с уведомлением\n"
            f"<code>/pin silent</code> — без уведомления",
            parse_mode="HTML"
        )
    
    args = message.text.split()
    silent = len(args) > 1 and args[1].lower() in ["silent", "тихо", "s"]
    
    try:
        await bot.pin_chat_message(
            chat_id=message.chat.id,
            message_id=message.reply_to_message.message_id,
            disable_notification=silent
        )
        await message.reply(f"{EMOJI['check']} Сообщение закреплено!")
    except TelegramBadRequest as e:
        await message.reply(f"{EMOJI['cross']} Ошибка: {e}")


# === РАНГИ ===

@router.message(Command("promote"))
async def promote_user(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    
    if perms["level"] < 4 and not has_permission(perms, "all"):
        return await message.reply(f"{EMOJI['cross']} Нужен ранг {RANKS[4]['emoji']} {RANKS[4]['name']} или выше!")
    
    target_id, first_name, username, remaining_args, error = await get_target_user(message, bot)
    
    if error:
        ranks_text = "\n".join([f"  {info['emoji']} <code>{level}</code> — {info['name']}" for level, info in RANKS.items() if 0 < level < 6])
        return await message.reply(
            f"{EMOJI['promote']} <b>Повышение</b>\n\n"
            f"<b>Использование:</b>\n"
            f"<code>/promote @user [ранг] [титул]</code>\n"
            f"<code>/promote [ранг] [титул]</code> (реплай)\n\n"
            f"<b>Ранги:</b>\n{ranks_text}",
            parse_mode="HTML"
        )
    
    if target_id == message.from_user.id:
        return await message.reply(f"{EMOJI['cross']} Нельзя повысить себя!")
    
    new_rank, custom_title = parse_rank_from_text(remaining_args)
    new_rank = max(1, min(5, new_rank))
    
    if not can_promote_to(perms, new_rank) and perms["level"] < 6:
        max_rank = 0
        for i in range(5, 0, -1):
            if has_permission(perms, f"promote_{i}"):
                max_rank = i
                break
        if max_rank > 0:
            return await message.reply(f"{EMOJI['cross']} Максимум до {RANKS[max_rank]['emoji']} {RANKS[max_rank]['name']}!")
        else:
            return await message.reply(f"{EMOJI['cross']} У тебя нет прав на повышение!")
    
    if new_rank >= perms["level"] and perms["level"] < 99:
        return await message.reply(f"{EMOJI['cross']} Нельзя повысить до своего ранга или выше!")
    
    db = get_db(message)
    target_rank = db.get_user_rank(target_id)
    
    if target_rank["rank_level"] >= perms["level"] and perms["level"] < 99:
        return await message.reply(f"{EMOJI['cross']} Нельзя изменять ранг равного или старшего!")
    
    if not db.get_user(target_id):
        db.create_user(target_id, username, first_name)
    
    # Обновляем глобальную БД
    DatabaseManager.get_global_db().update_user(target_id, username, first_name)
    
    db.set_user_rank(target_id, new_rank, custom_title, message.from_user.id)
    
    rank_info = RANKS[new_rank]
    old_rank_info = RANKS.get(target_rank["rank_level"], RANKS[0])
    
    # Пытаемся выдать права в Telegram
    tg_status = ""
    try:
        await bot.promote_chat_member(
            chat_id=message.chat.id,
            user_id=target_id,
            can_delete_messages=new_rank >= 1,
            can_restrict_members=new_rank >= 1,
            can_pin_messages=new_rank >= 2,
            can_invite_users=new_rank >= 2,
            can_manage_video_chats=new_rank >= 3,
            can_promote_members=new_rank >= 5 and perms["level"] >= 6,
            can_change_info=new_rank >= 4
        )
        
        if custom_title:
            try:
                await bot.set_chat_administrator_custom_title(
                    chat_id=message.chat.id,
                    user_id=target_id,
                    custom_title=custom_title[:16]
                )
            except:
                pass
        
        tg_status = "\n\n✅ <i>Права Telegram выданы</i>"
    except Exception as e:
        tg_status = f"\n\n⚠️ <i>Права Telegram не выданы: проверь права бота</i>"
    
    await message.reply(
        f"{EMOJI['promote']} <b>ПОВЫШЕНИЕ!</b>\n\n"
        f"👤 {mention_user(target_id, first_name, username)}\n"
        f"📊 {old_rank_info['emoji']} → {rank_info['emoji']} <b>{rank_info['name']}</b>\n"
        f"{f'🏷️ Титул: <b>{custom_title}</b>' if custom_title else ''}\n\n"
        f"👮 {message.from_user.mention_html()}{tg_status}",
        parse_mode="HTML"
    )


@router.message(Command("demote"))
async def demote_user(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    
    if not has_permission(perms, "demote") and not has_permission(perms, "all"):
        return await message.reply(f"{EMOJI['cross']} Нужен ранг {RANKS[5]['emoji']} {RANKS[5]['name']} или выше!")
    
    target_id, first_name, username, remaining_args, error = await get_target_user(message, bot)
    
    if error:
        return await message.reply(
            f"{EMOJI['demote']} <b>Понижение</b>\n\n"
            f"<code>/demote @user</code> — на 1 ранг\n"
            f"<code>/demote @user 0</code> — снять все",
            parse_mode="HTML"
        )
    
    if target_id == message.from_user.id:
        return await message.reply(f"{EMOJI['cross']} Нельзя понизить себя!")
    
    db = get_db(message)
    target_rank = db.get_user_rank(target_id)
    
    if target_rank["rank_level"] >= perms["level"] and perms["level"] < 99:
        return await message.reply(f"{EMOJI['cross']} Нельзя понизить равного или старшего!")
    
    new_rank = max(0, target_rank["rank_level"] - 1)
    
    if remaining_args:
        try:
            new_rank = max(0, int(remaining_args.split()[0]))
        except ValueError:
            pass
    
    db.set_user_rank(target_id, new_rank, "", message.from_user.id)
    
    rank_info = RANKS[new_rank]
    old_rank_info = RANKS.get(target_rank["rank_level"], RANKS[0])
    
    try:
        if new_rank == 0:
            await bot.promote_chat_member(
                chat_id=message.chat.id,
                user_id=target_id,
                can_delete_messages=False,
                can_restrict_members=False,
                can_pin_messages=False,
                can_invite_users=False,
                can_manage_video_chats=False,
                can_promote_members=False,
                can_change_info=False
            )
    except:
        pass
    
    await message.reply(
        f"{EMOJI['demote']} <b>ПОНИЖЕНИЕ</b>\n\n"
        f"👤 {mention_user(target_id, first_name, username)}\n"
        f"📊 {old_rank_info['emoji']} → {rank_info['emoji']} <b>{rank_info['name']}</b>\n\n"
        f"👮 {message.from_user.mention_html()}",
        parse_mode="HTML"
    )


@router.message(Command("ranks"))
@router.message(Command("staff"))
@router.message(Command("admins"))
async def show_ranks(message: Message):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    db = get_db(message)
    ranks = db.get_chat_ranks()
    
    if not ranks:
        return await message.reply(f"{EMOJI['rank']} Нет администрации!\n/promote для назначения", parse_mode="HTML")
    
    by_rank = {}
    for r in ranks:
        level = r["rank_level"]
        if level not in by_rank:
            by_rank[level] = []
        by_rank[level].append(r)
    
    text = f"{EMOJI['crown']} <b>АДМИНИСТРАЦИЯ</b>\n\n"
    
    for level in sorted(by_rank.keys(), reverse=True):
        rank_info = RANKS[level]
        text += f"{rank_info['emoji']} <b>{rank_info['name']}:</b>\n"
        for user in by_rank[level]:
            name = user["first_name"] or user["username"] or "Пользователь"
            title = f" • <i>{user['custom_title']}</i>" if user["custom_title"] else ""
            text += f"   └ {name}{title}\n"
        text += "\n"
    
    await message.reply(text, parse_mode="HTML")


@router.message(Command("myrank"))
async def show_my_rank(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    
    text = f"{perms['rank_emoji']} <b>Твой ранг:</b> {perms['rank_name']}"
    
    if perms.get("is_bot_creator"):
        text += f"\n\n💠 <i>Создатель бота</i>"
    elif perms.get("is_owner"):
        text += f"\n\n🏆 <i>Владелец группы</i>"
    
    await message.reply(text, parse_mode="HTML")


@router.message(Command("ranklist"))
async def show_all_ranks(message: Message):
    text = f"{EMOJI['rank']} <b>РАНГИ</b>\n\n"
    
    for level, info in RANKS.items():
        if level == 99:
            continue
        text += f"{info['emoji']} <b>{info['name']}</b> (ур.{level})\n"
    
    text += f"\n💠 <b>Создатель бота</b> (ур.99)"
    
    await message.reply(text, parse_mode="HTML")


@router.message(Command("perms"))
async def show_permissions(message: Message, bot: Bot):
    args = message.text.split()
    
    if len(args) > 1:
        try:
            target_level = int(args[1])
        except:
            target_level = None
    else:
        perms = await get_user_permissions(message, bot)
        target_level = perms["level"]
    
    if target_level not in RANKS:
        return await message.reply(f"{EMOJI['cross']} Ранг не найден!")
    
    rank_info = RANKS[target_level]
    text = f"{rank_info['emoji']} <b>{rank_info['name']}</b>\n\n"
    
    if "all" in rank_info["permissions"]:
        text += f"👑 <b>ВСЕ ПРАВА</b>"
    elif rank_info["permissions"]:
        for perm in rank_info["permissions"]:
            desc = PERMISSION_DESCRIPTIONS.get(perm, perm)
            text += f"• {desc}\n"
    else:
        text += "<i>Нет прав</i>"
    
    await message.reply(text, parse_mode="HTML")


# === ПРАВИЛА ===

@router.message(Command("rules"))
async def show_rules(message: Message):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    db = get_db(message)
    rules = db.get_rules()
    
    if rules:
        await message.reply(f"{EMOJI['rules']} <b>ПРАВИЛА</b>\n\n{rules}", parse_mode="HTML")
    else:
        await message.reply(f"{EMOJI['rules']} Правила не установлены", parse_mode="HTML")


@router.message(Command("setrules"))
async def set_rules(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    
    if not has_permission(perms, "set_rules") and not has_permission(perms, "all"):
        return await message.reply(f"{EMOJI['cross']} Нет прав!")
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("/setrules <текст>")
    
    db = get_db(message)
    db.set_rules(args[1])
    await message.reply(f"{EMOJI['check']} Правила установлены!")


# === WARN ===

@router.message(Command("warn"))
async def warn_user(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    
    if not has_permission(perms, "warn") and not has_permission(perms, "all"):
        return await message.reply(f"{EMOJI['cross']} Нет прав!")
    
    target_id, first_name, username, remaining_args, error = await get_target_user(message, bot)
    
    if error:
        return await message.reply(
            f"{EMOJI['warn']} <b>Варн</b>\n\n"
            f"<code>/warn @user</code>\n"
            f"<code>/warn @user причина</code>\n"
            f"<code>/warn @user 1h причина</code>",
            parse_mode="HTML"
        )
    
    if target_id == message.from_user.id:
        return await message.reply(f"{EMOJI['cross']} Нельзя варнить себя!")
    
    target_perms = await get_user_permissions(message, bot, target_id)
    if target_perms["level"] >= perms["level"] and perms["level"] < 99:
        return await message.reply(f"{EMOJI['cross']} Нельзя варнить {target_perms['rank_emoji']} {target_perms['rank_name']}!")
    
    duration, duration_str, reason = parse_args_after_target(message, remaining_args)
    
    if not duration_str:
        duration_str = "навсегда"
    
    db = get_db(message)
    
    if not db.get_user(target_id):
        db.create_user(target_id, username, first_name)
    
    duration_hours = duration / 60 if duration else None
    db.add_warning(target_id, reason, message.from_user.id,
                   int(duration_hours) if duration_hours else None)
    warns = db.get_warnings(target_id)
    
    warn_bar = "🔴" * min(warns, 3) + "⚪" * max(0, 3 - warns)
    
    text = (
        f"{EMOJI['warn']} <b>ПРЕДУПРЕЖДЕНИЕ</b>\n\n"
        f"👤 {mention_user(target_id, first_name, username)}\n"
        f"📝 {reason}\n"
        f"⏰ {duration_str}\n\n"
        f"[{warn_bar}] {warns}/3\n\n"
        f"👮 {message.from_user.mention_html()}"
    )
    
    if warns >= 3:
        success, ban_error = await try_ban_member(bot, message.chat.id, target_id)
        if success:
            db.clear_warnings(target_id)
            text += f"\n\n{EMOJI['ban']} <b>АВТОБАН!</b>"
        else:
            text += f"\n\n⚠️ Автобан не удался: {ban_error}"
            db.clear_warnings(target_id)
    
    await message.reply(text, parse_mode="HTML")


@router.message(Command("unwarn"))
async def unwarn_user(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    
    if not has_permission(perms, "unwarn") and not has_permission(perms, "all"):
        return await message.reply(f"{EMOJI['cross']} Нет прав!")
    
    target_id, first_name, username, remaining_args, error = await get_target_user(message, bot)
    
    if error:
        return await message.reply(
            f"{EMOJI['check']} <b>Снятие варна</b>\n\n"
            f"<code>/unwarn @user</code> — снять 1\n"
            f"<code>/unwarn @user all</code> — снять все",
            parse_mode="HTML"
        )
    
    db = get_db(message)
    clear_all = remaining_args and remaining_args.lower() in ["all", "все"]
    
    if clear_all:
        db.clear_warnings(target_id)
        await message.reply(f"{EMOJI['check']} Все варны сняты с {mention_user(target_id, first_name, username)}!", parse_mode="HTML")
    else:
        if db.get_warnings(target_id) == 0:
            return await message.reply("Нет варнов!")
        db.remove_one_warning(target_id)
        warns = db.get_warnings(target_id)
        await message.reply(f"{EMOJI['check']} -1 варн! Осталось: {warns}/3", parse_mode="HTML")


@router.message(Command("warns"))
async def view_warns(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    
    target_id, first_name, username, remaining_args, error = await get_target_user(message, bot)
    
    if error:
        target_id = message.from_user.id
        first_name = message.from_user.first_name
        username = message.from_user.username
    elif not has_permission(perms, "view_warns") and target_id != message.from_user.id:
        target_id = message.from_user.id
        first_name = message.from_user.first_name
        username = message.from_user.username
    
    db = get_db(message)
    warns = db.get_warnings_list(target_id)
    count = len(warns)
    
    if count == 0:
        return await message.reply(f"{EMOJI['check']} Нет варнов!")
    
    warn_bar = "🔴" * min(count, 3) + "⚪" * max(0, 3 - count)
    text = f"⚠️ <b>{first_name}</b> [{warn_bar}] {count}/3\n\n"
    
    for i, w in enumerate(warns[:5], 1):
        exp = ""
        if w.get("expires_at"):
            try:
                exp_time = datetime.fromisoformat(w["expires_at"])
                exp = f" (до {exp_time.strftime('%d.%m %H:%M')})"
            except:
                pass
        text += f"{i}. {w['reason']}{exp}\n"
    
    await message.reply(text, parse_mode="HTML")


# === MUTE ===

@router.message(Command("mute"))
async def mute_user(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    
    if not has_permission(perms, "mute") and not has_permission(perms, "all"):
        return await message.reply(f"{EMOJI['cross']} Нет прав!")
    
    target_id, first_name, username, remaining_args, error = await get_target_user(message, bot)
    
    if error:
        return await message.reply(
            f"{EMOJI['mute']} <b>Мут</b>\n\n"
            f"<code>/mute @user</code> — 1 час\n"
            f"<code>/mute @user 30m</code> — 30 мин\n"
            f"<code>/mute @user 1h причина</code>\n"
            f"<code>/mute @user 1d</code> — 1 день",
            parse_mode="HTML"
        )
    
    if target_id == message.from_user.id:
        return await message.reply(f"{EMOJI['cross']} Нельзя замутить себя!")
    
    target_perms = await get_user_permissions(message, bot, target_id)
    if target_perms["level"] >= perms["level"] and perms["level"] < 99:
        return await message.reply(f"{EMOJI['cross']} Нельзя мутить {target_perms['rank_emoji']} {target_perms['rank_name']}!")
    
    duration, duration_str, reason = parse_args_after_target(message, remaining_args)
    
    if not duration:
        duration = 60
        duration_str = "1 ч."
    
    duration = max(1, min(525600, duration))
    until_date = datetime.now() + timedelta(minutes=duration)
    
    success, error_msg = await try_restrict_member(bot, message.chat.id, target_id, until_date)
    
    if success:
        db = get_db(message)
        db.add_punishment(target_id, "mute", reason, message.from_user.id, duration)
        
        await message.reply(
            f"{EMOJI['mute']} <b>MUTE</b>\n\n"
            f"👤 {mention_user(target_id, first_name, username)}\n"
            f"⏰ {duration_str}\n"
            f"📝 {reason}\n\n"
            f"👮 {message.from_user.mention_html()}",
            parse_mode="HTML"
        )
    else:
        await message.reply(
            f"{EMOJI['cross']} <b>Не удалось замутить!</b>\n\n"
            f"Причина: {error_msg}",
            parse_mode="HTML"
        )


@router.message(Command("unmute"))
async def unmute_user(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    
    if not has_permission(perms, "unmute") and not has_permission(perms, "all"):
        return await message.reply(f"{EMOJI['cross']} Нет прав!")
    
    target_id, first_name, username, remaining_args, error = await get_target_user(message, bot)
    
    if error:
        return await message.reply("<code>/unmute @user</code>", parse_mode="HTML")
    
    success, error_msg = await try_unrestrict_member(bot, message.chat.id, target_id)
    
    if success:
        db = get_db(message)
        db.remove_punishment(target_id, "mute")
        await message.reply(f"{EMOJI['check']} {mention_user(target_id, first_name, username)} размучен!", parse_mode="HTML")
    else:
        await message.reply(f"{EMOJI['cross']} Ошибка: {error_msg}")


# === BAN ===

@router.message(Command("ban"))
async def ban_user(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    
    if not has_permission(perms, "ban") and not has_permission(perms, "all"):
        return await message.reply(f"{EMOJI['cross']} Нет прав!")
    
    target_id, first_name, username, remaining_args, error = await get_target_user(message, bot)
    
    if error:
        return await message.reply(
            f"{EMOJI['ban']} <b>Бан</b>\n\n"
            f"<code>/ban @user</code> — навсегда\n"
            f"<code>/ban @user причина</code>\n"
            f"<code>/ban @user 1d причина</code>",
            parse_mode="HTML"
        )
    
    if target_id == message.from_user.id:
        return await message.reply(f"{EMOJI['cross']} Нельзя забанить себя!")
    
    target_perms = await get_user_permissions(message, bot, target_id)
    if target_perms["level"] >= perms["level"] and perms["level"] < 99:
        return await message.reply(f"{EMOJI['cross']} Нельзя банить {target_perms['rank_emoji']} {target_perms['rank_name']}!")
    
    duration, duration_str, reason = parse_args_after_target(message, remaining_args)
    
    if not duration_str:
        duration_str = "навсегда"
    
    until_date = None
    if duration:
        until_date = datetime.now() + timedelta(minutes=duration)
    
    success, error_msg = await try_ban_member(bot, message.chat.id, target_id, until_date)
    
    if success:
        db = get_db(message)
        db.add_punishment(target_id, "ban", reason, message.from_user.id, duration)
        
        await message.reply(
            f"{EMOJI['ban']} <b>BAN</b>\n\n"
            f"👤 {mention_user(target_id, first_name, username)}\n"
            f"⏰ {duration_str}\n"
            f"📝 {reason}\n\n"
            f"👮 {message.from_user.mention_html()}",
            parse_mode="HTML"
        )
    else:
        await message.reply(
            f"{EMOJI['cross']} <b>Не удалось забанить!</b>\n\n"
            f"Причина: {error_msg}",
            parse_mode="HTML"
        )


@router.message(Command("unban"))
async def unban_user(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    
    if not has_permission(perms, "unban") and not has_permission(perms, "all"):
        return await message.reply(f"{EMOJI['cross']} Нет прав!")
    
    args = message.text.split()
    
    if len(args) < 2:
        return await message.reply("<code>/unban @user</code> или <code>/unban ID</code>", parse_mode="HTML")
    
    target_id, first_name, username, remaining_args, error = await get_target_user(message, bot)
    
    if error and len(args) > 1:
        try:
            target_id = int(args[1])
            first_name = str(target_id)
            username = None
        except:
            return await message.reply(f"{EMOJI['cross']} {error}")
    
    success, error_msg = await try_unban_member(bot, message.chat.id, target_id)
    
    if success:
        db = get_db(message)
        db.remove_punishment(target_id, "ban")
        await message.reply(f"{EMOJI['check']} {mention_user(target_id, first_name, username)} разбанен!", parse_mode="HTML")
    else:
        await message.reply(f"{EMOJI['cross']} Ошибка: {error_msg}")


@router.message(Command("kick"))
async def kick_user(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    
    if not has_permission(perms, "kick") and not has_permission(perms, "all"):
        return await message.reply(f"{EMOJI['cross']} Нет прав!")
    
    target_id, first_name, username, remaining_args, error = await get_target_user(message, bot)
    
    if error:
        return await message.reply("<code>/kick @user</code>", parse_mode="HTML")
    
    if target_id == message.from_user.id:
        return await message.reply(f"{EMOJI['cross']} Нельзя кикнуть себя!")
    
    target_perms = await get_user_permissions(message, bot, target_id)
    if target_perms["level"] >= perms["level"] and perms["level"] < 99:
        return await message.reply(f"{EMOJI['cross']} Нельзя кикнуть равного или старшего!")
    
    success, error_msg = await try_kick_member(bot, message.chat.id, target_id)
    
    if success:
        await message.reply(f"👢 {mention_user(target_id, first_name, username)} кикнут!", parse_mode="HTML")
    else:
        await message.reply(f"{EMOJI['cross']} Ошибка: {error_msg}")


# === КОМАНДЫ ОЧИСТКИ (АДМИН) ===

@router.message(Command("clearrating"))
async def clear_user_rating(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    if perms["level"] < 6 and not perms.get("is_bot_creator"):
        return await message.reply(f"{EMOJI['cross']} Только владелец группы или создатель бота!")
    
    target_id, first_name, username, remaining_args, error = await get_target_user(message, bot)
    
    if error:
        return await message.reply(
            f"🔄 <b>Сброс рейтинга</b>\n\n"
            f"<code>/clearrating @user</code>\n"
            f"<code>/clearrating</code> (реплай)",
            parse_mode="HTML"
        )
    
    db = get_db(message)
    user = db.get_user(target_id)
    if not user:
        return await message.reply(f"{EMOJI['cross']} Пользователь не найден в базе!")
    
    db.reset_user_rating(target_id)
    
    await message.reply(
        f"🔄 <b>Рейтинг сброшен!</b>\n\n"
        f"👤 {mention_user(target_id, first_name, username)}\n"
        f"⭐ Рейтинг: 0 | ✅ Побед: 0 | ❌ Поражений: 0\n\n"
        f"👮 {message.from_user.mention_html()}",
        parse_mode="HTML"
    )


@router.message(Command("clearcards"))
async def clear_user_cards(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    if perms["level"] < 6 and not perms.get("is_bot_creator"):
        return await message.reply(f"{EMOJI['cross']} Только владелец группы или создатель бота!")
    
    target_id, first_name, username, remaining_args, error = await get_target_user(message, bot)
    
    if error:
        return await message.reply(
            f"🗑 <b>Удаление карт</b>\n\n"
            f"<code>/clearcards @user</code>\n"
            f"⚠️ Удаляет ВСЕ карты!",
            parse_mode="HTML"
        )
    
    db = get_db(message)
    user = db.get_user(target_id)
    if not user:
        return await message.reply(f"{EMOJI['cross']} Пользователь не найден в базе!")
    
    old_cards_count = len(user.get("cards", []))
    db.clear_user_cards(target_id)
    
    await message.reply(
        f"🗑 <b>Карты удалены!</b>\n\n"
        f"👤 {mention_user(target_id, first_name, username)}\n"
        f"🃏 Удалено карт: <b>{old_cards_count}</b>\n\n"
        f"👮 {message.from_user.mention_html()}",
        parse_mode="HTML"
    )


@router.message(Command("clearcoins"))
async def clear_user_coins(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    if perms["level"] < 6 and not perms.get("is_bot_creator"):
        return await message.reply(f"{EMOJI['cross']} Только владелец группы или создатель бота!")
    
    target_id, first_name, username, remaining_args, error = await get_target_user(message, bot)
    
    if error:
        return await message.reply(
            f"🪙 <b>Сброс монет</b>\n\n"
            f"<code>/clearcoins @user</code>",
            parse_mode="HTML"
        )
    
    db = get_db(message)
    user = db.get_user(target_id)
    if not user:
        return await message.reply(f"{EMOJI['cross']} Пользователь не найден в базе!")
    
    old_coins = user.get("coins", 0)
    db.set_coins(target_id, 0)
    
    await message.reply(
        f"🪙 <b>Монеты обнулены!</b>\n\n"
        f"👤 {mention_user(target_id, first_name, username)}\n"
        f"💰 Было: <b>{old_coins}</b> 🪙\n\n"
        f"👮 {message.from_user.mention_html()}",
        parse_mode="HTML"
    )


@router.message(Command("clearall"))
async def clear_user_all(message: Message, bot: Bot):
    if not is_group_chat(message):
        return await message.reply(f"{EMOJI['cross']} Только в группах!")
    
    perms = await get_user_permissions(message, bot)
    if perms["level"] < 6 and not perms.get("is_bot_creator"):
        return await message.reply(f"{EMOJI['cross']} Только владелец группы или создатель бота!")
    
    target_id, first_name, username, remaining_args, error = await get_target_user(message, bot)
    
    if error:
        return await message.reply(
            f"⚠️ <b>Полный сброс</b>\n\n"
            f"<code>/clearall @user</code>\n\n"
            f"Удаляет ВСЁ: карты, рейтинг, монеты",
            parse_mode="HTML"
        )
    
    db = get_db(message)
    user = db.get_user(target_id)
    if not user:
        return await message.reply(f"{EMOJI['cross']} Пользователь не найден в базе!")
    
    old_cards = len(user.get("cards", []))
    old_rating = user.get("rating", 0)
    old_coins = user.get("coins", 0)
    old_wins = user.get("wins", 0)
    old_losses = user.get("losses", 0)
    
    db.clear_user_cards(target_id)
    db.reset_user_rating(target_id)
    db.set_coins(target_id, 0)
    
    await message.reply(
        f"⚠️ <b>ПОЛНЫЙ СБРОС!</b>\n\n"
        f"👤 {mention_user(target_id, first_name, username)}\n\n"
        f"<b>Удалено:</b>\n"
        f"🃏 Карт: {old_cards}\n"
        f"⭐ Рейтинг: {old_rating}\n"
        f"✅ Побед: {old_wins}\n"
        f"❌ Поражений: {old_losses}\n"
        f"🪙 Монет: {old_coins}\n\n"
        f"👮 {message.from_user.mention_html()}",
        parse_mode="HTML"
    )


# === СОЗДАТЕЛИ ===

@router.message(Command("addcreator"))
async def add_creator(message: Message):
    if message.from_user.username and message.from_user.username.lower() not in [c.lower() for c in BOT_CREATORS]:
        return await message.reply(f"{EMOJI['cross']} Только создатели!")
    
    args = message.text.split()
    if len(args) < 2:
        return await message.reply("/addcreator @username")
    
    new_creator = args[1].replace("@", "")
    if new_creator.lower() not in [c.lower() for c in BOT_CREATORS]:
        BOT_CREATORS.append(new_creator)
        await message.reply(f"{EMOJI['check']} @{new_creator} добавлен!")
    else:
        await message.reply("Уже создатель!")


@router.message(Command("creators"))
async def list_creators(message: Message):
    text = "\n".join([f"💠 @{c}" for c in BOT_CREATORS])
    await message.reply(f"<b>Создатели:</b>\n\n{text}", parse_mode="HTML")


# === КОМАНДЫ ДЛЯ ПОВЫШЕНИЯ ШАНСА СПИНА ===

@router.message(Command("boostspin"))
async def boost_spin_chance(message: Message, bot: Bot):
    """Команда для повышения шанса спина игроку через ЛС"""
    # Проверяем, что команда используется в ЛС
    if message.chat.type != "private":
        return await message.reply("Эту команду можно использовать только в личных сообщениях с ботом!")
    
    # Проверяем, что пользователь - создатель бота
    if not (message.from_user.username and message.from_user.username.lower() in [c.lower() for c in BOT_CREATORS]):
        return await message.reply("Только создатели бота могут использовать эту команду!")
    
    args = message.text.split()
    if len(args) < 3:
        return await message.reply(
            "Использование: /boostspin USER_ID MULTIPLIER\n"
            "Пример: /boostspin 123456789 2.0\n"
            "Где 2.0 - множитель шанса (обычно от 1.0 до 5.0)"
        )
    
    try:
        target_user_id = int(args[1])
        multiplier = float(args[2])
    except ValueError:
        return await message.reply("Неправильный формат. USER_ID должен быть числом, MULTIPLIER должен быть числом.")
    
    # Ограничиваем множитель разумными пределами
    multiplier = max(0.1, min(10.0, multiplier))
    
    # Сохраняем множитель в глобальной базе данных
    global_db = DatabaseManager.get_global_db()
    global_db.set_spin_boost(target_user_id, multiplier)
    
    await message.reply(f"Шанс спина для пользователя {target_user_id} увеличен в {multiplier} раз!")


@router.message(Command("removespinboost"))
async def remove_spin_boost(message: Message, bot: Bot):
    """Команда для удаления буста шанса спина"""
    # Проверяем, что команда используется в ЛС
    if message.chat.type != "private":
        return await message.reply("Эту команду можно использовать только в личных сообщениях с ботом!")
    
    # Проверяем, что пользователь - создатель бота
    if not (message.from_user.username and message.from_user.username.lower() in [c.lower() for c in BOT_CREATORS]):
        return await message.reply("Только создатели бота могут использовать эту команду!")
    
    args = message.text.split()
    if len(args) < 2:
        return await message.reply("Использование: /removespinboost USER_ID")
    
    try:
        target_user_id = int(args[1])
    except ValueError:
        return await message.reply("USER_ID должен быть числом.")
    
    # Удаляем множитель из глобальной базы данных
    global_db = DatabaseManager.get_global_db()
    global_db.remove_spin_boost(target_user_id)
    
    await message.reply(f"Буст шанса спина для пользователя {target_user_id} удален!")