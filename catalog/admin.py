from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product, Tag, Review, Specification, Sale


class SpecificationInline(admin.TabularInline):
    model = Specification
    extra = 1
    verbose_name = "Характеристика"
    verbose_name_plural = "Характеристики"


class CategoryAdmin(admin.ModelAdmin):
    list_display = ("get_title_display", "get_parent_display", "get_active_display")
    list_filter = ("is_active",)
    search_fields = ("title",)

    def get_title_display(self, obj):
        return obj.title

    get_title_display.short_description = "Название"

    def get_parent_display(self, obj):
        return obj.parent.title if obj.parent else "Корневая категория"

    get_parent_display.short_description = "Родительская категория"

    def get_active_display(self, obj):
        return obj.is_active

    get_active_display.short_description = "Активна"
    get_active_display.boolean = True

    def delete_model(self, request, obj):
        # "Мягкое" удаление
        obj.is_active = False
        obj.save()


class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "get_title_display",
        "get_image_preview",
        "get_category_display",
        "get_price_display",
        "get_count_display",
        "get_rating_display",
        "get_free_delivery_display",
        "get_limited_display",
        "get_banner_display",
        "get_active_display",
    )
    list_filter = ("category", "freeDelivery", "limited", "is_banner", "is_active")
    search_fields = ("title", "description")
    inlines = [SpecificationInline]
    filter_horizontal = ("tags",)
    fields = (
        "category",
        "title",
        "description",
        "fullDescription",
        "price",
        "count",
        "get_image_preview_large",
        "image",
        "image_alt",
        "freeDelivery",
        "tags",
        "rating",
        "purchases_count",
        "limited",
        "is_active",
        "is_banner",
    )
    readonly_fields = ("get_image_preview_large",)

    def get_title_display(self, obj):
        return obj.title

    get_title_display.short_description = "Название"

    def get_category_display(self, obj):
        return obj.category.title

    get_category_display.short_description = "Категория"

    def get_price_display(self, obj):
        return f"{obj.price}$"

    get_price_display.short_description = "Цена"

    def get_count_display(self, obj):
        return f"{obj.count} шт."

    get_count_display.short_description = "Количество"

    def get_rating_display(self, obj):
        return f"{obj.rating}/5"

    get_rating_display.short_description = "Рейтинг"

    def get_free_delivery_display(self, obj):
        return obj.freeDelivery

    get_free_delivery_display.short_description = "Бесплатная доставка"
    get_free_delivery_display.boolean = True

    def get_limited_display(self, obj):
        return obj.limited

    get_limited_display.short_description = "Ограниченный тираж"
    get_limited_display.boolean = True

    def get_banner_display(self, obj):
        return obj.is_banner

    get_banner_display.short_description = "В баннере"
    get_banner_display.boolean = True

    def get_active_display(self, obj):
        return obj.is_active

    get_active_display.short_description = "Статус"
    get_active_display.boolean = True

    def get_image_preview(self, obj):
        """Предварительный просмотр изображения товара для списка"""
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />',
                obj.image.url,
            )
        else:
            return format_html(
                '<img src="/media/placeholder.jpg" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px; opacity: 0.5;" />'
            )

    get_image_preview.short_description = "Изображение"

    def get_image_preview_large(self, obj):
        """Большой предварительный просмотр изображения товара для формы редактирования"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px; object-fit: cover; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />',
                obj.image.url,
            )
        else:
            return format_html(
                '<img src="/media/placeholder.jpg" style="max-width: 200px; max-height: 200px; object-fit: cover; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); opacity: 0.5;" />'
                '<br><small style="color: #666; margin-top: 8px; display: block;">Дефолтное изображение</small>'
            )

    get_image_preview_large.short_description = "Текущее изображение"

    def delete_model(self, request, obj):
        # "Мягкое" удаление
        obj.is_active = False
        obj.save()


class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "get_author_display",
        "get_product_display",
        "get_rate_display",
        "get_date_display",
        "get_active_display",
    )
    list_filter = ("rate", "is_active")
    search_fields = ("author", "text")

    def get_author_display(self, obj):
        return obj.author

    get_author_display.short_description = "Автор"

    def get_product_display(self, obj):
        return obj.product.title

    get_product_display.short_description = "Товар"

    def get_rate_display(self, obj):
        return f"{obj.rate}/5 ⭐"

    get_rate_display.short_description = "Оценка"

    def get_date_display(self, obj):
        return obj.date.strftime("%d.%m.%Y %H:%M")

    get_date_display.short_description = "Дата отзыва"

    def get_active_display(self, obj):
        return obj.is_active

    get_active_display.short_description = "Статус"
    get_active_display.boolean = True

    def delete_model(self, request, obj):
        # "Мягкое" удаление
        obj.is_active = False
        obj.save()


class TagAdmin(admin.ModelAdmin):
    list_display = ("get_name_display", "get_active_display")
    list_filter = ("is_active",)
    search_fields = ("name",)

    def get_name_display(self, obj):
        return obj.name

    get_name_display.short_description = "Название"

    def get_active_display(self, obj):
        return obj.is_active

    get_active_display.short_description = "Активен"
    get_active_display.boolean = True

    def delete_model(self, request, obj):
        # "Мягкое" удаление
        obj.is_active = False
        obj.save()


class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "get_product_display",
        "get_sale_price_display",
        "get_date_from_display",
        "get_date_to_display",
        "get_active_display",
    )
    list_filter = ("dateFrom", "dateTo", "is_active")

    def get_product_display(self, obj):
        return obj.product.title

    get_product_display.short_description = "Товар"

    def get_sale_price_display(self, obj):
        return f"{obj.salePrice}$"

    get_sale_price_display.short_description = "Цена со скидкой"

    def get_date_from_display(self, obj):
        return obj.dateFrom.strftime("%d.%m.%Y")

    get_date_from_display.short_description = "Дата начала"

    def get_date_to_display(self, obj):
        return obj.dateTo.strftime("%d.%m.%Y")

    get_date_to_display.short_description = "Дата окончания"

    def get_active_display(self, obj):
        return obj.is_active

    get_active_display.short_description = "Статус"
    get_active_display.boolean = True

    def delete_model(self, request, obj):
        # "Мягкое" удаление
        obj.is_active = False
        obj.save()


admin.site.register(Category, CategoryAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(Review, ReviewAdmin)
admin.site.register(Sale, SaleAdmin)
