"""
Модуль обработки платежей интернет-магазина
"""

import json
import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from orders.models import Order
from .models import Payment
from .serializers import PaymentCreateSerializer, RandomPaymentCreateSerializer

logger = logging.getLogger(__name__)

# Создаем thread pool для обработки платежей с ограниченным количеством потоков
# Используем максимум 5 потоков для предотвращения перегрузки системы
payment_executor = ThreadPoolExecutor(
    max_workers=5, thread_name_prefix="payment_processor"
)


def safe_thread_execution(func):
    """
    Декоратор для безопасного выполнения функций в потоках
    Обеспечивает proper error handling и логирование
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(
                f"Ошибка в потоке {threading.current_thread().name}: {str(e)}",
                exc_info=True,
            )
            # Дополнительно логируем детали для диагностики
            if args:
                logger.error(f"Аргументы функции: {args}")
            if kwargs:
                logger.error(f"Ключевые аргументы функции: {kwargs}")

    return wrapper


@safe_thread_execution
def process_payment(payment_id):
    """
    Фиктивная обработка платежа с улучшенной обработкой ошибок
    """
    thread_name = threading.current_thread().name
    logger.info(f"[{thread_name}] Начинаем обработку платежа ID={payment_id}")

    try:
        # Имитируем задержку обработки платежа
        time.sleep(5)

        # Проверяем, что платеж все еще существует и в правильном статусе
        try:
            payment = Payment.objects.get(id=payment_id)
        except ObjectDoesNotExist:
            logger.error(
                f"[{thread_name}] Платеж с ID={payment_id} не найден при обработке"
            )
            return

        # Проверяем, что платеж еще в статусе pending
        if payment.status != "pending":
            logger.warning(
                f"[{thread_name}] Платеж ID={payment_id} уже обработан, статус: {payment.status}"
            )
            return

        number = payment.number
        logger.info(
            f"[{thread_name}] Обрабатываем платеж ID={payment_id}, номер: {number}"
        )

        # Проверка по заданной логике:
        # Если номер чётный и не заканчивается на ноль - успех
        # Иначе - случайная ошибка
        if int(number) % 2 == 0 and not number.endswith("0"):
            payment.status = "success"
            logger.info(f"[{thread_name}] Платеж ID={payment_id} успешно обработан")
        else:
            payment.status = "failed"
            errors = [
                "Недостаточно средств",
                "Карта заблокирована",
                "Превышен лимит операций",
                "Подозрительная операция",
                "Ошибка сервера платежной системы",
            ]
            payment.error_message = random.choice(errors)
            logger.info(
                f"[{thread_name}] Платеж ID={payment_id} отклонен: {payment.error_message}"
            )

        payment.processed_at = timezone.now()
        payment.save()

        # Обновляем статус заказа только в случае успешного платежа
        if payment.status == "success":
            try:
                order = payment.order
                if order.status in [
                    "accepted",
                    "pending",
                ]:  # Дополнительная проверка статуса заказа
                    order.status = "processing"
                    order.save()
                    logger.info(
                        f"[{thread_name}] Статус заказа #{order.id} изменен на 'processing'"
                    )
                else:
                    logger.warning(
                        f"[{thread_name}] Заказ #{order.id} в неожиданном статусе: {order.status}"
                    )
            except Exception as e:
                logger.error(
                    f"[{thread_name}] Ошибка при обновлении статуса заказа для платежа ID={payment_id}: {str(e)}"
                )

        logger.info(
            f"[{thread_name}] Завершена обработка платежа ID={payment_id}, статус: {payment.status}"
        )

    except Exception as e:
        # Обновляем статус платежа как failed в случае любой критической ошибки
        logger.error(
            f"[{thread_name}] Критическая ошибка при обработке платежа ID={payment_id}: {str(e)}",
            exc_info=True,
        )
        try:
            payment = Payment.objects.get(id=payment_id)
            if payment.status == "pending":  # Обновляем только если все еще pending
                payment.status = "failed"
                payment.error_message = "Техническая ошибка при обработке платежа"
                payment.processed_at = timezone.now()
                payment.save()
                logger.info(
                    f"[{thread_name}] Платеж ID={payment_id} помечен как failed из-за технической ошибки"
                )
        except Exception as save_error:
            logger.error(
                f"[{thread_name}] Не удалось обновить статус платежа при ошибке: {str(save_error)}"
            )


def submit_payment_for_processing(payment_id):
    """
    Отправляет платеж на обработку в thread pool
    Возвращает Future объект для отслеживания выполнения (опционально)
    """
    try:
        future = payment_executor.submit(process_payment, payment_id)
        logger.info(f"Платеж ID={payment_id} отправлен на обработку в thread pool")
        return future
    except Exception as e:
        logger.error(
            f"Ошибка при отправке платежа ID={payment_id} на обработку: {str(e)}"
        )
        # В случае ошибки пытаемся пометить платеж как failed
        try:
            payment = Payment.objects.get(id=payment_id)
            if payment.status == "pending":
                payment.status = "failed"
                payment.error_message = "Ошибка системы обработки платежей"
                payment.processed_at = timezone.now()
                payment.save()
        except Exception:
            logger.error(
                f"Не удалось обновить статус платежа ID={payment_id} после ошибки отправки"
            )
        return None


@api_view(["POST"])
def payment(request, order_id):
    """
    Создание платежа картой
    """
    # Проверяем, что заказ существует и принадлежит текущему пользователю
    if request.user.is_authenticated:
        order = get_object_or_404(Order, pk=order_id, user=request.user, is_active=True)
    else:
        order = get_object_or_404(Order, pk=order_id, user=None, is_active=True)

    # Проверяем статус последнего платежа
    last_payment = order.payments.order_by("-created_at").first()

    # Разрешаем оплату только если:
    # - заказ в статусе accepted/pending ИЛИ
    # - последний платёж был неуспешным (failed)
    if order.status not in ["accepted", "pending"]:
        if last_payment and last_payment.status == "success":
            return Response(
                {"error": "Заказ уже оплачен"}, status=status.HTTP_400_BAD_REQUEST
            )

    # Получаем данные платежа
    data = json.loads(request.body)
    serializer = PaymentCreateSerializer(data=data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Получаем валидированный номер карты (валидация выполняется в сериализаторе)
    number = serializer.validated_data["number"]

    # Создаем платеж
    payment = Payment.objects.create(
        order=order,
        payment_type="card",
        number=number,
        name=serializer.validated_data.get("name", ""),
        month=serializer.validated_data.get("month", ""),
        year=serializer.validated_data.get("year", ""),
        code=serializer.validated_data.get("code", ""),
        status="pending",
    )

    # Запускаем асинхронную обработку платежа через thread pool
    submit_payment_for_processing(payment.id)

    return Response(status=status.HTTP_200_OK)


@api_view(["POST"])
def payment_someone(request, order_id):
    """
    Создание платежа со случайного чужого счёта
    """
    # Проверяем, что заказ существует и принадлежит текущему пользователю
    if request.user.is_authenticated:
        order = get_object_or_404(Order, pk=order_id, user=request.user, is_active=True)
    else:
        order = get_object_or_404(Order, pk=order_id, user=None, is_active=True)

    # Проверяем статус последнего платежа
    last_payment = order.payments.order_by("-created_at").first()

    # Разрешаем оплату только если:
    # - заказ в статусе accepted/pending ИЛИ
    # - последний платёж был неуспешным (failed)
    if order.status not in ["accepted", "pending"]:
        if last_payment and last_payment.status == "success":
            return Response(
                {"error": "Заказ уже оплачен"}, status=status.HTTP_400_BAD_REQUEST
            )

    # Получаем данные платежа
    data = json.loads(request.body)
    serializer = RandomPaymentCreateSerializer(data=data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Получаем валидированный номер счёта (валидация выполняется в сериализаторе)
    number = serializer.validated_data["number"]

    # Создаем платеж
    payment = Payment.objects.create(
        order=order, payment_type="someone", number=number, status="pending"
    )

    # Запускаем асинхронную обработку платежа через thread pool
    submit_payment_for_processing(payment.id)

    return Response(status=status.HTTP_200_OK)


@api_view(["GET"])
def generate_random_account(request):
    """
    Генерация случайного номера счёта согласно ТЗ
    """
    # Генерируем случайное четное 8-значное число согласно ТЗ
    # ВКЛЮЧАЯ числа заканчивающиеся на 0 (они должны приводить к ошибке платежа)
    min_num = 10000000  # минимальное 8-значное число
    max_num = 99999998  # максимальное 8-значное четное число

    # Генерируем случайное число в диапазоне
    number = random.randint(min_num, max_num)

    # Делаем число четным
    if number % 2 != 0:
        number = number - 1

    return Response({"number": str(number)})


@api_view(["GET"])
def payment_status(request, order_id):
    """
    Проверка статуса платежа для заказа
    """
    # Проверяем, что заказ существует и принадлежит текущему пользователю
    if request.user.is_authenticated:
        order = get_object_or_404(Order, pk=order_id, user=request.user, is_active=True)
    else:
        order = get_object_or_404(Order, pk=order_id, user=None, is_active=True)

    # Получаем последний платеж
    last_payment = order.payments.order_by("-created_at").first()

    if not last_payment:
        return Response({"status": "no_payment"})

    return Response(
        {
            "status": last_payment.status,
            "error_message": (
                last_payment.error_message if last_payment.status == "failed" else None
            ),
        }
    )
