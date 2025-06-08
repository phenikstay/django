from django.apps import AppConfig


class BasketConfig(AppConfig):
    """
    Конфигурация приложения корзины покупок
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "basket"
    verbose_name = "Корзина покупок"
