import json
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from basket.models import BasketItem
from catalog.models import Product
from users.models import Profile
from .models import Order, DeliverySettings, OrderItem
from .serializers import OrderSerializer


@api_view(["GET", "POST"])
def orders(request):
    """
    Получение списка заказов или создание нового заказа
    """
    # GET: получение списка заказов
    if request.method == "GET":
        # Для авторизованных пользователей возвращаем их заказы
        if request.user.is_authenticated:
            orders = (
                Order.objects.filter(user=request.user, is_active=True)
                .prefetch_related("products__product")
                .order_by("-createdAt")
            )
            serializer = OrderSerializer(orders, many=True)
            return Response(serializer.data)
        return Response([], status=status.HTTP_200_OK)

    # POST: создание нового заказа
    elif request.method == "POST":
        # Получаем данные корзины из запроса
        data = json.loads(request.body)

        # Подготавливаем данные для заказа
        order_data = {
            "user": request.user if request.user.is_authenticated else None,
            "totalCost": 0,  # Временно, потом пересчитаем
            "fullName": "",
            "email": "",
            "phone": "",
        }

        # Для авторизованных пользователей берем данные из профиля
        if request.user.is_authenticated:
            try:
                profile = request.user.profile
                order_data["fullName"] = profile.fullName or ""
                order_data["email"] = request.user.email or ""
                order_data["phone"] = profile.phone or ""
            except ObjectDoesNotExist:
                # Если профиля нет, создаем его
                Profile.objects.create(user=request.user)

        # Создаем заказ без связи с товарами
        order = Order.objects.create(**order_data)

        # Добавляем товары из корзины в заказ
        total_cost = Decimal("0.00")

        for item in data:
            try:
                product_id = item.get("id")
                count = item.get("count", 1)

                product = Product.objects.get(id=product_id, is_active=True)

                # Создаем элемент заказа
                order_item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    price=product.get_current_price(),
                    count=count,
                )

                # Обновляем общую стоимость
                total_cost += product.get_current_price() * Decimal(str(count))

                # Увеличиваем счетчик покупок товара
                product.purchases_count += count
                product.save()

            except ObjectDoesNotExist:
                continue

        # Если для текущего пользователя есть корзина, очищаем её
        if request.user.is_authenticated:
            BasketItem.objects.filter(user=request.user).delete()
        else:
            # Для анонимных пользователей очищаем сессию
            request.session["basket"] = []

        # Обновляем общую стоимость заказа (только товары, доставка рассчитается позже)
        order.totalCost = total_cost
        order.save()

        # Возвращаем ID созданного заказа
        return Response({"orderId": order.id})

    # Если метод не GET и не POST, возвращаем ошибку
    return Response(
        {"error": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


@api_view(["GET", "POST"])
def order_view(request, order_id):
    """
    Получение деталей заказа или подтверждение заказа
    """
    # Проверяем, что заказ существует и принадлежит текущему пользователю
    if request.user.is_authenticated:
        order = get_object_or_404(
            Order.objects.prefetch_related("products__product"),
            pk=order_id,
            user=request.user,
            is_active=True,
        )
    else:
        order = get_object_or_404(
            Order.objects.prefetch_related("products__product"),
            pk=order_id,
            user=None,
            is_active=True,
        )

    # GET: получение деталей заказа
    if request.method == "GET":
        serializer = OrderSerializer(order)
        return Response(serializer.data)

    # POST: подтверждение заказа
    elif request.method == "POST":
        data = json.loads(request.body)

        # Обновляем информацию о заказе
        order.fullName = data.get("fullName", "")
        order.email = data.get("email", "")
        order.phone = data.get("phone", "")
        order.deliveryType = data.get("deliveryType", "ordinary")
        order.paymentType = data.get("paymentType", "online")
        order.city = data.get("city", "")
        order.address = data.get("address", "")
        order.comment = data.get("comment", "")

        # Пересчитываем общую стоимость с учетом доставки
        order.totalCost = order.get_total_cost_with_delivery()

        # Меняем статус заказа
        order.status = "accepted"

        # Сохраняем обновленный заказ
        order.save()

        return Response(status=status.HTTP_200_OK)

    # Если метод не GET и не POST, возвращаем ошибку
    return Response(
        {"error": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


@api_view(["GET"])
def delivery_settings(request):
    """
    Получение настроек доставки для frontend
    """
    settings = DeliverySettings.get_settings()
    return Response(
        {
            "express_delivery_cost": float(settings.express_delivery_cost),
            "free_delivery_threshold": float(settings.free_delivery_threshold),
            "regular_delivery_cost": float(settings.regular_delivery_cost),
        }
    )


@api_view(["GET"])
def last_order(request):
    """
    Получение последнего заказа пользователя для отображения в профиле
    """
    if not request.user.is_authenticated:
        return Response(
            {"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED
        )

    try:
        # Получаем последний заказ пользователя
        last_order = (
            Order.objects.filter(user=request.user, is_active=True)
            .prefetch_related("products__product")
            .order_by("-createdAt")
            .first()
        )

        if not last_order:
            return Response({"order": None})

        # Сериализуем заказ
        serializer = OrderSerializer(last_order)
        return Response({"order": serializer.data})

    except Exception:
        return Response(
            {"error": "Ошибка при получении последнего заказа"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
