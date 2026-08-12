import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_SOURCE = PROJECT_ROOT / 'lingua_track' / 'settings.py'
SETTINGS_ENVIRONMENT = {
    'DEBUG',
    'SECRET_KEY',
    'ALLOWED_HOSTS',
    'CSRF_TRUSTED_ORIGINS',
    'DATABASE_URL',
    'TIME_ZONE',
}


@pytest.fixture
def isolated_settings(tmp_path):
    settings_dir = tmp_path / 'lingua_track'
    settings_dir.mkdir()
    settings_path = settings_dir / 'settings.py'
    settings_path.write_bytes(SETTINGS_SOURCE.read_bytes())
    return tmp_path, settings_path


def run_settings(isolated_settings, environment=None):
    base_dir, settings_path = isolated_settings
    env = os.environ.copy()
    for name in SETTINGS_ENVIRONMENT:
        env.pop(name, None)
    env.update(environment or {})

    script = """
import importlib.util
import json
import os
import sys

spec = importlib.util.spec_from_file_location('isolated_runtime_settings', sys.argv[1])
settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings)

print(json.dumps({
    'debug': settings.DEBUG,
    'secret_key': settings.SECRET_KEY,
    'allowed_hosts': settings.ALLOWED_HOSTS,
    'csrf_trusted_origins': settings.CSRF_TRUSTED_ORIGINS,
    'time_zone': settings.TIME_ZONE,
    'database': {key: str(value) for key, value in settings.DATABASES['default'].items()},
    'static_url': settings.STATIC_URL,
    'static_root': str(settings.STATIC_ROOT),
    'staticfiles_dirs': [str(path) for path in settings.STATICFILES_DIRS],
    'media_url': settings.MEDIA_URL,
    'media_root': str(settings.MEDIA_ROOT),
}))
"""
    return subprocess.run(
        [sys.executable, '-c', script, str(settings_path)],
        cwd=base_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def read_settings(isolated_settings, environment=None):
    result = run_settings(isolated_settings, environment)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_development_defaults_are_local_and_use_sqlite(isolated_settings):
    base_dir, _ = isolated_settings
    settings = read_settings(isolated_settings)

    assert settings['debug'] is True
    assert settings['secret_key'].startswith('django-insecure-development-only')
    assert settings['allowed_hosts'] == ['localhost', '127.0.0.1', '[::1]']
    assert settings['csrf_trusted_origins'] == []
    assert settings['time_zone'] == 'UTC'
    assert settings['database']['ENGINE'] == 'django.db.backends.sqlite3'
    assert settings['database']['NAME'] == str(base_dir / 'db.sqlite3')


@pytest.mark.parametrize('value', ['1', 'true', 'TRUE', 'yes', 'on'])
def test_debug_accepts_true_aliases(isolated_settings, value):
    assert read_settings(isolated_settings, {'DEBUG': value})['debug'] is True


@pytest.mark.parametrize('value', ['0', 'false', 'FALSE', 'no', 'off'])
def test_debug_accepts_false_aliases(isolated_settings, value):
    settings = read_settings(isolated_settings, {
        'DEBUG': value,
        'SECRET_KEY': 'dummy-test-only-secret-not-for-production',
    })
    assert settings['debug'] is False


def test_invalid_debug_value_fails_fast(isolated_settings):
    result = run_settings(isolated_settings, {'DEBUG': 'sometimes'})

    assert result.returncode != 0
    assert 'DEBUG must be one of' in result.stderr


def test_environment_takes_precedence_over_dotenv(isolated_settings):
    base_dir, _ = isolated_settings
    (base_dir / '.env').write_text(
        'DEBUG=False\n'
        'SECRET_KEY=dummy-dotenv-secret-not-for-production\n'
        'TIME_ZONE=Europe/Paris\n',
        encoding='utf-8',
    )

    settings = read_settings(isolated_settings, {
        'DEBUG': 'True',
        'TIME_ZONE': 'Europe/Berlin',
    })

    assert settings['debug'] is True
    assert settings['secret_key'] == 'dummy-dotenv-secret-not-for-production'
    assert settings['time_zone'] == 'Europe/Berlin'


def test_production_requires_secret_key(isolated_settings):
    result = run_settings(isolated_settings, {'DEBUG': 'False'})

    assert result.returncode != 0
    assert 'SECRET_KEY must be set when DEBUG=False.' in result.stderr


def test_production_reads_secret_key(isolated_settings):
    settings = read_settings(isolated_settings, {
        'DEBUG': 'False',
        'SECRET_KEY': 'dummy-test-only-secret-not-for-production',
    })

    assert settings['secret_key'] == 'dummy-test-only-secret-not-for-production'


def test_host_and_csrf_lists_are_trimmed(isolated_settings):
    settings = read_settings(isolated_settings, {
        'ALLOWED_HOSTS': 'example.com, www.example.com,,',
        'CSRF_TRUSTED_ORIGINS': 'https://example.com, https://www.example.com,',
    })

    assert settings['allowed_hosts'] == ['example.com', 'www.example.com']
    assert settings['csrf_trusted_origins'] == [
        'https://example.com',
        'https://www.example.com',
    ]


def test_timezone_can_be_overridden(isolated_settings):
    assert read_settings(
        isolated_settings,
        {'TIME_ZONE': 'Europe/Berlin'},
    )['time_zone'] == 'Europe/Berlin'


def test_postgresql_database_url_is_parsed(isolated_settings):
    settings = read_settings(isolated_settings, {
        'DATABASE_URL': 'postgresql://test_user:test_password@db.example:5432/linguatrack',
    })
    database = settings['database']

    assert database['ENGINE'] == 'django.db.backends.postgresql'
    assert database['NAME'] == 'linguatrack'
    assert database['USER'] == 'test_user'
    assert database['PASSWORD'] == 'test_password'
    assert database['HOST'] == 'db.example'
    assert database['PORT'] == '5432'


def test_postgresql_url_decodes_credentials(isolated_settings):
    settings = read_settings(isolated_settings, {
        'DATABASE_URL': 'postgresql://app%2Duser:p%40ss@database:5433/lingua_track',
    })

    assert settings['database']['USER'] == 'app-user'
    assert settings['database']['PASSWORD'] == 'p@ss'


def test_static_and_media_paths(isolated_settings):
    base_dir, _ = isolated_settings
    settings = read_settings(isolated_settings)

    assert settings['static_url'] == '/static/'
    assert settings['static_root'] == str(base_dir / 'staticfiles')
    assert settings['staticfiles_dirs'] == []
    assert settings['media_url'] == '/media/'
    assert settings['media_root'] == str(base_dir / 'media')


def test_django_check_has_no_missing_static_directory_warning():
    env = os.environ.copy()
    env.update({
        'DEBUG': 'True',
        'ALLOWED_HOSTS': 'localhost,127.0.0.1,[::1]',
    })
    for name in ('SECRET_KEY', 'DATABASE_URL', 'CSRF_TRUSTED_ORIGINS'):
        env.pop(name, None)

    result = subprocess.run(
        [sys.executable, 'manage.py', 'check'],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert 'staticfiles.W004' not in result.stdout + result.stderr
