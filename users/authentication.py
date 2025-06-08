from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    Аутентификация через сессии без проверки CSRF токена
    """

    def enforce_csrf(self, request):
        return  # Отключаем проверку CSRF
