from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Название")
    is_active = models.BooleanField(
        default=True, verbose_name="Активен"
    )  # Для "мягкого" удаления

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Тег"
        verbose_name_plural = "Теги"


class Category(models.Model):
    title = models.CharField(max_length=255, verbose_name="Название")
    image = models.ImageField(
        upload_to="categories/", blank=True, null=True, verbose_name="Изображение"
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="subcategories",
        verbose_name="Родительская категория",
    )
    is_active = models.BooleanField(
        default=True, verbose_name="Активна"
    )  # Для "мягкого" удаления

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name="Категория",
    )
    title = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    fullDescription = models.TextField(blank=True, verbose_name="Полное описание")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Цена",
    )
    count = models.PositiveIntegerField(default=0, verbose_name="Количество")
    date = models.DateTimeField(default=timezone.now, verbose_name="Дата добавления")
    freeDelivery = models.BooleanField(
        default=False, verbose_name="Бесплатная доставка"
    )
    image = models.ImageField(
        upload_to="products/", blank=True, null=True, verbose_name="Изображение товара"
    )
    image_alt = models.CharField(
        max_length=255, blank=True, verbose_name="Альтернативный текст изображения"
    )
    tags = models.ManyToManyField(
        Tag, related_name="products", blank=True, verbose_name="Теги"
    )
    rating = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name="Рейтинг",
    )
    purchases_count = models.PositiveIntegerField(
        default=0, verbose_name="Количество покупок"
    )  # Для определения популярности
    limited = models.BooleanField(
        default=False, verbose_name="Ограниченный тираж"
    )  # Для товаров с ограниченным тиражом
    is_active = models.BooleanField(
        default=True, verbose_name="Активен"
    )  # Для "мягкого" удаления
    is_banner = models.BooleanField(
        default=False, verbose_name="В баннере"
    )  # Для отображения в баннерах на главной странице

    def __str__(self):
        return self.title

    def get_current_price(self):
        """Возвращает текущую цену с учетом активных скидок"""
        active_sale = self.sales.filter(
            is_active=True, dateFrom__lte=date.today(), dateTo__gte=date.today()
        ).first()

        if active_sale:
            return active_sale.salePrice
        return self.price

    def get_active_sale(self):
        """Возвращает активную скидку если есть"""
        return self.sales.filter(
            is_active=True, dateFrom__lte=date.today(), dateTo__gte=date.today()
        ).first()

    def has_active_sale(self):
        """Проверяет, есть ли активная скидка"""
        return self.get_active_sale() is not None

    def get_image_url(self):
        """Возвращает URL изображения или placeholder"""
        if self.image:
            return self.image.url
        return "/media/placeholder.jpg"

    def get_image_alt(self):
        """Возвращает альтернативный текст или название товара"""
        return self.image_alt or f"Изображение {self.title}"

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"


class Specification(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="specifications",
        verbose_name="Товар",
    )
    name = models.CharField(max_length=255, verbose_name="Название")
    value = models.CharField(max_length=255, verbose_name="Значение")

    def __str__(self):
        return f"{self.name}: {self.value}"

    class Meta:
        verbose_name = "Характеристика"
        verbose_name_plural = "Характеристики"


class Review(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews", verbose_name="Товар"
    )
    author = models.CharField(max_length=255, verbose_name="Автор")
    email = models.EmailField(verbose_name="Email")
    text = models.TextField(verbose_name="Текст отзыва")
    rate = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Оценка"
    )
    date = models.DateTimeField(default=timezone.now, verbose_name="Дата")
    is_active = models.BooleanField(
        default=True, verbose_name="Активен"
    )  # Для "мягкого" удаления

    def __str__(self):
        return f"Review by {self.author} for {self.product.title}"

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"


class Sale(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="sales", verbose_name="Товар"
    )
    salePrice = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Цена со скидкой",
    )
    dateFrom = models.DateField(verbose_name="Дата начала")
    dateTo = models.DateField(verbose_name="Дата окончания")
    is_active = models.BooleanField(
        default=True, verbose_name="Активна"
    )  # Для "мягкого" удаления

    def clean(self):
        """Валидация для предотвращения пересекающихся активных скидок"""
        super().clean()

        if self.dateFrom and self.dateTo:
            if self.dateFrom > self.dateTo:
                raise ValidationError(
                    {"dateTo": "Дата окончания не может быть раньше даты начала"}
                )

        # Проверяем пересекающиеся активные скидки только если скидка активна
        if self.is_active and self.product_id and self.dateFrom and self.dateTo:
            overlapping_sales = Sale.objects.filter(
                product=self.product,
                is_active=True,
                dateFrom__lte=self.dateTo,
                dateTo__gte=self.dateFrom,
            )

            # Исключаем текущую скидку при обновлении
            if self.pk:
                overlapping_sales = overlapping_sales.exclude(pk=self.pk)

            if overlapping_sales.exists():
                overlapping_sale = overlapping_sales.first()
                raise ValidationError(
                    {
                        "dateFrom": f"Период скидки пересекается с существующей скидкой "
                        f"({overlapping_sale.dateFrom} - {overlapping_sale.dateTo})"
                    }
                )

    def save(self, *args, **kwargs):
        """Переопределяем save для выполнения валидации"""
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sale for {self.product.title}"

    class Meta:
        verbose_name = "Скидка"
        verbose_name_plural = "Скидки"
        # Добавляем индекс для оптимизации запросов поиска активных скидок
        indexes = [
            models.Index(fields=["product", "is_active", "dateFrom", "dateTo"]),
        ]
