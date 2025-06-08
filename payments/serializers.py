from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "order",
            "payment_type",
            "number",
            "name",
            "created_at",
            "status",
            "error_message",
        )
        read_only_fields = ("id", "order", "created_at", "status", "error_message")


class PaymentCreateSerializer(serializers.Serializer):
    number = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    month = serializers.CharField(max_length=2, required=False, allow_blank=True)
    year = serializers.CharField(max_length=4, required=False, allow_blank=True)
    code = serializers.CharField(max_length=3, required=False, allow_blank=True)
    payment_type = serializers.CharField(max_length=10, default="card")

    def validate_number(self, value):
        """
        Валидация номера карты согласно ТЗ:
        - Только цифры
        - Не длиннее 8 цифр
        - Четное число
        """
        # Проверяем, что номер содержит только цифры
        if not value.isdigit():
            raise serializers.ValidationError(
                "Номер карты должен содержать только цифры"
            )

        # Проверяем длину
        if len(value) > 8:
            raise serializers.ValidationError(
                "Номер карты должен быть не длиннее 8 цифр"
            )

        # Проверяем четность
        if int(value) % 2 != 0:
            raise serializers.ValidationError("Номер карты должен быть четным")

        return value


class RandomPaymentCreateSerializer(serializers.Serializer):
    number = serializers.CharField(max_length=8)  # Номер случайного счёта

    def validate_number(self, value):
        """
        Валидация номера счёта согласно ТЗ:
        - Только цифры
        - Не длиннее 8 цифр
        - Четное число
        """
        # Проверяем, что номер содержит только цифры
        if not value.isdigit():
            raise serializers.ValidationError(
                "Номер счёта должен содержать только цифры"
            )

        # Проверяем длину
        if len(value) > 8:
            raise serializers.ValidationError(
                "Номер счёта должен быть не длиннее 8 цифр"
            )

        # Проверяем четность
        if int(value) % 2 != 0:
            raise serializers.ValidationError("Номер счёта должен быть четным")

        return value
