from django.urls import path

from . import views

urlpatterns = [
    path("categories", views.categories_list, name="categories"),
    path("catalog", views.catalog, name="catalog"),
    path("products/popular", views.popular_products, name="popular-products"),
    path("products/limited", views.limited_products, name="limited-products"),
    path("sales", views.sales, name="sales"),
    path("banners", views.banners, name="banners"),
    path("product/<int:pk>", views.product_detail, name="product-detail"),
    path("product/<int:product_id>/review", views.review, name="product-review"),
    path("tags", views.tags_list, name="tags"),
]
