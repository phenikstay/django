from django.urls import path

from . import views

urlpatterns = [
    path("payment/<int:order_id>/", views.payment, name="payment-create"),
    path(
        "payment-someone/<int:order_id>/", views.payment_someone, name="payment-someone"
    ),
    path(
        "generate-random-account/",
        views.generate_random_account,
        name="generate-random-account",
    ),
    path("payment-status/<int:order_id>/", views.payment_status, name="payment-status"),
]
