from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import Profile


class UserForm(forms.ModelForm):
    """Форма пользователя с валидацией email и обработкой пароля"""

    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput,
        required=False,
        help_text="Оставьте пустым, чтобы не менять пароль. Введите новый пароль для изменения.",
    )

    class Meta:
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Если редактируем существующего пользователя, очищаем поле пароля
        if self.instance and self.instance.pk:
            self.fields["password"].initial = ""

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            # Исключаем текущего пользователя при проверке уникальности
            existing_user = User.objects.filter(email=email)
            if self.instance and self.instance.pk:
                existing_user = existing_user.exclude(pk=self.instance.pk)

            if existing_user.exists():
                raise ValidationError(f'Пользователь с email "{email}" уже существует.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")

        # Если введен новый пароль, устанавливаем его
        if password:
            user.set_password(password)

        if commit:
            user.save()
        return user


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Профиль"

    def get_or_create_instance(self, request, instance=None):
        """Получаем или создаем экземпляр профиля"""
        if instance is None:
            return None
        try:
            return instance.profile
        except Profile.DoesNotExist:
            return Profile(user=instance)


class UserAdmin(BaseUserAdmin):
    form = UserForm
    inlines = (ProfileInline,)
    list_display = (
        "get_username_display",
        "get_email_display",
        "get_full_name",
        "get_phone",
        "get_active_display",
        "get_staff_display",
    )

    # Настройка полей формы
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Персональная информация", {"fields": ("first_name", "last_name", "email")}),
        (
            "Права доступа",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Важные даты", {"fields": ("last_login", "date_joined")}),
    )

    def get_username_display(self, instance):
        return instance.username

    get_username_display.short_description = "Имя пользователя"

    def get_email_display(self, instance):
        return instance.email or "-"

    get_email_display.short_description = "Email"

    def get_full_name(self, instance):
        return instance.profile.fullName or "-"

    get_full_name.short_description = "Полное имя"

    def get_phone(self, instance):
        return instance.profile.phone or "-"

    get_phone.short_description = "Телефон"

    def get_active_display(self, instance):
        return instance.is_active

    get_active_display.short_description = "Активен"
    get_active_display.boolean = True

    def get_staff_display(self, instance):
        return instance.is_staff

    get_staff_display.short_description = "Сотрудник"
    get_staff_display.boolean = True

    def save_model(self, request, obj, form, change):
        """Сохранение пользователя с правильной обработкой профиля"""
        # Если создаем нового пользователя и у него есть inline профиль,
        # устанавливаем флаг для предотвращения дублирования
        if not change:  # Создание нового пользователя
            obj._skip_profile_creation = True

        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        # "Мягкое" удаление
        obj.is_active = False
        obj.profile.is_active = False
        obj.profile.save()
        obj.save()


# Перерегистрация модели User с нашим UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
