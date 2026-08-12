import os
from pathlib import Path

import dj_database_url
from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env', override=False)


def _get_bool(name, default):
    """Read a boolean environment variable or fail on an ambiguous value."""
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    raise ImproperlyConfigured(
        f'{name} must be one of: true, false, 1, 0, yes, no, on, off.'
    )


def _get_list(name, default=()):
    """Read a comma-separated environment variable, ignoring empty items."""
    value = os.getenv(name)
    if value is None:
        return list(default)
    return [item.strip() for item in value.split(',') if item.strip()]


# --- Безопасность ---
DEBUG = _get_bool('DEBUG', True)

_configured_secret_key = os.getenv('SECRET_KEY', '').strip()
if not DEBUG and not _configured_secret_key:
    raise ImproperlyConfigured('SECRET_KEY must be set when DEBUG=False.')
SECRET_KEY = (
    _configured_secret_key
    or 'django-insecure-development-only-key-do-not-use-in-production'
)

ALLOWED_HOSTS = _get_list('ALLOWED_HOSTS', ('localhost', '127.0.0.1', '[::1]'))
CSRF_TRUSTED_ORIGINS = _get_list('CSRF_TRUSTED_ORIGINS')

# --- Приложения ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'users',
    'cards',
    'core',
    'bot_api',
]

# --- Middleware ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'lingua_track.urls'

# --- Шаблоны ---
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'lingua_track.wsgi.application'

# --- База данных ---
_database_url = os.getenv('DATABASE_URL', '').strip()
if _database_url:
    DATABASES = {'default': dj_database_url.parse(_database_url)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# --- Валидация паролей ---
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTH_USER_MODEL = 'users.User'

# --- Локализация ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.getenv('TIME_ZONE', 'UTC')
USE_I18N = True
USE_TZ = True

# --- Статика ---
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

_project_static_dir = BASE_DIR / 'static'
STATICFILES_DIRS = [_project_static_dir] if _project_static_dir.is_dir() else []

# --- Медиа ---
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --- Primary key ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Celery ---
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_SOFT_TIME_LIMIT = 60  # 1 минута на задачу
CELERY_TASK_TIME_LIMIT = 120      # 2 минуты на задачу

CELERY_BEAT_SCHEDULE = {
    'send-daily-review-reminders': {
        'task': 'cards.tasks.send_daily_review_reminders',
        'schedule': crontab(hour=8, minute=0),  # каждый день в 8:00 утра
    },
}
