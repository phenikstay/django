from django.contrib import admin

from .models import Order, OrderItem, DeliverySettings


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "price", "count", "total_price")
    verbose_name = "Товар в заказе"
    verbose_name_plural = "Товары в заказе"


class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "get_id_display",
        "get_full_name_display",
        "get_email_display",
        "get_created_at_display",
        "get_status_display_ru",
        "get_total_cost_display",
        "get_delivery_type_display_ru",
        "get_payment_type_display_ru",
        "get_active_display",
    )
    list_filter = ("status", "deliveryType", "paymentType", "is_active")
    search_fields = ("fullName", "email", "city", "address")
    readonly_fields = ("user", "createdAt", "totalCost")
    inlines = [OrderItemInline]

    def get_id_display(self, obj):
        return f"№{obj.id}"

    get_id_display.short_description = "Номер заказа"

    def get_full_name_display(self, obj):
        return obj.fullName

    get_full_name_display.short_description = "ФИО"

    def get_email_display(self, obj):
        return obj.email

    get_email_display.short_description = "Email"

    def get_created_at_display(self, obj):
        return obj.createdAt.strftime("%d.%m.%Y %H:%M")

    get_created_at_display.short_description = "Дата создания"

    def get_status_display_ru(self, obj):
        """Отображение статуса заказа на русском языке"""
        statuses = {
            "pending": "Ожидает обработки",
            "processing": "Обрабатывается",
            "accepted": "Принят",
            "completed": "Выполнен",
            "canceled": "Отменён",
        }
        return statuses.get(obj.status, obj.status)

    get_status_display_ru.short_description = "Статус"

    def get_total_cost_display(self, obj):
        return f"{obj.totalCost}$"

    get_total_cost_display.short_description = "Сумма заказа"

    def get_delivery_type_display_ru(self, obj):
        """Отображение типа доставки на русском языке"""
        delivery_types = {
            "ordinary": "Обычная доставка",
            "express": "Экспресс-доставка",
        }
        return delivery_types.get(obj.deliveryType, obj.deliveryType)

    get_delivery_type_display_ru.short_description = "Тип доставки"

    def get_payment_type_display_ru(self, obj):
        """Отображение типа платежа на русском языке"""
        payment_types = {
            "online": "Онлайн картой",
            "someone": "Онлайн со случайного чужого счёта",
        }
        return payment_types.get(obj.paymentType, obj.paymentType)

    get_payment_type_display_ru.short_description = "Тип платежа"

    def get_active_display(self, obj):
        return obj.is_active

    get_active_display.short_description = "Статус активности"
    get_active_display.boolean = True

    def delete_model(self, request, obj):
        # "Мягкое" удаление
        obj.is_active = False
        obj.save()


@admin.register(DeliverySettings)
class DeliverySettingsAdmin(admin.ModelAdmin):
    """
    Административный интерфейс для настройки стоимости доставки (Singleton)
    """

    list_display = (
        "get_express_cost_display",
        "get_free_threshold_display",
        "get_regular_cost_display",
    )
    fieldsets = (
        (
            "Настройки доставки",
            {
                "fields": (
                    "express_delivery_cost",
                    "free_delivery_threshold",
                    "regular_delivery_cost",
                ),
                "description": "Настройки стоимости доставки согласно техническому заданию. Может существовать только одна запись настроек.",
            },
        ),
    )

    def get_express_cost_display(self, obj):
        return f"{obj.express_delivery_cost}$"

    get_express_cost_display.short_description = "Экспресс-доставка"

    def get_free_threshold_display(self, obj):
        return f"{obj.free_delivery_threshold}$"

    get_free_threshold_display.short_description = "Порог бесплатной доставки"

    def get_regular_cost_display(self, obj):
        return f"{obj.regular_delivery_cost}$"

    get_regular_cost_display.short_description = "Обычная доставка"

    def has_add_permission(self, request):
        # Разрешаем добавление только если нет записей
        return not DeliverySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Запрещаем удаление singleton записи
        return False

    def changelist_view(self, request, extra_context=None):
        """
        Переопределяем changelist_view для автоматического перенаправления на редактирование
        единственной записи, если она существует
        """
        try:
            settings = DeliverySettings.get_settings()
            from django.http import HttpResponseRedirect
            from django.urls import reverse

            return HttpResponseRedirect(
                reverse("admin:orders_deliverysettings_change", args=[settings.pk])
            )
        except Exception:
            return super().changelist_view(request, extra_context)

    def response_change(self, request, obj):
        """
        После сохранения изменений остаемся на той же странице
        """
        from django.http import HttpResponseRedirect

        return HttpResponseRedirect(request.path)


admin.site.register(Order, OrderAdmin)

# Изменяем заголовок админ панели
admin.site.site_header = "Админ панель интернет-магазина"
admin.site.site_title = "Админ панель"
admin.site.index_title = "Управление интернет-магазином"
