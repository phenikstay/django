from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "get_id_display",
        "get_order_display",
        "get_payment_type_display_ru",
        "get_number_display",
        "get_name_display",
        "get_status_display_ru",
        "get_created_at_display",
        "get_processed_at_display",
    )
    list_filter = ("payment_type", "status", "created_at")
    search_fields = ("order__id", "number", "name", "order__fullName", "order__email")
    readonly_fields = ("created_at", "processed_at")
    raw_id_fields = ("order",)

    def get_id_display(self, obj):
        return obj.id

    get_id_display.short_description = "ID"

    def get_order_display(self, obj):
        return f"Заказ #{obj.order.id}"

    get_order_display.short_description = "Заказ"

    def get_payment_type_display_ru(self, obj):
        """Отображение типа платежа на русском языке"""
        payment_types = {
            "card": "Онлайн картой",
            "someone": "Онлайн со случайного чужого счёта",
        }
        return payment_types.get(obj.payment_type, obj.payment_type)

    get_payment_type_display_ru.short_description = "Тип платежа"

    def get_number_display(self, obj):
        return obj.number

    get_number_display.short_description = "Номер карты/счёта"

    def get_name_display(self, obj):
        return obj.name or "-"

    get_name_display.short_description = "Имя владельца"

    def get_status_display_ru(self, obj):
        """Отображение статуса платежа на русском языке"""
        statuses = {
            "pending": "Ожидает обработки",
            "success": "Успешно",
            "failed": "Неуспешно",
        }
        return statuses.get(obj.status, obj.status)

    get_status_display_ru.short_description = "Статус"

    def get_created_at_display(self, obj):
        return obj.created_at.strftime("%d.%m.%Y %H:%M")

    get_created_at_display.short_description = "Дата создания"

    def get_processed_at_display(self, obj):
        return obj.processed_at.strftime("%d.%m.%Y %H:%M") if obj.processed_at else "-"

    get_processed_at_display.short_description = "Дата обработки"

    fieldsets = (
        (
            "Основная информация",
            {"fields": ("order", "payment_type", "status", "error_message")},
        ),
        (
            "Данные платежа",
            {
                "fields": ("number", "name", "month", "year", "code"),
                "description": "Для платежей картой заполняются все поля, для случайного счёта - только номер",
            },
        ),
        (
            "Временные метки",
            {"fields": ("created_at", "processed_at"), "classes": ("collapse",)},
        ),
    )
