from functools import wraps
from secrets import compare_digest

from django.conf import settings
from django.http import JsonResponse


def require_bot_api_token(view_func):
    """Require the Telegram bot's bearer token for an API view."""

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        authorization = request.headers.get('Authorization', '')
        scheme, separator, provided_token = authorization.partition(' ')
        is_authorized = (
            separator
            and scheme.lower() == 'bearer'
            and bool(provided_token)
            and compare_digest(provided_token, settings.BOT_API_TOKEN)
        )
        if not is_authorized:
            response = JsonResponse({'error': 'Unauthorized'}, status=401)
            response['WWW-Authenticate'] = 'Bearer'
            return response
        return view_func(request, *args, **kwargs)

    return wrapped_view
