from rest_framework import serializers

from catalog.serializers import ProductShortSerializer
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductShortSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ("product", "price", "count")


class OrderSerializer(serializers.ModelSerializer):
    products = OrderItemSerializer(many=True, read_only=True)
    paymentError = serializers.SerializerMethodField()
    deliveryCost = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "createdAt",
            "fullName",
            "email",
            "phone",
            "deliveryType",
            "paymentType",
            "totalCost",
            "status",
            "city",
            "address",
            "comment",
            "products",
            "paymentError",
            "deliveryCost",
        )
        read_only_fields = (
            "id",
            "createdAt",
            "status",
            "totalCost",
            "paymentError",
            "deliveryCost",
        )

    def get_paymentError(self, obj):
        """Получаем ошибку оплаты только если последний платёж неудачный"""
        # Используем select_related для оптимизации если payments не prefetch_related
        last_payment = obj.payments.select_related().order_by("-created_at").first()
        if last_payment and last_payment.status == "failed":
            return last_payment.error_message
        return None

    def get_deliveryCost(self, obj):
        """Получаем стоимость доставки"""
        return float(obj.calculate_delivery_cost())
