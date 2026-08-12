import logging
from datetime import date, timedelta

import pytest
import requests

from cards import tasks
from cards.models import Card


NOTIFY_API_TOKEN = 'dummy-test-only-notify-api-token'


def add_card(user, *, due=True):
    card = Card.objects.create(
        user=user,
        word='hello',
        translation='привет',
    )
    schedule = card.schedule
    schedule.next_review = date.today() if due else date.today() + timedelta(days=1)
    schedule.save(update_fields=['next_review'])
    return card


@pytest.mark.django_db
def test_reminder_is_sent_for_bound_user_with_due_card(
    monkeypatch,
    user_with_telegram,
):
    add_card(user_with_telegram)
    sent_request = {}

    class Response:
        status_code = 200

    def fake_post(url, **kwargs):
        sent_request.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr(tasks, 'NOTIFY_API_TOKEN', NOTIFY_API_TOKEN)
    monkeypatch.setattr(tasks.requests, 'post', fake_post)

    result = tasks.send_daily_review_reminders.run()

    assert result == 'Отправлено напоминаний: 1'
    assert sent_request['url'] == tasks.TELEGRAM_BOT_NOTIFY_URL
    assert sent_request['json']['telegram_id'] == user_with_telegram.telegram_id
    assert sent_request['headers'] == {
        'Authorization': f'Bearer {NOTIFY_API_TOKEN}',
    }
    assert sent_request['timeout'] == 10


@pytest.mark.django_db
def test_unbound_user_is_ignored(monkeypatch, user):
    add_card(user)

    def unexpected_post(*args, **kwargs):
        pytest.fail('An unbound user must not trigger a Telegram request.')

    monkeypatch.setattr(tasks.requests, 'post', unexpected_post)

    assert tasks.send_daily_review_reminders.run() == 'Отправлено напоминаний: 0'


@pytest.mark.django_db
def test_bound_user_without_due_card_is_ignored(monkeypatch, user_with_telegram):
    add_card(user_with_telegram, due=False)

    def unexpected_post(*args, **kwargs):
        pytest.fail('A future card must not trigger a Telegram request.')

    monkeypatch.setattr(tasks.requests, 'post', unexpected_post)

    assert tasks.send_daily_review_reminders.run() == 'Отправлено напоминаний: 0'


@pytest.mark.django_db
def test_http_failure_is_counted_as_unsent_and_logged(
    monkeypatch,
    caplog,
    user_with_telegram,
):
    add_card(user_with_telegram)

    class Response:
        status_code = 503

    monkeypatch.setattr(tasks.requests, 'post', lambda *args, **kwargs: Response())

    with caplog.at_level(logging.WARNING, logger='cards.tasks'):
        result = tasks.send_daily_review_reminders.run()

    assert result == 'Отправлено напоминаний: 0'
    assert f'user_id={user_with_telegram.pk}: HTTP 503' in caplog.text


@pytest.mark.django_db
def test_network_failure_does_not_expose_exception_details(
    monkeypatch,
    caplog,
    user_with_telegram,
):
    add_card(user_with_telegram)

    def raise_connection_error(*args, **kwargs):
        raise requests.ConnectionError('sensitive upstream detail')

    monkeypatch.setattr(tasks.requests, 'post', raise_connection_error)

    with caplog.at_level(logging.WARNING, logger='cards.tasks'):
        result = tasks.send_daily_review_reminders.run()

    assert result == 'Отправлено напоминаний: 0'
    assert f'user_id={user_with_telegram.pk}: ConnectionError' in caplog.text
    assert 'sensitive upstream detail' not in caplog.text
