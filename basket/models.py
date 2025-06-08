from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models

from catalog.models import Product


class BasketItem(models.Model):
    """
    Модель элемента корзины, связывающая пользователя с товаром.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="basket_items",
        verbose_name="Пользователь",
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    count = models.PositiveIntegerField(default=1, verbose_name="Количество")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")

    class Meta:
        verbose_name = "Элемент корзины"
        verbose_name_plural = "Элементы корзины"
        ordering = ["id"]
        unique_together = ["user", "product"]

    def __str__(self):
        return f"{self.count} x {self.product.title} ({self.user.username})"

    @property
    def total_price(self) -> Decimal:
        """
        Возвращает общую стоимость элемента корзины (цена * количество)
        """
        return self.product.get_current_price() * self.count
