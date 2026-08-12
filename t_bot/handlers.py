"""
Обработчики команд Telegram-бота.
Содержит логику обработки команд и взаимодействия с пользователем.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputFile, BufferedInputFile
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import Dict, List
import io
from secrets import compare_digest

from .api_client import DjangoAPIClient
from .config import MESSAGES, NOTIFY_API_TOKEN

router = Router()
api_client = DjangoAPIClient()

# --- HTTP endpoint для Celery уведомлений ---
try:
    from aiohttp import web
    import asyncio

    async def notify_handler(request):
        authorization = request.headers.get('Authorization', '')
        scheme, separator, provided_token = authorization.partition(' ')
        is_authorized = (
            separator
            and scheme.lower() == 'bearer'
            and bool(provided_token)
            and compare_digest(provided_token, NOTIFY_API_TOKEN)
        )
        if not is_authorized:
            return web.json_response(
                {'error': 'Unauthorized'},
                status=401,
                headers={'WWW-Authenticate': 'Bearer'},
            )
        try:
            data = await request.json()
            telegram_id = data.get('telegram_id')
            message_text = data.get('message')
            if not telegram_id or not message_text:
                return web.json_response({'error': 'telegram_id and message required'}, status=400)
            # Отправляем сообщение через aiogram
            from .bot import Bot, BOT_TOKEN
            bot = Bot(token=BOT_TOKEN)
            await bot.send_message(chat_id=telegram_id, text=message_text)
            await bot.session.close()
            return web.json_response({'status': 'ok'})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    def setup_notify_endpoint(app):
        app.router.add_post('/notify', notify_handler)

except ImportError:
    # aiohttp не установлен — endpoint не будет работать
    def setup_notify_endpoint(app):
        pass

class TestStates(StatesGroup):
    """Состояния для тестирования карточек."""
    waiting_for_answer = State()

# --- Multiple Choice FSM ---
class MCStates(StatesGroup):
    waiting_for_mc_answer = State()

@router.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject = None):
    # Если есть аргумент (токен) — это попытка привязки
    if command and command.args:
        token = command.args.strip()
        telegram_id = message.from_user.id
        success, message_text = api_client.bind_telegram(token, telegram_id)
        await message.answer(message_text)
        return
    # Обычное приветствие
    await message.answer(MESSAGES['welcome'])

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help."""
    await message.answer(MESSAGES['help'])

@router.message(Command("cards"))
async def cmd_cards(message: Message):
    """Обработчик команды /cards - показывает все карточки пользователя."""
    telegram_id = message.from_user.id
    
    success, cards = api_client.get_cards(telegram_id)
    
    if not success:
        await message.answer(MESSAGES['not_bound'])
        return
    
    if not cards:
        await message.answer(MESSAGES['no_cards'])
        return
    
    # Формируем сообщение с карточками
    response = "📚 Твои карточки:\n\n"
    for i, card in enumerate(cards[:10], 1):  # Показываем первые 10
        level_emoji = {
            'beginner': '🟢',
            'intermediate': '🟡', 
            'advanced': '🔴'
        }.get(card['level'], '⚪')
        
        response += f"{i}. {level_emoji} <b>{card['word']}</b> — {card['translation']}\n"
        
        if card.get('example'):
            response += f"   <i>Пример: {card['example']}</i>\n"
        
        response += "\n"
    
    if len(cards) > 10:
        response += f"... и еще {len(cards) - 10} карточек"
    
    await message.answer(response, parse_mode="HTML")

@router.message(Command("today"))
async def cmd_today(message: Message):
    """Обработчик команды /today - показывает карточки на сегодня."""
    telegram_id = message.from_user.id
    
    success, cards = api_client.get_today_cards(telegram_id)
    
    if not success:
        await message.answer(MESSAGES['not_bound'])
        return
    
    if not cards:
        await message.answer(MESSAGES['no_today'])
        return
    
    # Формируем сообщения с карточками на сегодня (разбивка по лимиту Telegram)
    MAX_MSG_LEN = 4096
    head = "📅 Карточки на сегодня:\n\n"
    parts = []
    current = head
    for i, card in enumerate(cards, 1):
        level_emoji = {
            'beginner': '🟢',
            'intermediate': '🟡', 
            'advanced': '🔴'
        }.get(card['level'], '⚪')
        card_text = f"{i}. {level_emoji} <b>{card['word']}</b> — {card['translation']}\n"
        if card.get('example'):
            card_text += f"   <i>Пример: {card['example']}</i>\n"
        card_text += "\n"
        if len(current) + len(card_text) > MAX_MSG_LEN:
            parts.append(current)
            current = ""
        current += card_text
    if current:
        parts.append(current)
    # Отправляем по частям
    for idx, part in enumerate(parts):
        await message.answer(part, parse_mode="HTML")

@router.message(Command("progress"))
async def cmd_progress(message: Message):
    """Обработчик команды /progress - показывает прогресс пользователя."""
    telegram_id = message.from_user.id
    
    success, progress = api_client.get_progress(telegram_id)
    
    if not success:
        await message.answer(MESSAGES['not_bound'])
        return
    
    # Формируем сообщение с прогрессом
    response = "📊 Твой прогресс:\n\n"
    response += f"📚 Всего карточек: {progress.get('total', 0)}\n"
    response += f"✅ Выучено: {progress.get('learned', 0)}\n"
    response += f"❌ Ошибок: {progress.get('errors', 0)}\n"
    response += f"🔄 Повторений: {progress.get('repetitions', 0)}\n"
    
    # Вычисляем процент выученных
    total = progress.get('total', 0)
    learned = progress.get('learned', 0)
    if total > 0:
        percentage = (learned / total) * 100
        response += f"📈 Процент выученных: {percentage:.1f}%\n"
    
    await message.answer(response)

@router.message(Command("test"))
async def cmd_test(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    success, cards = api_client.get_today_cards(telegram_id)
    if not success:
        await message.answer(MESSAGES['not_bound'])
        return
    if not cards:
        await message.answer(MESSAGES['no_today'])
        return
    # Сохраняем очередь карточек в FSM
    await state.update_data(test_cards=cards, test_index=0)
    await send_next_test_card(message, state)

async def send_next_test_card(message, state):
    data = await state.get_data()
    cards = data.get('test_cards', [])
    idx = data.get('test_index', 0)
    if idx >= len(cards):
        await message.answer("🎉 Тест завершён! Все карточки на сегодня пройдены.")
        await state.clear()
        return
    card = cards[idx]
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Знаю", callback_data=f"test_yes_{card['id']}")
    builder.button(text="❌ Не знаю", callback_data=f"test_no_{card['id']}")
    builder.button(text="⏭ Пропустить", callback_data="test_skip")
    question = f"📝 Тест: переведи слово\n\n<b>{card['word']}</b>\n\n"
    if card.get('example'):
        question += f"<i>Пример: {card['example']}</i>\n\n"
    question += "Выбери ответ:"
    await message.answer(question, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("test_"))
async def handle_test_answer(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    if data == "test_skip":
        await callback.message.edit_text("Тест пропущен")
        await callback.answer()
        # Следующая карточка
        user_data = await state.get_data()
        idx = user_data.get('test_index', 0) + 1
        await state.update_data(test_index=idx)
        await send_next_test_card(callback.message, state)
        return
    parts = data.split("_")
    if len(parts) != 3:
        await callback.answer("Ошибка обработки ответа")
        return
    answer_type = parts[1]  # yes/no
    card_id = int(parts[2])
    telegram_id = callback.from_user.id
    answer = (answer_type == "yes")
    success, api_resp = api_client.submit_test_result(telegram_id, card_id, answer)
    if success and isinstance(api_resp, dict):
        msg = api_resp.get('msg', '')
        interval = api_resp.get('interval')
        next_review = api_resp.get('next_review')
        feedback = f"{msg}\nСледующее повторение через {interval} дней: {next_review}"
        # Рекомендация
        if answer:
            feedback += "\n👍 Продолжай в том же духе!"
        else:
            feedback += "\n👀 Обрати внимание на это слово ещё раз."
        await callback.message.edit_text(feedback)
    else:
        await callback.message.edit_text(f"Ошибка: {api_resp}")
    await callback.answer()
    # Следующая карточка
    user_data = await state.get_data()
    idx = user_data.get('test_index', 0) + 1
    await state.update_data(test_index=idx)
    await send_next_test_card(callback.message, state)

@router.message(Command("test_mc"))
async def cmd_test_mc(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    # Получаем первую карточку и варианты
    success, data = api_client.get_multiple_choice(telegram_id)
    if not success or not data.get('card'):
        await message.answer(MESSAGES.get('no_today', 'Нет карточек для теста.'))
        return
    await state.update_data(mc_active=True)
    await send_mc_card(message, state, data)

async def send_mc_card(message, state, data):
    card = data['card']
    options = data['options']
    builder = InlineKeyboardBuilder()
    for idx, opt in enumerate(options):
        builder.button(text=opt, callback_data=f"mc_{card['id']}_{idx}")
    # Кнопка озвучки
    builder.button(text="▶️ Озвучить", callback_data=f"mc_tts_{card['id']}")
    builder.adjust(2, 1)  # 2 варианта в строке, последняя строка — озвучка
    text = f"📝 Multiple Choice:\n\n<b>{card['word']}</b>"
    if card.get('example'):
        text += f"\n<i>Пример: {card['example']}</i>"
    if card.get('comment'):
        text += f"\n<i>Комментарий: {card['comment']}</i>"
    text += "\n\nВыбери правильный перевод:"
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(MCStates.waiting_for_mc_answer)
    await state.update_data(mc_card_id=card['id'], mc_options=options)

@router.callback_query(lambda c: c.data.startswith("mc_"))
async def handle_mc_answer(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    if data.startswith("mc_tts_"):
        # Озвучка слова
        card_id = int(data.split("_")[2])
        user_data = await state.get_data()
        telegram_id = callback.from_user.id
        success, card_data = api_client.get_multiple_choice(telegram_id)
        word = card_data.get('card', {}).get('word') if card_data else None
        if word:
            success, audio_data = api_client.get_tts_audio(telegram_id, word)
            if success and audio_data:
                voice_file = BufferedInputFile(audio_data, filename=f"{word}.ogg")
                await callback.message.answer_voice(
                    voice=voice_file,
                    caption=f"▶️ Озвучка слова: {word}"
                )
            else:
                await callback.message.answer("Ошибка получения аудио")
        else:
            await callback.message.answer("Ошибка: не удалось получить слово для озвучки")
        await callback.answer()
        return
    # Ответ пользователя (вариант)
    parts = data.split("_")
    if len(parts) != 3:
        await callback.answer("Ошибка обработки варианта")
        return
    card_id = int(parts[1])
    opt_idx = int(parts[2])
    user_data = await state.get_data()
    options = user_data.get('mc_options', [])
    if 0 <= opt_idx < len(options):
        answer = options[opt_idx]
    else:
        await callback.answer("Ошибка варианта")
        return
    telegram_id = callback.from_user.id
    success, resp = api_client.submit_multiple_choice(telegram_id, card_id, answer)
    if not success or not isinstance(resp, dict):
        await callback.message.edit_text("Ошибка отправки ответа. Попробуй позже.")
        await callback.answer()
        return
    msg = resp.get('msg', '')
    feedback = f"{msg}\nСледующее повторение через {resp.get('interval', '?')} дней: {resp.get('next_review', '?')}"
    await callback.message.edit_text(feedback)
    await callback.answer()
    # Следующая карточка
    success, data = api_client.get_multiple_choice(telegram_id)
    if not success or not data.get('card'):
        await callback.message.answer("🎉 Тест завершён! Все карточки на сегодня пройдены.")
        await state.clear()
        return
    await send_mc_card(callback.message, state, data)

@router.message(Command("say"))
async def cmd_say(message: Message):
    """Обработчик команды /say - озвучивает слово."""
    # Извлекаем слово из команды
    text = message.text.strip()
    if text == "/say":
        await message.answer("Использование: /say слово")
        return
    
    word = text[5:].strip()  # Убираем "/say "
    if not word:
        await message.answer("Использование: /say слово")
        return
    
    telegram_id = message.from_user.id
    
    # Получаем аудиофайл
    success, audio_data = api_client.get_tts_audio(telegram_id, word)
    
    if not success:
        await message.answer(MESSAGES['word_not_found'])
        return
    
    if not audio_data:
        await message.answer("Ошибка получения аудио")
        return
    
    # Отправляем аудиофайл как голосовое сообщение
    voice_file = BufferedInputFile(audio_data, filename=f"{word}.ogg")
    await message.answer_voice(
        voice=voice_file,
        caption=f"▶️ Озвучка слова: {word}"
    )

@router.message()
async def handle_unknown(message: Message):
    """Обработчик неизвестных команд и magic-ссылок."""
    text = message.text.strip()
    # Удаляю обработку /start <token> отсюда, теперь она в cmd_start
    await message.answer(
        "Не понимаю эту команду. Используй /help для списка доступных команд."
    )
