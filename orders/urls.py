from django.urls import path

from . import views

urlpatterns = [
    path("orders", views.orders, name="orders-list-create"),
    path("orders/<int:order_id>", views.order_view, name="order-detail"),
    path("orders/last/", views.last_order, name="last-order"),
    path("delivery-settings/", views.delivery_settings, name="delivery-settings"),
]
