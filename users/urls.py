from django.urls import path

from . import views

urlpatterns = [
    path("sign-in", views.sign_in, name="sign-in"),
    path("sign-up", views.sign_up, name="sign-up"),
    path("sign-out", views.sign_out, name="sign-out"),
    path("profile", views.profile, name="profile"),
    path("profile/password", views.update_password, name="update-password"),
    path("profile/avatar", views.update_avatar, name="update-avatar"),
]
