import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def inspect_client(environment=None):
    env = os.environ.copy()
    env.pop('DJANGO_API_URL', None)
    env.pop('BOT_API_TOKEN', None)
    env.update(environment or {})
    script = """
import json
from t_bot.api_client import DjangoAPIClient

client = DjangoAPIClient()
requested = {}

class Response:
    status_code = 404
    text = ''

def fake_get(url, **kwargs):
    requested['url'] = url
    return Response()

client.session.get = fake_get
client._make_request('GET', 'api/cards/')
print(json.dumps({
    'base_url': client.base_url,
    'endpoint_url': requested['url'],
    'authorization': client.session.headers['Authorization'],
}))
"""
    result = subprocess.run(
        [sys.executable, '-c', script],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_client_uses_local_default():
    client = inspect_client()

    assert client['base_url'] == 'http://127.0.0.1:8000'
    assert client['endpoint_url'] == 'http://127.0.0.1:8000/api/cards/'
    assert client['authorization'].startswith('Bearer development-only-')


@pytest.mark.parametrize(
    'configured_url',
    ['http://web:8000', 'http://web:8000/'],
)
def test_client_uses_environment_url_without_duplicate_slashes(configured_url):
    client = inspect_client({
        'DJANGO_API_URL': configured_url,
        'BOT_API_TOKEN': 'dummy-test-only-bot-api-token',
    })

    assert client['base_url'] == 'http://web:8000'
    assert client['endpoint_url'] == 'http://web:8000/api/cards/'
    assert client['authorization'] == 'Bearer dummy-test-only-bot-api-token'
