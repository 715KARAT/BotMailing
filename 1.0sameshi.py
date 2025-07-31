import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)
logger = logging.getLogger(__name__)

# Определение состояний
class Form(StatesGroup):
    waiting_for_files = State()

# Конфигурация
import os
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 739361473 # 796381516

# Хранение данных
current_mailing = {
    "date": "04.08.2025",
    "files": [],
    "text": "Здравствуйте! Вот материалы по рассылке: https://drive.google.com/drive/folders/1-srO5whhr4KfEMRej111by9qcs37HbOI?usp=sharing",
    "channels": [
        {"id": -1002895938397, "name": "@studywithmiro"},
        {"id": -1002542163897, "name": "@miroholst"},
        {"id": -1001832702236, "name": "@mamasbooks"},
        {"id": -1002386014261, "name": "@russianlanguageandgeography"},
        {"id": -1002861287275, "name": "@lazvik_repet"},
        {"id": -1002204291357, "name": "@mirocreativonline"},
        {"id": -1002549199780, "name": "@proyazyk1"},
        
        # {"id": -1002631054307, "name": "@zxcmabot"},
    ],
    "user_ids": set()
}

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def check_subscription(user_id: int) -> tuple[bool, list[str]]:
    """
    Проверяет подписки на все каналы
    Возвращает кортеж:
    - True если подписан на все каналы, иначе False
    - Список каналов, на которые нет подписки
    """
    unsubscribed_channels = []
    
    for channel in current_mailing["channels"]:
        try:
            member = await bot.get_chat_member(chat_id=channel["id"], user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                unsubscribed_channels.append(channel["name"])
        except Exception as e:
            logger.error(f"Ошибка проверки подписки на {channel['name']}: {e}")
            unsubscribed_channels.append(channel["name"])
    
    return (not unsubscribed_channels, unsubscribed_channels)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    current_mailing["user_ids"].add(message.from_user.id)
    is_subscribed, missing_channels = await check_subscription(message.from_user.id)
    
    if is_subscribed:
        await message.answer("✅ Вы подписаны на все каналы! Ожидайте рассылку.")
    else:
        channels_list = "\n".join([f"• {name}" for name in missing_channels])
        await message.answer(
            f"📢 Для доступа к материалам подпишитесь на наши каналы:\n\n"
            f"{channels_list}\n\n"
            "После подписки нажмите /start повторно для проверки."
        )

@dp.message(Command("mailing"))
async def cmd_mailing(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ У вас нет прав доступа!")
    
    await message.answer("🔄 Запускаю рассылку...")
    asyncio.create_task(send_mailing())

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ У вас нет прав доступа!")
    
    await state.clear()
    buttons = [
        [InlineKeyboardButton(text="🔄 Запустить рассылку", callback_data="send_mailing")],
        [InlineKeyboardButton(text="📅 Изменить дату", callback_data="change_date")],
        [InlineKeyboardButton(text="📝 Изменить текст", callback_data="change_text")],
        [InlineKeyboardButton(text="📎 Добавить файлы", callback_data="add_files")]
    ]
    
    info = (
        f"📅 Дата рассылки: {current_mailing['date']}\n"
        f"📝 Текст: {current_mailing['text'][:100]}...\n"
        f"📎 Файлов: {len(current_mailing['files'])}\n"
        f"👥 Пользователей: {len(current_mailing['user_ids'])}"
    )
    
    await message.answer(
        f"⚙️ Админ-панель\n\n{info}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@dp.callback_query(F.data == "change_date")
async def change_date(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите дату в формате ДД.ММ.ГГГГ:")
    await state.set_state("waiting_for_date")
    await callback.answer()

@dp.message(F.state == "waiting_for_date", F.text.regexp(r'^\d{2}\.\d{2}\.\d{4}$'))
async def handle_date(message: types.Message, state: FSMContext):
    current_mailing["date"] = message.text
    await state.clear()
    await message.answer(f"📅 Новая дата рассылки: {message.text}")
    await cmd_admin(message, state)

@dp.callback_query(F.data == "change_text")
async def change_text(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новый текст рассылки:")
    await state.set_state("waiting_for_text")
    await callback.answer()

@dp.message(F.state == "waiting_for_text")
async def handle_text(message: types.Message, state: FSMContext):
    current_mailing["text"] = message.text
    await state.clear()
    await message.answer("📝 Текст рассылки обновлен!")
    await cmd_admin(message, state)

@dp.callback_query(F.data == "add_files")
async def add_files_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Отправьте файлы для рассылки (документы, фото, видео).\n"
        "Когда закончите, нажмите /admin для возврата в меню."
    )
    await state.set_state(Form.waiting_for_files)
    await callback.answer()

@dp.message(F.from_user.id == ADMIN_ID, Form.waiting_for_files, F.document | F.photo | F.video)
async def handle_files(message: types.Message):
    file_id = None
    if message.document:
        file_id = message.document.file_id
    elif message.photo:
        file_id = message.photo[-1].file_id
    elif message.video:
        file_id = message.video.file_id
    
    if file_id:
        current_mailing["files"].append(file_id)
        await message.answer(f"📎 Файл добавлен! Всего: {len(current_mailing['files'])}")

@dp.callback_query(F.data == "send_mailing")
async def send_mailing_handler(callback: types.CallbackQuery):
    await callback.answer("Рассылка начата...")
    asyncio.create_task(send_mailing())

async def send_mailing():
    try:
        success = failed = 0
        total = len(current_mailing["user_ids"])
        logger.info(f"Начало рассылки для {total} пользователей")
        
        for user_id in list(current_mailing["user_ids"]):  # Используем list для копирования
            try:
                is_subscribed, _ = await check_subscription(user_id)
                if is_subscribed:
                    await bot.send_message(user_id, current_mailing["text"])
                    for file_id in current_mailing["files"]:
                        await bot.send_document(user_id, file_id)
                        await asyncio.sleep(0.3)
                    success += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Ошибка рассылки для {user_id}: {e}")
                failed += 1
        
        report = (
            f"✅ Рассылка завершена!\n"
            f"👥 Всего: {total}\n"
            f"✔️ Успешно: {success}\n"
            f"✖️ Ошибки: {failed}"
        )
        await bot.send_message(ADMIN_ID, report)
    except Exception as e:
        logger.critical(f"Критическая ошибка рассылки: {e}")
        await bot.send_message(ADMIN_ID, f"⛔ Ошибка рассылки: {e}")

async def schedule_checker():
    while True:
        try:
            now = datetime.now().strftime("%d.%m.%Y")
            if now == current_mailing["date"]:
                await send_mailing()
                current_mailing["date"] = "31.12.2099"
            await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"Ошибка в schedule_checker: {e}")
            await asyncio.sleep(60)

async def main():
    asyncio.create_task(schedule_checker())
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"Фатальная ошибка: {e}")
