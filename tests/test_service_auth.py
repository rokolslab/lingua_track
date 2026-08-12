import asyncio
import json

import pytest
from django.test import override_settings

from cards import tasks
from t_bot import bot as bot_module
from t_bot import handlers


BOT_API_TOKEN = 'dummy-test-only-bot-api-token'
NOTIFY_API_TOKEN = 'dummy-test-only-notify-api-token'


@pytest.mark.django_db
@override_settings(BOT_API_TOKEN=BOT_API_TOKEN)
@pytest.mark.parametrize(
    'path',
    [
        '/api/telegram/bind/',
        '/api/cards/',
        '/api/today/',
        '/api/progress/',
        '/api/tts/',
        '/api/test/',
        '/api/test/multiple_choice/',
    ],
)
def test_bot_api_endpoints_reject_missing_token(client, path):
    response = client.get(path)

    assert response.status_code == 401
    assert response.json() == {'error': 'Unauthorized'}
    assert response['WWW-Authenticate'] == 'Bearer'


@pytest.mark.django_db
@override_settings(BOT_API_TOKEN=BOT_API_TOKEN)
def test_bot_api_rejects_invalid_token(client):
    response = client.get(
        '/api/cards/',
        HTTP_AUTHORIZATION='Bearer wrong-test-token',
    )

    assert response.status_code == 401


@pytest.mark.django_db
@override_settings(BOT_API_TOKEN=BOT_API_TOKEN)
def test_bot_api_accepts_configured_token(client, user_with_telegram):
    response = client.get(
        '/api/cards/',
        {'telegram_id': user_with_telegram.telegram_id},
        HTTP_AUTHORIZATION=f'Bearer {BOT_API_TOKEN}',
    )

    assert response.status_code == 200
    assert response.json() == {'cards': []}


class FakeNotifyRequest:
    def __init__(self, authorization=None, payload=None):
        self.headers = {}
        if authorization is not None:
            self.headers['Authorization'] = authorization
        self._payload = payload or {}

    async def json(self):
        return self._payload


@pytest.mark.parametrize(
    'authorization',
    [None, 'Bearer wrong-test-token'],
)
def test_notify_endpoint_rejects_unauthorized_requests(monkeypatch, authorization):
    monkeypatch.setattr(handlers, 'NOTIFY_API_TOKEN', NOTIFY_API_TOKEN)
    request = FakeNotifyRequest(authorization=authorization)

    response = asyncio.run(handlers.notify_handler(request))

    assert response.status == 401
    assert json.loads(response.text) == {'error': 'Unauthorized'}
    assert response.headers['WWW-Authenticate'] == 'Bearer'


def test_notify_endpoint_accepts_configured_token(monkeypatch):
    sent_message = {}

    class FakeSession:
        async def close(self):
            sent_message['closed'] = True

    class FakeBot:
        def __init__(self, token):
            self.session = FakeSession()

        async def send_message(self, chat_id, text):
            sent_message.update(chat_id=chat_id, text=text)

    monkeypatch.setattr(handlers, 'NOTIFY_API_TOKEN', NOTIFY_API_TOKEN)
    monkeypatch.setattr(bot_module, 'Bot', FakeBot)
    request = FakeNotifyRequest(
        authorization=f'Bearer {NOTIFY_API_TOKEN}',
        payload={'telegram_id': 123456789, 'message': 'Test reminder'},
    )

    response = asyncio.run(handlers.notify_handler(request))

    assert response.status == 200
    assert json.loads(response.text) == {'status': 'ok'}
    assert sent_message == {
        'chat_id': 123456789,
        'text': 'Test reminder',
        'closed': True,
    }


def test_reminder_task_sends_notify_token(monkeypatch):
    request = {}

    class User:
        telegram_id = 123456789

    class Users:
        def exclude(self, **kwargs):
            return self

        def __iter__(self):
            return iter([User()])

    class UserModel:
        objects = Users()

    class Schedules:
        def filter(self, **kwargs):
            return self

        def exists(self):
            return True

    class Response:
        status_code = 200

    def fake_post(url, **kwargs):
        request.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr(tasks, 'NOTIFY_API_TOKEN', NOTIFY_API_TOKEN)
    monkeypatch.setattr(tasks, 'get_user_model', lambda: UserModel)
    monkeypatch.setattr(tasks.Schedule, 'objects', Schedules())
    monkeypatch.setattr(tasks.requests, 'post', fake_post)

    result = tasks.send_daily_review_reminders.run()

    assert result == 'Отправлено напоминаний: 1'
    assert request['headers'] == {
        'Authorization': f'Bearer {NOTIFY_API_TOKEN}',
    }
