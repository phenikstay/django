import json
import logging

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.decorators import api_view
from rest_framework.response import Response

from catalog.models import Product
from catalog.serializers import ProductShortSerializer
from .models import BasketItem

logger = logging.getLogger(__name__)


def check_user_authentication(request):
    """
    Проверяет аутентификацию пользователя унифицированным способом

    Returns:
        bool: True если пользователь аутентифицирован, False иначе
    """
    # Стандартная проверка Django
    if hasattr(request.user, "is_authenticated") and request.user.is_authenticated:
        return True

    # Дополнительная проверка через сессию для совместимости
    if request.session.get("_auth_user_id"):
        return True

    return False


def get_authenticated_user(request):
    """
    Получает аутентифицированного пользователя из запроса

    Returns:
        tuple: (user_object, error_response) где error_response=None если успешно
    """
    # Сначала проверяем стандартный способ Django
    if hasattr(request.user, "is_authenticated") and request.user.is_authenticated:
        return request.user, None

    # Если стандартный способ не сработал, пробуем через сессию
    user_id = request.session.get("_auth_user_id")
    if not user_id:
        logger.error("[BASKET] Авторизованный пользователь, но ID не найден в сессии")
        return None, Response({"error": "User ID not found in session"}, status=400)

    try:
        user = User.objects.get(id=user_id)
        return user, None
    except ObjectDoesNotExist:
        logger.error(
            f"[BASKET] Пользователь с ID={user_id} из сессии не найден в базе данных"
        )
        return None, Response({"error": "User not found"}, status=404)


def get_user_basket_data(user):
    """
    Получает данные корзины для аутентифицированного пользователя

    Returns:
        list: Список товаров в корзине с количеством
    """
    basket_items = (
        BasketItem.objects.filter(user=user).select_related("product").order_by("id")
    )
    result = []

    for item in basket_items:
        if item.product.is_active:
            product_data = ProductShortSerializer(item.product).data
            product_data["count"] = item.count
            result.append(product_data)

    return result


@api_view(["GET", "POST", "DELETE"])
def basket(request):
    """
    Операции с корзиной: получение, добавление, удаление товаров
    """
    # Унифицированная проверка аутентификации
    is_authenticated = check_user_authentication(request)

    # GET: Получение корзины
    if request.method == "GET":
        try:
            # Для авторизованного пользователя - получаем из БД
            if is_authenticated:
                user, error_response = get_authenticated_user(request)
                if error_response:
                    return error_response

                # Получаем корзину из БД с оптимизацией запросов
                result = get_user_basket_data(user)

                # Возвращаем массив товаров для стабильного порядка
                return Response(result)

            # Если пользователь не авторизован - используем сессии
            else:
                session_basket = request.session.get("basket", [])
                result = []
                for item in session_basket:
                    try:
                        product = Product.objects.get(id=item["id"], is_active=True)
                        product_data = ProductShortSerializer(product).data
                        product_data["count"] = item["count"]
                        result.append(product_data)
                    except ObjectDoesNotExist as e:
                        logger.warning(
                            f"[BASKET][GET] Товар с ID={item['id']} из сессии не найден: {str(e)}"
                        )

                return Response(result)
        except Exception as e:
            logger.error(f"[BASKET][GET] Ошибка: {str(e)}")
            return Response({"error": str(e)}, status=400)

    # POST: Добавление товара в корзину
    elif request.method == "POST":
        try:
            # Попытаемся получить ID и количество из разных источников
            product_id = None
            count = 1

            # Сначала проверяем query_params
            if "id" in request.query_params:
                product_id = int(request.query_params.get("id"))
                count = int(request.query_params.get("count", 1))

            # Затем проверяем тело запроса (в формате JSON)
            elif request.body:
                try:
                    data = json.loads(request.body)
                    product_id = int(data.get("id"))
                    count = int(data.get("count", 1))
                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    logger.error(
                        f"[BASKET][POST] Ошибка парсинга тела запроса: {str(e)}"
                    )
                    # Пытаемся получить данные из других источников
                    if request.POST:
                        data = request.POST.dict()
                        product_id = int(data.get("id"))
                        count = int(data.get("count", 1))

            # Также проверяем request.data (может быть заполнено DRF)
            elif hasattr(request, "data") and request.data:
                try:
                    product_id = int(request.data.get("id"))
                    count = int(request.data.get("count", 1))
                except (TypeError, ValueError) as e:
                    logger.error(
                        f"[BASKET][POST] Ошибка получения данных из request.data: {str(e)}"
                    )

            # Если ID продукта не найден, возвращаем ошибку
            if product_id is None:
                logger.error("[BASKET][POST] Отсутствует ID товара")
                return Response({"error": "Product ID is required"}, status=400)

            # Проверяем существование товара
            try:
                product = Product.objects.get(id=product_id, is_active=True)
            except ObjectDoesNotExist:
                logger.error(
                    f"[BASKET][POST] Товар с ID={product_id} не найден или неактивен"
                )
                return Response({"error": "Product not found"}, status=404)

            # Для авторизованного пользователя - работа с БД
            if is_authenticated:
                user, error_response = get_authenticated_user(request)
                if error_response:
                    return error_response

                # Ищем товар в корзине пользователя
                basket_item, created = BasketItem.objects.get_or_create(
                    user=user, product=product, defaults={"count": count}
                )

                # Если товар уже есть - увеличиваем количество
                if not created:
                    basket_item.count += count
                    basket_item.save()

                # Получаем обновленную корзину из БД с оптимизацией запросов
                result = get_user_basket_data(user)

                # Возвращаем массив товаров для стабильного порядка
                return Response(result)

            # Для анонимного пользователя - работа с сессией
            else:
                # Получаем или создаем корзину в сессии
                basket = request.session.get("basket", [])

                # Проверяем, есть ли такой товар в корзине
                found = False
                for item in basket:
                    if item["id"] == product_id:
                        item["count"] += count
                        found = True
                        break

                # Если товара нет в корзине, добавляем его
                if not found:
                    basket.append({"id": product_id, "count": count})

                # Сохраняем корзину в сессии
                request.session["basket"] = basket
                request.session.modified = True

                # Подготавливаем ответ - формируем список товаров с подробной информацией
                result = []
                for item in basket:
                    try:
                        product = Product.objects.get(id=item["id"], is_active=True)
                        product_data = ProductShortSerializer(product).data
                        product_data["count"] = item["count"]
                        result.append(product_data)
                    except ObjectDoesNotExist as e:
                        logger.warning(
                            f"[BASKET][POST] Товар с ID={item['id']} из сессии не найден: {str(e)}"
                        )

                return Response(result)

        except ValueError as e:
            logger.error(f"[BASKET][POST] Ошибка значения: {str(e)}")
            return Response({"error": str(e)}, status=400)
        except Exception as e:
            logger.error(f"[BASKET][POST] Общая ошибка: {str(e)}")
            return Response({"error": str(e)}, status=400)

    # DELETE: Удаление товара из корзины
    elif request.method == "DELETE":
        try:
            # Попытаемся получить ID и количество из разных источников
            product_id = None
            count = 1

            # Сначала проверяем query_params (например, DELETE /api/basket?id=123&count=2)
            if "id" in request.query_params:
                product_id = int(request.query_params.get("id"))
                count = int(request.query_params.get("count", 1))

            # Затем проверяем данные из тела запроса (JSON)
            if (
                product_id is None
                and hasattr(request, "data")
                and isinstance(request.data, dict)
            ):
                if "id" in request.data:
                    product_id = int(request.data.get("id"))
                    count = int(request.data.get("count", 1))

            # Если JSON не распарсился, пробуем вручную
            if product_id is None and request.body:
                try:
                    data = json.loads(request.body)
                    if "id" in data:
                        product_id = int(data.get("id"))
                        count = int(data.get("count", 1))
                except Exception as e:
                    logger.warning(
                        f"[BASKET][DELETE] Ошибка парсинга JSON данных: {str(e)}"
                    )

            # Проверяем, что ID товара найден
            if product_id is None:
                logger.error("[BASKET][DELETE] ID товара не указан")
                return Response({"error": "Product ID is required"}, status=400)

            # Проверяем существование товара
            try:
                product = Product.objects.get(id=product_id)
            except ObjectDoesNotExist:
                logger.error(f"[BASKET][DELETE] Товар с ID={product_id} не найден")
                return Response({"error": "Product not found"}, status=404)

            # Для авторизованного пользователя - работаем с БД
            if is_authenticated:
                user, error_response = get_authenticated_user(request)
                if error_response:
                    return error_response

                # Работаем с корзиной в БД
                try:
                    basket_item = BasketItem.objects.get(user=user, product=product)

                    # Уменьшаем количество или удаляем полностью
                    if count >= basket_item.count:
                        basket_item.delete()
                    else:
                        basket_item.count -= count
                        basket_item.save()

                    # Получаем обновленную корзину с оптимизацией запросов
                    result = get_user_basket_data(user)

                    return Response(result)

                except ObjectDoesNotExist:
                    logger.warning(
                        f"[BASKET][DELETE] Товар {product.title} не найден в корзине пользователя {user.username}"
                    )
                    return Response({"error": "Item not in basket"}, status=404)

            # Для анонимного пользователя - работа с сессией
            else:
                # Получаем корзину из сессии
                basket = request.session.get("basket", [])

                # Ищем товар в корзине
                found = False
                updated_basket = []
                for item in basket:
                    if item["id"] == product_id:
                        found = True
                        # Уменьшаем количество товара
                        if item["count"] <= count:
                            # Полностью удаляем товар из корзины
                            logger.debug(
                                f"[BASKET][DELETE] Полностью удаляем товар с ID={product_id} из корзины"
                            )
                        else:
                            # Уменьшаем количество
                            item["count"] -= count
                            updated_basket.append(item)
                    else:
                        updated_basket.append(item)

                # Если товар не найден, возвращаем ошибку
                if not found:
                    logger.warning(
                        f"[BASKET][DELETE] Товар с ID={product_id} не найден в корзине"
                    )
                    return Response({"error": "Item not in basket"}, status=404)

                # Сохраняем обновленную корзину в сессии
                request.session["basket"] = updated_basket
                request.session.modified = True

                # Подготавливаем ответ - формируем список товаров с подробной информацией
                result = []
                for item in updated_basket:
                    try:
                        product = Product.objects.get(id=item["id"], is_active=True)
                        product_data = ProductShortSerializer(product).data
                        product_data["count"] = item["count"]
                        result.append(product_data)
                    except ObjectDoesNotExist as e:
                        logger.warning(
                            f"[BASKET][DELETE] Товар с ID={item['id']} из сессии не найден: {str(e)}"
                        )

                return Response(result)

        except ValueError as e:
            logger.error(f"[BASKET][DELETE] Ошибка значения: {str(e)}")
            return Response({"error": str(e)}, status=400)
        except Exception as e:
            logger.error(f"[BASKET][DELETE] Общая ошибка: {str(e)}")
            return Response({"error": str(e)}, status=400)

    # Если метод не GET, не POST и не DELETE, возвращаем ошибку
    return Response({"error": "Method not allowed"}, status=405)
