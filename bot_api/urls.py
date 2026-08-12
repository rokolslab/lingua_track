from django.urls import path
from .auth import require_bot_api_token
from .views import telegram_bind, cards_list, cards_today, user_progress, tts, test, test_multiple_choice

urlpatterns = [
    path('telegram/bind/', require_bot_api_token(telegram_bind), name='api_telegram_bind'),
    path('cards/', require_bot_api_token(cards_list), name='api_cards_list'),
    path('today/', require_bot_api_token(cards_today), name='api_cards_today'),
    path('progress/', require_bot_api_token(user_progress), name='api_user_progress'),
    path('tts/', require_bot_api_token(tts), name='api_tts'),
    path('test/', require_bot_api_token(test), name='api_test'),  # опционально
    path(
        'test/multiple_choice/',
        require_bot_api_token(test_multiple_choice),
        name='api_test_multiple_choice',
    ),
]
