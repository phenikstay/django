"""
Модуль моделей заказов интернет-магазина
"""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from catalog.models import Product


class DeliverySettingsManager(models.Manager):
    """
    Менеджер для модели DeliverySettings, обеспечивающий thread-safe singleton поведение
    """

    def create(self, **kwargs):
        """
        Thread-safe создание записи настроек
        """
        # Принудительно устанавливаем pk=1 для singleton
        kwargs["pk"] = 1

        with transaction.atomic():
            # Проверяем существование с блокировкой
            if self.select_for_update().filter(pk=1).exists():
                raise ValidationError(
                    "Настройки доставки уже существуют. Может быть только одна запись."
                )
            return super().create(**kwargs)

    def get_or_create(self, defaults=None, **kwargs):
        """
        Thread-safe получение или создание записи настроек
        """
        # Принудительно используем pk=1 для singleton
        kwargs["pk"] = 1

        with transaction.atomic():
            try:
                # Пытаемся получить существующую запись с блокировкой
                return self.select_for_update().get(pk=1), False
            except self.model.DoesNotExist:
                # Если записи нет, создаем новую
                if defaults is None:
                    defaults = {}
                defaults.update(kwargs)
                try:
                    return self.create(**defaults), True
                except ValidationError:
                    # Если другой поток создал запись между нашими операциями,
                    # просто возвращаем существующую
                    return self.get(pk=1), False


class DeliverySettings(models.Model):
    """
    Настройки доставки для административного интерфейса (Thread-safe Singleton)
    """

    # Явно устанавливаем ID = 1 для обеспечения единственности
    id = models.AutoField(primary_key=True)

    express_delivery_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=500.00,
        verbose_name="Стоимость экспресс-доставки",
    )
    free_delivery_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=2000.00,
        verbose_name="Сумма для бесплатной доставки",
    )
    regular_delivery_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=200.00,
        verbose_name="Стоимость обычной доставки",
    )

    objects = DeliverySettingsManager()

    class Meta:
        verbose_name = "Настройки доставки"
        verbose_name_plural = "Настройки доставки"
        # Добавляем ограничения на уровне Django для админки
        default_permissions = ("change",)  # Только изменение, без добавления/удаления
        # Добавляем database-level constraint для обеспечения единственности
        constraints = [
            models.CheckConstraint(
                check=models.Q(id=1),
                name="delivery_settings_singleton",
                violation_error_message="Настройки доставки должны иметь id=1 (singleton pattern)",
            )
        ]

    def __str__(self):
        return "Настройки доставки"

    def save(self, *args, **kwargs):
        """
        Thread-safe сохранение с принудительным установлением ID = 1 и очисткой кэша
        """
        # Singleton: принудительно устанавливаем ID = 1
        self.pk = 1
        self.id = 1

        # Используем atomic transaction для thread-safety
        with transaction.atomic():
            # Если это новая запись, проверяем что singleton еще не создан
            if self._state.adding:
                if DeliverySettings.objects.select_for_update().filter(pk=1).exists():
                    raise ValidationError(
                        "Настройки доставки уже существуют. Используйте существующую запись."
                    )

            result = super().save(*args, **kwargs)

            # Очищаем кэш при изменении настроек
            from django.core.cache import cache

            cache.delete("delivery_settings_singleton")

            return result

    def delete(self, *args, **kwargs):
        """
        Предотвращаем удаление единственной записи настроек
        """
        raise ValidationError(
            "Нельзя удалить настройки доставки. Измените значения, если необходимо."
        )

    @classmethod
    def get_settings(cls):
        """
        Thread-safe получение настроек доставки (создает запись по умолчанию, если не существует)

        Использует database-level atomic operations для предотвращения race conditions.
        """
        try:
            # Сначала пытаемся получить существующую запись
            return cls.objects.get(pk=1)
        except cls.DoesNotExist:
            # Если записи нет, используем get_or_create для thread-safe создания
            settings, created = cls.objects.get_or_create(
                pk=1,
                defaults={
                    "express_delivery_cost": 500.00,
                    "free_delivery_threshold": 2000.00,
                    "regular_delivery_cost": 200.00,
                },
            )
            return settings


class Order(models.Model):
    STATUS_CHOICES = (
        ("pending", "Ожидает обработки"),
        ("processing", "Обрабатывается"),
        ("accepted", "Принят"),
        ("completed", "Выполнен"),
        ("canceled", "Отменён"),
    )

    DELIVERY_CHOICES = (
        ("ordinary", "Обычная доставка"),
        ("express", "Экспресс-доставка"),
    )

    PAYMENT_CHOICES = (
        ("online", "Онлайн картой"),
        ("someone", "Онлайн со случайного чужого счёта"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="orders",
        null=True,
        blank=True,
        verbose_name="Пользователь",
    )
    fullName = models.CharField(max_length=255, verbose_name="ФИО")
    email = models.EmailField(verbose_name="Email")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    createdAt = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    deliveryType = models.CharField(
        max_length=10,
        choices=DELIVERY_CHOICES,
        default="ordinary",
        verbose_name="Тип доставки",
    )
    paymentType = models.CharField(
        max_length=10,
        choices=PAYMENT_CHOICES,
        default="online",
        verbose_name="Тип платежа",
    )
    totalCost = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Общая стоимость"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="Статус"
    )
    city = models.CharField(max_length=255, verbose_name="Город")
    address = models.CharField(max_length=255, verbose_name="Адрес")
    comment = models.TextField(blank=True, verbose_name="Комментарий к заказу")
    is_active = models.BooleanField(
        default=True, verbose_name="Активен"
    )  # Для "мягкого" удаления

    def __str__(self):
        return f"Order #{self.id} by {self.fullName}"

    def _get_products_total(self):
        """Кэшированный расчет общей стоимости товаров в заказе"""
        if not hasattr(self, "_cached_products_total"):
            from django.db.models import Sum, F

            self._cached_products_total = (
                self.products.aggregate(total=Sum(F("price") * F("count")))["total"]
                or 0
            )
        return self._cached_products_total

    def calculate_delivery_cost(self, products_total=None):
        """Рассчитывает стоимость доставки согласно ТЗ"""
        settings = DeliverySettings.get_settings()

        if self.deliveryType == "express":
            return settings.express_delivery_cost
        elif self.deliveryType == "ordinary":
            # Используем переданное значение или вычисляем один раз
            if products_total is None:
                products_total = self._get_products_total()

            if products_total < settings.free_delivery_threshold:
                return settings.regular_delivery_cost
            else:
                return 0
        return 0

    def get_total_cost_with_delivery(self):
        """Получить общую стоимость заказа включая доставку"""
        # Вычисляем стоимость товаров один раз
        products_total = self._get_products_total()

        # Передаем уже вычисленное значение в calculate_delivery_cost
        delivery_cost = self.calculate_delivery_cost(products_total)
        return products_total + delivery_cost

    def clear_cache(self):
        """Очищает кэшированные значения (например, при изменении товаров в заказе)"""
        if hasattr(self, "_cached_products_total"):
            delattr(self, "_cached_products_total")

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="products", verbose_name="Заказ"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Цена"
    )  # Цена на момент покупки
    count = models.PositiveIntegerField(default=1, verbose_name="Количество")

    def __str__(self):
        return f"{self.count} x {self.product.title} in Order #{self.order.id}"

    @property
    def total_price(self):
        if self.price is None:
            return 0
        return self.price * self.count

    def save(self, *args, **kwargs):
        """Переопределяем save для очистки кэша заказа"""
        super().save(*args, **kwargs)
        # Очищаем кэш при изменении товара в заказе
        if hasattr(self.order, "clear_cache"):
            self.order.clear_cache()

    class Meta:
        verbose_name = "Товар в заказе"
        verbose_name_plural = "Товары в заказе"


@receiver([post_save, post_delete], sender=OrderItem)
def clear_order_cache_on_item_change(sender, instance, **kwargs):
    """Очищает кэш заказа при изменении/удалении товаров"""
    if hasattr(instance.order, "clear_cache"):
        instance.order.clear_cache()
