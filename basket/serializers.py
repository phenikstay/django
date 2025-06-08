from rest_framework import serializers

from catalog.models import Product
from catalog.serializers import ProductShortSerializer
from .models import BasketItem


class BasketItemSerializer(serializers.ModelSerializer):
    """
    Сериализатор для отдельного элемента корзины
    """
    product = ProductShortSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
        source='product',
        write_only=True
    )

    class Meta:
        model = BasketItem
        fields = ('id', 'product', 'product_id', 'count')

    def to_representation(self, instance):
        """
        Форматирует данные в соответствии с API контрактом
        """
        representation = super().to_representation(instance)
        product_data = representation.pop('product')
        product_data['count'] = representation['count']
        return product_data


class BasketSerializer(serializers.Serializer):
    """
    Сериализатор для списка элементов корзины (для анонимных пользователей)
    """
    id = serializers.IntegerField()
    count = serializers.IntegerField(min_value=1)

    def to_representation(self, instance):
        """
        Преобразует элемент корзины в формат API контракта
        """
        product = Product.objects.get(id=instance['id'])
        product_data = ProductShortSerializer(product).data
        product_data['count'] = instance['count']
        return product_data
