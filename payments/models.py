from django.db import models

from orders.models import Order


class Payment(models.Model):
    STATUS_CHOICES = (
        ("pending", "Ожидает обработки"),
        ("success", "Успешно"),
        ("failed", "Неуспешно"),
    )

    PAYMENT_TYPE_CHOICES = (
        ("card", "Онлайн картой"),
        ("someone", "Онлайн со случайного чужого счёта"),
    )

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="payments", verbose_name="Заказ"
    )
    payment_type = models.CharField(
        max_length=10,
        choices=PAYMENT_TYPE_CHOICES,
        default="card",
        verbose_name="Тип платежа",
    )
    number = models.CharField(
        max_length=20, verbose_name="Номер карты/счёта"
    )  # Номер карты/счета
    name = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Имя владельца"
    )  # Имя владельца (только для карт)
    month = models.CharField(
        max_length=2, blank=True, null=True, verbose_name="Месяц"
    )  # Месяц (только для карт)
    year = models.CharField(
        max_length=4, blank=True, null=True, verbose_name="Год"
    )  # Год (только для карт)
    code = models.CharField(
        max_length=3, blank=True, null=True, verbose_name="CVV код"
    )  # CVV (только для карт)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    processed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Дата обработки"
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="pending", verbose_name="Статус"
    )
    error_message = models.TextField(
        blank=True, null=True, verbose_name="Сообщение об ошибке"
    )

    def __str__(self):
        return f"Payment #{self.id} for Order #{self.order.id}"

    class Meta:
        verbose_name = "Платеж"
        verbose_name_plural = "Платежи"
