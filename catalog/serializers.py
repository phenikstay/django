from rest_framework import serializers

from .models import Category, Product, Tag, Review, Specification, Sale


class ProductImageMixin:
    """Миксин для получения изображений товара"""

    def get_images(self, obj):
        """Возвращает список с одним изображением для совместимости с API"""
        # Проверяем, работаем ли мы с товаром напрямую или через связанный объект
        product = obj if isinstance(obj, Product) else getattr(obj, "product", None)
        if product:
            return [{"src": product.get_image_url(), "alt": product.get_image_alt()}]
        return [{"src": "/media/placeholder.jpg", "alt": "Изображение товара"}]


class ProductSalePriceMixin:
    """Миксин для получения цены со скидкой"""

    def get_salePrice(self, obj):
        """Возвращает цену со скидкой если есть активная скидка"""

        # Проверяем, работаем ли мы с товаром напрямую или через связанный объект
        product = obj if isinstance(obj, Product) else getattr(obj, "product", None)
        if product:
            # Используем кэшированные активные скидки если доступны
            if hasattr(product, "active_sales_cached"):
                active_sales = product.active_sales_cached
                if active_sales:
                    # Возвращаем первую активную скидку (должна быть только одна)
                    return active_sales[0].salePrice
            else:
                # Fallback на стандартный метод если кэш недоступен
                active_sale = product.get_active_sale()
                if active_sale:
                    return active_sale.salePrice
        return None


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name")


class SubcategorySerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "title", "image")

    def get_image(self, obj):
        if obj.image:
            return {"src": obj.image.url, "alt": f"Изображение категории {obj.title}"}
        return {
            "src": "/media/placeholder.jpg",
            "alt": f"Изображение категории {obj.title}",
        }


class CategorySerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    subcategories = SubcategorySerializer(many=True)

    class Meta:
        model = Category
        fields = ("id", "title", "image", "subcategories")

    def get_image(self, obj):
        if obj.image:
            return {"src": obj.image.url, "alt": f"Изображение категории {obj.title}"}
        return {
            "src": "/media/placeholder.jpg",
            "alt": f"Изображение категории {obj.title}",
        }


class ReviewSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ("author", "email", "text", "rate", "date", "avatar")

    def get_avatar(self, obj):
        """
        Оптимизированное получение аватара пользователя с кэшированием.
        Использует context для кэширования пользователей и избежания N+1 запросов.
        """
        # Получаем контекст serializer для кэширования
        context = self.context or {}
        users_cache = context.setdefault("users_cache", {})

        # Проверяем кэш пользователей
        if obj.email not in users_cache:
            try:
                # Импортируем User локально для избежания неиспользуемого импорта на уровне модуля
                from django.contrib.auth.models import User

                # Получаем пользователя с профилем одним запросом
                user = User.objects.select_related("profile").get(email=obj.email)
                users_cache[obj.email] = user
            except User.DoesNotExist:
                # Кэшируем None для несуществующих пользователей
                users_cache[obj.email] = None

        user = users_cache[obj.email]

        # Возвращаем аватар пользователя или placeholder
        if user and hasattr(user, "profile") and user.profile.avatar:
            if hasattr(user.profile.avatar, "url"):
                return user.profile.avatar.url
            else:
                # Если аватар задан как строка (например, 'placeholder.jpg')
                return f"/media/{user.profile.avatar}"

        return "/media/placeholder.jpg"


class SpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specification
        fields = ("name", "value")


class ProductShortSerializer(
    ProductImageMixin, ProductSalePriceMixin, serializers.ModelSerializer
):
    images = serializers.SerializerMethodField()
    tags = TagSerializer(many=True)
    reviews = serializers.SerializerMethodField()
    salePrice = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "category",
            "price",
            "salePrice",
            "count",
            "date",
            "title",
            "description",
            "freeDelivery",
            "images",
            "tags",
            "reviews",
            "rating",
        )

    def get_reviews(self, obj):
        # Возвращаем количество отзывов
        return obj.reviews.filter(is_active=True).count()


class ProductFullSerializer(
    ProductImageMixin, ProductSalePriceMixin, serializers.ModelSerializer
):
    images = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    specifications = SpecificationSerializer(many=True)
    salePrice = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "category",
            "price",
            "salePrice",
            "count",
            "date",
            "title",
            "description",
            "fullDescription",
            "freeDelivery",
            "images",
            "tags",
            "reviews",
            "specifications",
            "rating",
        )

    def get_reviews(self, obj):
        """
        Оптимизированное получение отзывов с передачей контекста для кэширования
        """
        # Получаем активные отзывы (предполагается что они были prefetch в view)
        active_reviews = obj.reviews.filter(is_active=True)

        # Передаем контекст для кэширования пользователей
        context = self.context or {}
        if "users_cache" not in context:
            context["users_cache"] = {}

        # Сериализуем отзывы с передачей контекста
        return ReviewSerializer(active_reviews, many=True, context=context).data

    def get_tags(self, obj):
        # Возвращаем полную информацию о тегах (ID и название)
        return TagSerializer(obj.tags.filter(is_active=True), many=True).data


class SaleSerializer(ProductImageMixin, serializers.ModelSerializer):
    images = serializers.SerializerMethodField()
    price = serializers.DecimalField(
        source="product.price", max_digits=10, decimal_places=2
    )
    title = serializers.CharField(source="product.title")
    description = serializers.CharField(source="product.description")
    reviews = serializers.SerializerMethodField()
    id = serializers.IntegerField(source="product.id")

    class Meta:
        model = Sale
        fields = (
            "id",
            "price",
            "salePrice",
            "dateFrom",
            "dateTo",
            "title",
            "description",
            "reviews",
            "images",
        )

    def get_reviews(self, obj):
        # Возвращаем количество отзывов для товара
        return obj.product.reviews.filter(is_active=True).count()
