from django.contrib import admin

from .models import BasketItem


@admin.register(BasketItem)
class BasketItemAdmin(admin.ModelAdmin):
    """
    Административный интерфейс для работы с элементами корзины
    """
    list_display = ('get_id_display', 'get_user_display', 'get_product_display', 'get_count_display', 'get_added_at_display', 'get_total_price_display')
    list_filter = ('added_at', 'user')
    search_fields = ('user__username', 'product__title')
    readonly_fields = ('added_at', 'get_total_price_display')
    raw_id_fields = ('user', 'product')

    def get_id_display(self, obj):
        return obj.id
    get_id_display.short_description = 'ID'

    def get_user_display(self, obj):
        return obj.user.username
    get_user_display.short_description = 'Пользователь'

    def get_product_display(self, obj):
        return obj.product.title
    get_product_display.short_description = 'Товар'

    def get_count_display(self, obj):
        return f"{obj.count} шт."
    get_count_display.short_description = 'Количество'

    def get_added_at_display(self, obj):
        return obj.added_at.strftime('%d.%m.%Y %H:%M')
    get_added_at_display.short_description = 'Дата добавления'

    def get_total_price_display(self, obj):
        """
        Отображает общую стоимость товара (кол-во * цена)
        """
        return f"{obj.total_price}$"
    get_total_price_display.short_description = 'Общая стоимость'
