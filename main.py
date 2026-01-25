import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message, BotCommand, ChatPermissions
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, EMOJI
from handlers import admin, cards, battle, market, trade
from database import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

dp.include_router(admin.router)
dp.include_router(cards.router)
dp.include_router(battle.router)
dp.include_router(market.router)
dp.include_router(trade.router)


async def check_expired_punishments():
    """Фоновая задача для автоснятия наказаний"""
    while True:
        try:
            for group_db in DatabaseManager.get_all_group_dbs():
                expired = group_db.get_expired_punishments()
                
                for punishment in expired:
                    try:
                        if punishment["punishment_type"] == "mute":
                            await bot.restrict_chat_member(
                                punishment["chat_id"],
                                punishment["user_id"],
                                permissions=ChatPermissions(
                                    can_send_messages=True,
                                    can_send_media_messages=True,
                                    can_send_other_messages=True,
                                    can_add_web_page_previews=True
                                )
                            )
                            logger.info(f"Auto-unmute: {punishment['user_id']} in {punishment['chat_id']}")
                        
                        elif punishment["punishment_type"] == "ban":
                            await bot.unban_chat_member(
                                punishment["chat_id"],
                                punishment["user_id"]
                            )
                            logger.info(f"Auto-unban: {punishment['user_id']} in {punishment['chat_id']}")
                        
                        group_db.deactivate_punishment(punishment["id"])
                        
                    except Exception as e:
                        logger.error(f"Error removing punishment: {e}")
                        group_db.deactivate_punishment(punishment["id"])
            
        except Exception as e:
            logger.error(f"Error in check_expired_punishments: {e}")
        
        await asyncio.sleep(30)


@dp.message(Command("start", "help"))
async def start_help_command(message: Message):
    text = (
        "<b>Добро пожаловать!</b>\n\n"
        
        "<b>🎟️ БИЛЕТЫ И ПРОКРУТКА</b>\n"
        "├ /ticket — получить бесплатный билет (раз в 30 мин)\n"
        "├ /tickets — мои билеты\n"
        "├ /spin — использовать билет для прокрутки\n"
        "└ /givetickets — выдать билеты (админ)\n\n"
        
        "<b>🃏 КАРТОЧКИ</b>\n"
        "├ /mycards — мои карты\n"
        "├ /cards — все возможные карты\n"
        "├ /card [имя] — подробности о карте\n"
        "├ /collection — статистика коллекции\n"
        "└ /topcards — топ самых сильных карт\n\n"
        
        "<b>🪙 МОНЕТЫ</b>\n"
        "├ /balance — мой баланс\n"
        "└ /market — купить щиты для арены\n\n"
        
        "<b>🏟️ АРЕНА</b>\n"
        "├ /arena — начать поиск боя\n"
        "├ /rating — топ игроков\n"
        "├ /profile — профиль (свой или чужой)\n"
        "├ /setbio [текст] — установить описание\n"
        "├ /setphoto — закрепить фото в профиле\n"
        "└ /removephoto — убрать закреплённое фото\n\n"
        
        "<b>🏆 РЕЙТИНГИ</b>\n"
        "└ /top — все рейтинги (карты, монеты, арена)\n\n"
        
        "<b>🎖️ РАНГИ</b>\n"
        "├ /ranks — список администрации\n"
        "├ /myrank — мой ранг\n"
        "├ /ranklist — все ранги в чате\n"
        "└ /perms — права текущего ранга\n\n"
        
        "<b>🛡️ МОДЕРАЦИЯ</b>\n"
        "├ /warn, /unwarn, /warns\n"
        "├ /mute, /unmute\n"
        "├ /ban, /unban, /kick\n"
        "└ /rules, /setrules\n\n"
        
        "<b>📢 ОБЪЯВЛЕНИЯ</b>\n"
        "├ /announce — объявление + закреп\n"
        "├ /pin — закрепить сообщение\n"
        "└ /unpin — открепить\n\n"
        
        "<b>👑 АДМИН КОМАНДЫ</b>\n"
        "├ /promote, /demote\n"
        "├ /givecard, /givecoins, /givetickets\n"
        "├ /resetcd — сброс времени бесплатного билета\n"
        "├ /clearrating, /clearcards, /clearcoins\n"
        "└ /clearall — полный сброс пользователя\n\n"
        "└ /boostspin — Буст удачи\n\n"
        
        "<b>⏰ Форматы времени для наказаний:</b>\n"
        "30m, 1h, 1d, 7d, 30d и т.д.\n\n"
        
        "<i>⚠️ Все данные (карты, монеты, рейтинг) отдельные для каждой группы!</i>"
    )

    # Используем answer вместо reply для избежания ошибок
    await message.answer(text, parse_mode="HTML")


async def set_commands():
    commands = [
        BotCommand(command="start",      description="🚀 Начать / Помощь"),
        BotCommand(command="help",       description="❓ Показать команды"),
        BotCommand(command="ticket",     description="🎫 Получить билет"),
        BotCommand(command="tickets",    description="🎟️ Мои билеты"),
        BotCommand(command="spin",       description="🎰 Прокрутить карту"),
        BotCommand(command="mycards",    description="🃏 Мои карты"),
        BotCommand(command="cards",      description="📋 Все карты"),
        BotCommand(command="card",       description="🔍 Инфо о карте"),
        BotCommand(command="collection", description="📊 Статистика коллекции"),
        BotCommand(command="top",        description="🏆 Рейтинги"),
        BotCommand(command="balance",    description="🪙 Мой баланс"),
        BotCommand(command="market",     description="🛒 Купить щиты"),
        BotCommand(command="arena",      description="🏟️ На арену"),
        BotCommand(command="rating",     description="📈 Топ игроков"),
        BotCommand(command="profile",    description="👤 Профиль"),
        BotCommand(command="setbio",     description="✏️ Изменить био"),
        BotCommand(command="ranks",      description="🎖️ Администрация"),
        BotCommand(command="myrank",     description="📊 Мой ранг"),
        BotCommand(command="rules",      description="📜 Правила чата"),
    ]
    await bot.set_my_commands(commands)


async def main():
    logger.info("🚀 Бот запускается...")
    
    await set_commands()
    asyncio.create_task(check_expired_punishments())
    asyncio.create_task(battle.check_queue_periodically(bot))
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())