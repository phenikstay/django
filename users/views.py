import json
import logging

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from basket.models import BasketItem
from catalog.models import Product
from orders.models import Order
from users.models import Profile

logger = logging.getLogger(__name__)


def transfer_session_basket_to_db(request, user, session_basket):
    """
    Переносит товары из корзины сессии в базу данных для авторизованного пользователя

    Args:
        request: HTTP запрос (для очистки сессии)
        user: Пользователь, которому принадлежит корзина
        session_basket: Список товаров из сессии
    """
    if not session_basket:
        return

    try:
        for item in session_basket:
            try:
                product = Product.objects.get(id=item["id"], is_active=True)
                basket_item, created = BasketItem.objects.get_or_create(
                    user=user,
                    product=product,
                    defaults={"count": item["count"]},
                )
                if not created:
                    basket_item.count += item["count"]
                    basket_item.save()
            except ObjectDoesNotExist:
                logger.warning(
                    f"Товар с ID={item['id']} не найден при переносе из сессии в БД"
                )
            except Exception as e:
                logger.error(f"Ошибка при переносе товара из сессии: {str(e)}")

        # Очищаем корзину в сессии
        request.session["basket"] = []
        request.session.modified = True
    except Exception as e:
        logger.error(f"Общая ошибка при переносе товаров из сессии: {str(e)}")


def attach_recent_orders_to_user(user, user_full_name=None):
    """
    Привязывает незавершенные заказы, созданные за последние 24 часа, к пользователю

    Args:
        user: Пользователь, к которому привязать заказы
        user_full_name: Полное имя пользователя (опционально, для sign_up)
    """
    try:
        from django.utils import timezone
        from datetime import timedelta

        recent_orders = (
            Order.objects.filter(
                user=None,
                is_active=True,
                status="pending",
                createdAt__gte=timezone.now() - timedelta(hours=24),
            )
            .select_related("user")
            .order_by("-createdAt")
        )

        # Привязываем самый последний заказ к пользователю
        if recent_orders.exists():
            latest_order = recent_orders.first()
            latest_order.user = user

            # Заполняем данные профиля
            if user_full_name:
                # Для sign_up используем переданное имя
                latest_order.fullName = user_full_name
            elif not latest_order.fullName and hasattr(user, "profile"):
                # Для sign_in берем из профиля, если заказ пустой
                try:
                    profile = user.profile
                    latest_order.fullName = profile.fullName or ""
                    latest_order.phone = profile.phone or ""
                except ObjectDoesNotExist as e:
                    logger.warning(
                        f"Профиль пользователя {user.username} не найден при привязке заказа: {str(e)}"
                    )

            latest_order.email = user.email or ""
            latest_order.save()

            action = "новому пользователю" if user_full_name else "пользователю"
            logger.info(f"Привязан заказ #{latest_order.id} к {action} {user.username}")
    except Exception as e:
        logger.error(f"Ошибка при привязке заказа к пользователю: {str(e)}")


@api_view(["POST"])
def sign_in(request):
    try:
        # Пробуем получить данные из query_params
        username = request.query_params.get("username")
        password = request.query_params.get("password")

        # Если данных нет в query_params, пробуем получить из тела запроса
        if not username or not password:
            try:
                data = json.loads(request.body)
                username = data.get("username", username)
                password = data.get("password", password)
            except Exception as e:
                logger.debug(f"Ошибка парсинга JSON при входе: {str(e)}")

        if not username or not password:
            return Response(
                {"success": False, "error": "Username and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Запоминаем корзину из сессии перед авторизацией
            session_basket = request.session.get("basket", [])

            # Авторизуем пользователя
            login(request, user)

            # После авторизации привязываем незавершенные заказы к пользователю
            attach_recent_orders_to_user(user)

            # После авторизации переносим товары из сессии в базу данных
            transfer_session_basket_to_db(request, user, session_basket)

            # Принудительно сохраняем сессию
            request.session.save()

            response = Response(
                {
                    "success": True,
                    "username": username,
                    "session_id": request.session.session_key,
                    "authenticated": True,
                },
                status=status.HTTP_200_OK,
            )

            # Явно добавляем cookie сессии в ответ
            response.set_cookie(
                settings.SESSION_COOKIE_NAME,
                request.session.session_key,
                max_age=settings.SESSION_COOKIE_AGE,
                path=settings.SESSION_COOKIE_PATH,
                domain=settings.SESSION_COOKIE_DOMAIN,
                secure=settings.SESSION_COOKIE_SECURE,
                httponly=settings.SESSION_COOKIE_HTTPONLY,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )

            return response
        else:
            return Response(
                {"success": False, "error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
    except Exception as e:
        logger.error(f"Ошибка при входе в систему: {str(e)}")
        return Response(
            {"success": False, "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
def sign_up(request):
    # Пробуем получить данные из query_params
    name = request.query_params.get("name")
    username = request.query_params.get("username")
    password = request.query_params.get("password")
    email = request.query_params.get("email", "")
    phone = request.query_params.get("phone", "")

    # Если данных нет в query_params, пробуем получить из тела запроса
    if not name or not username or not password:
        try:
            data = json.loads(request.body)
            name = data.get("name", name)
            username = data.get("username", username)
            password = data.get("password", password)
            email = data.get("email", email)
            phone = data.get("phone", phone)
        except Exception as e:
            logger.debug(f"Ошибка парсинга JSON при регистрации: {str(e)}")

    if not name or not username or not password:
        return Response(
            {"error": "Name, username and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Проверяем уникальность username
    if User.objects.filter(username=username).exists():
        return Response(
            {"error": "Пользователь с таким именем уже существует"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Проверяем уникальность email если он указан
    if email and User.objects.filter(email=email).exists():
        return Response(
            {"error": "Пользователь с таким email уже существует"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Проверяем уникальность телефона если он указан
    if phone and Profile.objects.filter(phone=phone).exists():
        return Response(
            {"error": "Пользователь с таким телефоном уже существует"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Запоминаем корзину из сессии перед созданием пользователя
        session_basket = request.session.get("basket", [])

        # Создаем пользователя
        user = User.objects.create_user(
            username=username, password=password, email=email
        )

        # Обновляем профиль
        profile = user.profile
        profile.fullName = name
        if phone:
            profile.phone = phone
        profile.save()

        # Авторизуем пользователя
        login(request, user)

        # После регистрации также привязываем незавершенные заказы
        attach_recent_orders_to_user(user, name)

        # После авторизации переносим товары из сессии в базу данных
        transfer_session_basket_to_db(request, user, session_basket)

        return Response(status=status.HTTP_200_OK)
    except IntegrityError as e:
        error_message = "Ошибка уникальности данных"
        if "email" in str(e).lower():
            error_message = "Пользователь с таким email уже существует"
        elif "phone" in str(e).lower():
            error_message = "Пользователь с таким телефоном уже существует"
        elif "username" in str(e).lower():
            error_message = "Пользователь с таким именем уже существует"

        return Response({"error": error_message}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Ошибка при регистрации: {str(e)}")
        return Response(
            {"error": "Внутренняя ошибка сервера"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
def sign_out(request):
    try:
        logout(request)
        return Response({"success": True}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Ошибка при выходе: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET", "POST"])
def profile(request):
    # Проверяем, авторизован ли пользователь
    if not request.user.is_authenticated:
        return Response(
            {"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED
        )

    user = request.user

    # Проверяем, есть ли профиль у пользователя
    try:
        profile = user.profile
    except ObjectDoesNotExist:
        # Создаем профиль, если его нет
        profile = Profile.objects.create(user=user)

    if request.method == "GET":
        # Обработка аватара с учетом значения по умолчанию
        avatar_url = None
        if profile.avatar:
            avatar_url = profile.avatar.url

        data = {
            "fullName": profile.fullName or "",
            "email": user.email or "",
            "phone": profile.phone or "",
            "avatar": {"src": avatar_url, "alt": profile.fullName or ""},
        }
        return Response(data)

    elif request.method == "POST":
        try:
            data = json.loads(request.body)

            new_email = data.get("email", user.email)
            new_phone = data.get("phone", profile.phone)

            # Проверяем уникальность email если он изменился
            if (
                new_email != user.email
                and User.objects.filter(email=new_email).exists()
            ):
                return Response(
                    {"error": "Пользователь с таким email уже существует"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Проверяем уникальность телефона если он изменился
            if (
                new_phone != profile.phone
                and new_phone
                and Profile.objects.filter(phone=new_phone).exclude(user=user).exists()
            ):
                return Response(
                    {"error": "Пользователь с таким телефоном уже существует"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Обновляем данные профиля
            profile.fullName = data.get("fullName", profile.fullName)
            user.email = new_email
            profile.phone = new_phone if new_phone else None

            user.save()
            profile.save()

            # Возвращаем обновленные данные
            # Обработка аватара с учетом значения по умолчанию
            avatar_url = None
            if profile.avatar:
                avatar_url = profile.avatar.url

            response_data = {
                "fullName": profile.fullName or "",
                "email": user.email or "",
                "phone": profile.phone or "",
                "avatar": {"src": avatar_url, "alt": profile.fullName or ""},
            }
            return Response(response_data)
        except IntegrityError as e:
            error_message = "Ошибка уникальности данных"
            if "email" in str(e).lower():
                error_message = "Пользователь с таким email уже существует"
            elif "phone" in str(e).lower():
                error_message = "Пользователь с таким телефоном уже существует"

            return Response(
                {"error": error_message}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Ошибка при обновлении профиля: {str(e)}")
            return Response(
                {"error": "Внутренняя ошибка сервера"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # Если метод не GET и не POST, возвращаем ошибку
    return Response(
        {"error": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


@api_view(["POST"])
def update_password(request):
    # Проверяем, авторизован ли пользователь
    if not request.user.is_authenticated:
        return Response(
            {"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED
        )

    try:
        data = json.loads(request.body)
        current_password = data.get("currentPassword", "")
        new_password = data.get("newPassword", "")

        if not current_password or not new_password:
            return Response(
                {"error": "Current password and new password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверяем текущий пароль
        user = authenticate(username=request.user.username, password=current_password)
        if user is None:
            return Response(
                {"error": "Current password is incorrect"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Обновляем пароль
        user.set_password(new_password)
        user.save()

        # Переавторизуем пользователя с новым паролем
        login(request, user)

        return Response(
            {"success": True, "message": "Password updated successfully"},
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response(
            {"error": f"Error updating password: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
def update_avatar(request):
    # Проверяем, авторизован ли пользователь
    if not request.user.is_authenticated:
        return Response(
            {"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED
        )

    try:
        if "avatar" not in request.FILES:
            return Response(
                {"error": "No avatar file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        avatar_file = request.FILES["avatar"]

        # Проверяем размер файла (не более 2 МБ)
        max_size = 2 * 1024 * 1024  # 2 МБ в байтах
        if avatar_file.size > max_size:
            return Response(
                {"error": "Размер файла не должен превышать 2 МБ"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверяем тип файла (только изображения)
        allowed_types = [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/gif",
            "image/webp",
        ]
        if avatar_file.content_type not in allowed_types:
            return Response(
                {"error": "Разрешены только изображения (JPEG, PNG, GIF, WebP)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверяем, есть ли профиль у пользователя
        try:
            profile = request.user.profile
        except ObjectDoesNotExist:
            # Создаем профиль, если его нет
            profile = Profile.objects.create(user=request.user)

        # Сохраняем старый аватар для удаления
        old_avatar = profile.avatar

        # Обновляем аватар
        profile.avatar = avatar_file
        profile.save()

        # Удаляем старый файл аватара, если он существует и не является дефолтным
        if old_avatar and old_avatar.name != "placeholder.jpg":
            try:
                old_avatar.delete(save=False)
            except Exception as e:
                logger.debug(
                    f"Не удалось удалить старый аватар {old_avatar.name}: {str(e)}"
                )  # Игнорируем ошибки удаления старого файла

        # Возвращаем информацию об обновленном аватаре
        # Обработка аватара с учетом значения по умолчанию
        avatar_url = None
        if profile.avatar:
            avatar_url = profile.avatar.url

        return Response(
            {
                "success": True,
                "avatar": {"src": avatar_url, "alt": profile.fullName or ""},
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response(
            {"error": f"Error updating avatar: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
