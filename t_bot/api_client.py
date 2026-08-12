"""
API клиент для взаимодействия с Django-приложением.

DjangoAPIClient — клиент для выполнения HTTP-запросов к Django API
для получения данных карточек, прогресса пользователя и других функций.
"""

import requests
import json
import logging
from typing import Tuple, List, Dict, Optional, Any
from urllib.parse import urljoin

from .config import BOT_API_TOKEN, DJANGO_API_URL

logger = logging.getLogger(__name__)


class DjangoAPIClient:
    """
    Клиент для взаимодействия с Django API.
    
    Выполняет HTTP-запросы к Django-приложению для получения данных
    карточек, прогресса пользователя, озвучки слов и других функций.
    
    Attributes:
        base_url: Базовый URL Django-приложения.
        session: Сессия requests для переиспользования соединений.
    
    Note:
        Все методы возвращают кортеж (success, data), где success - булево
        значение успешности запроса, data - данные ответа или сообщение об ошибке.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_token: Optional[str] = None,
    ):
        """
        Инициализация API клиента.
        
        Args:
            base_url: Базовый URL Django-приложения.
        """
        configured_url = (
            base_url
            if base_url is not None
            else DJANGO_API_URL
        )
        self.base_url = configured_url.rstrip('/')
        self.session = requests.Session()
        configured_token = api_token if api_token is not None else BOT_API_TOKEN
        
        # Настройка сессии для лучшей производительности
        self.session.headers.update({
            'Authorization': f'Bearer {configured_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'LinguaTrack-Bot/1.0'
        })

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Any]:
        """
        Выполняет HTTP-запрос к API.
        
        Args:
            method: HTTP метод (GET, POST, etc.).
            endpoint: Конечная точка API.
            data: Данные для отправки (для POST запросов).
            params: Параметры запроса (для GET запросов).
        
        Returns:
            Кортеж (success, response_data).
        
        Note:
            Обрабатывает сетевые ошибки и ошибки HTTP статусов.
        """
        url = urljoin(f"{self.base_url}/", endpoint)
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=params, timeout=10)
            elif method.upper() == 'POST':
                response = self.session.post(
                    url,
                    json=data,
                    params=params,
                    timeout=10
                )
            else:
                return False, f"Неподдерживаемый HTTP метод: {method}"
            
            # Проверяем HTTP статус
            if response.status_code == 200:
                try:
                    return True, response.json()
                except json.JSONDecodeError:
                    return True, response.text
            elif response.status_code == 404:
                return False, "API endpoint не найден"
            elif response.status_code == 500:
                return False, "Внутренняя ошибка сервера"
            else:
                return False, f"HTTP ошибка {response.status_code}: {response.text}"
                
        except requests.exceptions.ConnectionError:
            return False, "Не удается подключиться к Django-серверу"
        except requests.exceptions.Timeout:
            return False, "Таймаут запроса к API"
        except requests.exceptions.RequestException as e:
            return False, f"Ошибка сети: {str(e)}"
        except Exception as e:
            logger.error(f"Неожиданная ошибка в API запросе: {e}")
            return False, f"Неожиданная ошибка: {str(e)}"

    def bind_telegram(self, token: str, telegram_id: int) -> Tuple[bool, str]:
        """
        Привязывает Telegram ID к пользователю через токен.
        
        Args:
            token: Токен для привязки из magic-ссылки.
            telegram_id: Telegram ID пользователя.
        
        Returns:
            Кортеж (success, message).
        """
        data = {
            'token': token,
            'telegram_id': telegram_id
        }
        success, response = self._make_request('POST', 'api/telegram/bind/', data)
        
        if success and isinstance(response, dict):
            return True, response.get('message', 'Аккаунт успешно привязан')
        else:
            return False, str(response)

    def get_cards(self, telegram_id: int) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Получает список карточек пользователя.
        
        Args:
            telegram_id: Telegram ID пользователя.
        
        Returns:
            Кортеж (success, cards_list).
        """
        params = {'telegram_id': telegram_id}
        success, response = self._make_request('GET', 'api/cards/', params=params)
        
        if success and isinstance(response, dict):
            return True, response.get('cards', [])
        else:
            return False, []

    def get_today_cards(self, telegram_id: int) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Получает карточки на сегодня для повторения.
        
        Args:
            telegram_id: Telegram ID пользователя.
        
        Returns:
            Кортеж (success, cards_list).
        """
        params = {'telegram_id': telegram_id}
        success, response = self._make_request('GET', 'api/today/', params=params)
        
        if success and isinstance(response, dict):
            return True, response.get('cards', [])
        else:
            return False, []

    def get_progress(self, telegram_id: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Получает прогресс обучения пользователя.
        
        Args:
            telegram_id: Telegram ID пользователя.
        
        Returns:
            Кортеж (success, progress_data).
        """
        params = {'telegram_id': telegram_id}
        success, response = self._make_request('GET', 'api/progress/', params=params)
        
        if success and isinstance(response, dict):
            return True, response
        else:
            return False, {}

    def get_tts_audio(self, telegram_id: int, word: str) -> Tuple[bool, Optional[bytes]]:
        """
        Получает аудиофайл для озвучки слова.
        
        Args:
            telegram_id: Telegram ID пользователя.
            word: Слово для озвучки.
        
        Returns:
            Кортеж (success, audio_data).
        """
        params = {
            'telegram_id': telegram_id,
            'word': word
        }
        
        try:
            url = urljoin(f"{self.base_url}/", 'api/tts/')
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                return True, response.content
            else:
                return False, None
                
        except Exception as e:
            logger.error(f"Ошибка получения аудио: {e}")
            return False, None

    def submit_test_result(
        self,
        telegram_id: int,
        card_id: int,
        answer: bool
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Отправляет результат тестирования карточки.
        
        Args:
            telegram_id: Telegram ID пользователя.
            card_id: ID карточки.
            answer: Ответ пользователя (True - знал, False - не знал).
        
        Returns:
            Кортеж (success, response_data).
        """
        data = {
            'telegram_id': telegram_id,
            'card_id': card_id,
            'answer': answer
        }
        success, response = self._make_request('POST', 'api/test/', data)
        
        if success and isinstance(response, dict):
            return True, response
        else:
            return False, {'msg': str(response)}

    def get_multiple_choice(self, telegram_id: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Получает карточку для теста с множественным выбором.
        
        Args:
            telegram_id: Telegram ID пользователя.
        
        Returns:
            Кортеж (success, test_data).
        """
        params = {'telegram_id': telegram_id}
        success, response = self._make_request(
            'GET',
            'api/test/multiple_choice/',
            params=params
        )
        
        if success and isinstance(response, dict):
            return True, response
        else:
            return False, {}

    def submit_multiple_choice(
        self,
        telegram_id: int,
        card_id: int,
        answer: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Отправляет ответ на тест с множественным выбором.
        
        Args:
            telegram_id: Telegram ID пользователя.
            card_id: ID карточки.
            answer: Выбранный ответ.
        
        Returns:
            Кортеж (success, response_data).
        """
        data = {
            'telegram_id': telegram_id,
            'card_id': card_id,
            'answer': answer
        }
        success, response = self._make_request(
            'POST',
            'api/test/multiple_choice/',
            data
        )
        
        if success and isinstance(response, dict):
            return True, response
        else:
            return False, {'msg': str(response)}

    def __del__(self):
        """Закрывает сессию при удалении объекта."""
        if hasattr(self, 'session'):
            self.session.close()
