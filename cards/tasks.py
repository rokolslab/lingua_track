import logging
import os
from datetime import date

import requests
from celery import shared_task
from django.contrib.auth import get_user_model

from cards.models import Schedule


logger = logging.getLogger(__name__)

# URL локального API для отправки напоминаний (можно вынести в settings)
TELEGRAM_BOT_NOTIFY_URL = os.getenv('TELEGRAM_BOT_NOTIFY_URL', 'http://127.0.0.1:8080/notify')
NOTIFY_API_TOKEN = (
    os.getenv('NOTIFY_API_TOKEN', '').strip()
    or 'development-only-notify-api-token-do-not-use-in-production'
)

@shared_task
def send_daily_review_reminders():
    """
    Ежедневная задача: находит пользователей с карточками на сегодня и отправляет им напоминание через Telegram-бота.
    """
    User = get_user_model()
    today = date.today()
    users = User.objects.exclude(telegram_id__isnull=True)
    count = 0
    for user in users:
        # Есть ли карточки на сегодня?
        has_today = Schedule.objects.filter(card__user=user, next_review__lte=today).exists()
        if has_today:
            # Отправить напоминание через Telegram-бот (через API или напрямую)
            payload = {
                'telegram_id': user.telegram_id,
                'message': '⏰ Сегодня есть слова для повторения! Зайди в LinguaTrack или напиши /today боту.'
            }
            try:
                resp = requests.post(
                    TELEGRAM_BOT_NOTIFY_URL,
                    json=payload,
                    headers={'Authorization': f'Bearer {NOTIFY_API_TOKEN}'},
                    timeout=10,
                )
                if resp.status_code == 200:
                    count += 1
                else:
                    logger.warning(
                        'Не удалось отправить Telegram-напоминание '
                        'для user_id=%s: HTTP %s',
                        user.pk,
                        resp.status_code,
                    )
            except Exception as error:
                logger.warning(
                    'Ошибка отправки Telegram-напоминания '
                    'для user_id=%s: %s',
                    user.pk,
                    type(error).__name__,
                )
    return f'Отправлено напоминаний: {count}'
