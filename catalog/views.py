import json
import logging
from datetime import date

from django.db.models import Q, Count, Avg, Case, When, F, Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Category, Product, Tag, Review, Sale
from .serializers import (
    CategorySerializer,
    ProductShortSerializer,
    ProductFullSerializer,
    TagSerializer,
    ReviewSerializer,
    SaleSerializer,
)

logger = logging.getLogger(__name__)


def get_active_sales_prefetch():
    """
    Создает prefetch для активных скидок (избегает дублирования кода)
    """
    return Prefetch(
        "sales",
        queryset=Sale.objects.filter(
            is_active=True, dateFrom__lte=date.today(), dateTo__gte=date.today()
        ),
        to_attr="active_sales_cached",
    )


@api_view(["GET"])
def categories_list(request):
    """
    Получение каталога категорий
    """
    categories = Category.objects.filter(parent=None, is_active=True)
    serializer = CategorySerializer(categories, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def catalog(request):
    """
    Получение товаров с фильтрацией
    """
    # Получаем параметры запроса
    filter_params = {}
    # Извлекаем параметры фильтрации из запроса в формате filter[param]
    for key, value in request.query_params.items():
        if key.startswith("filter[") and key.endswith("]"):
            param_name = key[7:-1]  # Извлекаем имя параметра из filter[param]
            filter_params[param_name] = value

    # Поддержка формата ?filter=value (для поисковой строки)
    simple_filter = request.query_params.get("filter", None)

    # Если есть простой фильтр, добавляем его в filter[name]
    if simple_filter and simple_filter.strip():
        filter_params["name"] = simple_filter

    current_page = int(request.query_params.get("currentPage", 1))
    category_id = request.query_params.get("category")
    sort_by = request.query_params.get("sort", "date")
    sort_type = request.query_params.get("sortType", "dec")

    # Получаем список тегов из параметров запроса
    tags = []
    for key, value in request.query_params.items():
        if key.startswith("tags[") and key.endswith("]"):
            tags.append(value)

    limit = int(request.query_params.get("limit", 20))

    # Создаем prefetch для активных скидок
    active_sales_prefetch = get_active_sales_prefetch()

    # Базовый QuerySet с оптимизированными связями
    products = (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .prefetch_related("tags", active_sales_prefetch)
    )

    # Флаг для отслеживания создания аннотации с ценой
    price_annotated = False

    # Применяем фильтры
    if category_id:
        # Проверяем, является ли категория родительской
        category = Category.objects.filter(id=category_id).first()
        if category and Category.objects.filter(parent=category).exists():
            # Если категория родительская, включаем товары из всех её подкатегорий
            subcategory_ids = Category.objects.filter(parent=category).values_list(
                "id", flat=True
            )
            products = products.filter(category_id__in=list(subcategory_ids))
        else:
            # Если категория не родительская, фильтруем только по ней
            products = products.filter(category_id=category_id)

    # Фильтрация по имени (поиск)
    if "name" in filter_params and filter_params["name"]:
        # Создаем различные варианты поискового запроса для обеспечения регистронезависимости
        search_term = filter_params["name"]
        search_term_lower = search_term.lower()
        search_term_upper = search_term.upper()
        search_term_title = search_term.title()

        # Создаем Q-объекты для поиска по разным полям
        title_query = (
            Q(title__icontains=search_term)
            | Q(title__icontains=search_term_lower)
            | Q(title__icontains=search_term_upper)
            | Q(title__icontains=search_term_title)
        )

        # Поиск в описании
        description_query = Q(description__icontains=search_term) | Q(
            fullDescription__icontains=search_term
        )

        # Поиск в характеристиках
        spec_query = Q(specifications__name__icontains=search_term) | Q(
            specifications__value__icontains=search_term
        )

        # Объединяем все условия поиска
        search_query = title_query | description_query | spec_query

        # Применяем фильтр и убираем дубликаты
        products = products.filter(search_query).distinct()

    # Фильтрация по цене (с учетом скидок) - создаем аннотацию один раз
    needs_price_filter = (
        ("minPrice" in filter_params and filter_params["minPrice"])
        or ("maxPrice" in filter_params and filter_params["maxPrice"])
        or sort_by == "price"
    )

    if needs_price_filter and not price_annotated:
        # Создаем аннотацию с текущей ценой один раз
        products = products.annotate(
            current_price=Case(
                When(
                    sales__is_active=True,
                    sales__dateFrom__lte=date.today(),
                    sales__dateTo__gte=date.today(),
                    then=F("sales__salePrice"),
                ),
                default=F("price"),
            )
        ).distinct()
        price_annotated = True

    # Применяем фильтры по цене
    if "minPrice" in filter_params and filter_params["minPrice"]:
        try:
            min_price = float(filter_params["minPrice"])
            products = products.filter(current_price__gte=min_price)
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Ошибка парсинга минимальной цены '{filter_params['minPrice']}': {str(e)}"
            )

    if "maxPrice" in filter_params and filter_params["maxPrice"]:
        try:
            max_price = float(filter_params["maxPrice"])
            products = products.filter(current_price__lte=max_price)
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Ошибка парсинга максимальной цены '{filter_params['maxPrice']}': {str(e)}"
            )

    # Фильтрация по бесплатной доставке
    if (
        "freeDelivery" in filter_params
        and filter_params["freeDelivery"].lower() == "true"
    ):
        products = products.filter(freeDelivery=True)

    # Фильтрация по наличию
    if "available" in filter_params and filter_params["available"].lower() == "true":
        products = products.filter(count__gt=0)

    # Фильтрация по тегам
    if tags:
        try:
            tags_list = [int(tag) for tag in tags if tag.isdigit()]
            if tags_list:
                products = products.filter(tags__id__in=tags_list).distinct()
        except (ValueError, TypeError) as e:
            logger.warning(f"Ошибка парсинга тегов {tags}: {str(e)}")

    # Сортировка
    if sort_by == "rating":
        sort_field = "-rating" if sort_type == "dec" else "rating"
    elif sort_by == "price":
        # Используем уже созданную аннотацию
        sort_field = "-current_price" if sort_type == "dec" else "current_price"
    elif sort_by == "reviews":
        if sort_type == "dec":
            products = products.annotate(reviews_count=Count("reviews")).order_by(
                "-reviews_count"
            )
        else:
            products = products.annotate(reviews_count=Count("reviews")).order_by(
                "reviews_count"
            )
        sort_field = None
    else:  # sort_by == 'date'
        sort_field = "-date" if sort_type == "dec" else "date"

    if sort_field:
        products = products.order_by(sort_field)

    # Пагинация
    total_count = products.count()
    last_page = (total_count + limit - 1) // limit

    # Получаем товары для текущей страницы
    start = (current_page - 1) * limit
    end = start + limit
    products = products[start:end]

    # Сериализуем результаты
    serializer = ProductShortSerializer(products, many=True)

    return Response(
        {"items": serializer.data, "currentPage": current_page, "lastPage": last_page}
    )


@api_view(["GET"])
def popular_products(request):
    """
    Получение популярных товаров
    """
    # Создаем prefetch для активных скидок
    active_sales_prefetch = get_active_sales_prefetch()

    products = (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .prefetch_related("tags", active_sales_prefetch)
        .order_by("-purchases_count", "-rating")[:8]
    )
    serializer = ProductShortSerializer(products, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def limited_products(request):
    """
    Получение товаров с ограниченным тиражом
    """
    # Создаем prefetch для активных скидок
    active_sales_prefetch = get_active_sales_prefetch()

    products = (
        Product.objects.filter(limited=True, is_active=True)
        .select_related("category")
        .prefetch_related("tags", active_sales_prefetch)[:16]
    )
    serializer = ProductShortSerializer(products, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def sales(request):
    """
    Получение товаров со скидками
    """
    current_page = int(request.query_params.get("currentPage", 1))
    limit = 20

    # Получаем активные скидки только для активных товаров
    sales = (
        Sale.objects.filter(
            is_active=True,
            product__is_active=True,
            dateFrom__lte=date.today(),
            dateTo__gte=date.today(),
        )
        .select_related("product__category")
        .prefetch_related("product__tags")
    )

    # Пагинация с использованием QuerySet
    total_count = sales.count()
    last_page = (total_count + limit - 1) // limit

    # Получаем скидки для текущей страницы
    start = (current_page - 1) * limit
    end = start + limit
    sales_page = sales[start:end]

    # Сериализуем результаты
    serializer = SaleSerializer(sales_page, many=True)

    return Response(
        {"items": serializer.data, "currentPage": current_page, "lastPage": last_page}
    )


@api_view(["GET"])
def banners(request):
    """
    Получение баннеров (избранные товары)
    """
    # Создаем prefetch для активных скидок
    active_sales_prefetch = get_active_sales_prefetch()

    # Получаем товары, отмеченные как баннеры в админке
    products = (
        Product.objects.filter(is_active=True, is_banner=True)
        .select_related("category")
        .prefetch_related("tags", active_sales_prefetch)[:3]
    )
    serializer = ProductShortSerializer(products, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def product_detail(request, pk):
    """
    Получение детальной информации о товаре
    """
    # Создаем prefetch для активных скидок
    active_sales_prefetch = get_active_sales_prefetch()

    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related(
            "tags",
            "specifications",
            active_sales_prefetch,
            Prefetch("reviews", queryset=Review.objects.filter(is_active=True)),
        ),
        pk=pk,
        is_active=True,
    )
    serializer = ProductFullSerializer(product)
    return Response(serializer.data)


@api_view(["GET", "POST"])
def review(request, product_id):
    """
    Получение отзывов (GET) и добавление отзыва к товару (POST)
    """
    product = get_object_or_404(
        Product.objects.select_related("category"), pk=product_id, is_active=True
    )

    if request.method == "GET":
        # Возвращаем все отзывы для товара
        reviews = Review.objects.filter(product=product, is_active=True)
        # Создаем контекст для кэширования пользователей и оптимизации запросов
        context = {"users_cache": {}}
        review_serializer = ReviewSerializer(reviews, many=True, context=context)
        return Response(review_serializer.data)

    elif request.method == "POST":
        # Получаем данные отзыва
        data = json.loads(request.body)
        data["product"] = product.id

        # Создаем и сохраняем отзыв
        serializer = ReviewSerializer(data=data)
        if serializer.is_valid():
            serializer.save(product=product)

            # Обновляем рейтинг товара
            reviews = Review.objects.filter(product=product, is_active=True)
            avg_rating = reviews.aggregate(avg_rating=Avg("rate"))["avg_rating"] or 0
            product.rating = avg_rating
            product.save()

            # Возвращаем все отзывы
            reviews = Review.objects.filter(product=product, is_active=True)
            # Создаем контекст для кэширования пользователей и оптимизации запросов
            context = {"users_cache": {}}
            review_serializer = ReviewSerializer(reviews, many=True, context=context)
            return Response(review_serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Если метод не GET и не POST, возвращаем ошибку
    return Response(
        {"error": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


@api_view(["GET"])
def tags_list(request):
    """
    Получение списка тегов
    """
    category_id = request.query_params.get("category")

    tags = Tag.objects.filter(is_active=True)

    # Если задана категория, фильтруем теги по ней
    if category_id:
        # Проверяем, является ли категория родительской
        category = Category.objects.filter(id=category_id).first()
        if category and Category.objects.filter(parent=category).exists():
            # Если категория родительская, включаем теги из всех её подкатегорий
            subcategory_ids = Category.objects.filter(parent=category).values_list(
                "id", flat=True
            )
            tags = tags.filter(
                products__category_id__in=list(subcategory_ids)
            ).distinct()
        else:
            # Если категория не родительская, фильтруем только по ней
            tags = tags.filter(products__category_id=category_id).distinct()

    serializer = TagSerializer(tags, many=True)
    return Response(serializer.data)
