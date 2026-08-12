# Многоэтапная сборка для оптимизации размера
FROM python:3.11-slim AS builder

# Установка системных зависимостей для сборки
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Создание виртуального окружения
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Копирование и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Финальный образ
FROM python:3.11-slim

# Установка runtime зависимостей
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование виртуального окружения
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Создание пользователя для безопасности
RUN groupadd -r django && useradd -r -m -g django django

# Создание рабочей директории
WORKDIR /app

# Копирование кода приложения
COPY . .

# Создание директорий для медиа и статических файлов
RUN mkdir -p /app/media/audio /app/staticfiles && \
    chown -R django:django /app

# Переключение на пользователя django
USER django

# Открытие порта
EXPOSE 8000

# Команда запуска
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "lingua_track.wsgi:application"]
