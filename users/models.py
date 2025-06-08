import logging
import time

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db import transaction, IntegrityError, OperationalError
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


class Profile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Пользователь",
    )
    fullName = models.CharField(max_length=255, blank=True, verbose_name="Полное имя")
    phone = models.CharField(
        max_length=20, blank=True, unique=True, null=True, verbose_name="Телефон"
    )
    avatar = models.ImageField(
        upload_to="avatars/",
        blank=True,
        default="placeholder.jpg",
        verbose_name="Аватар",
    )
    is_active = models.BooleanField(
        default=True, verbose_name="Активен"
    )  # Для "мягкого" удаления

    def save(self, *args, **kwargs):
        # Если phone пустой, устанавливаем None для правильной работы unique
        if not self.phone:
            self.phone = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username}'s profile"

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Создает профиль пользователя при создании нового пользователя.
    Использует атомарные операции и retry логику для предотвращения race conditions.
    """
    if created:
        # Проверяем, не создается ли профиль уже в админке
        if hasattr(instance, "_skip_profile_creation"):
            logger.debug(
                f"Пропускаем создание профиля для {instance.username} (флаг _skip_profile_creation)"
            )
            return

        # Retry логика для обработки конкурентного доступа и блокировок БД
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    # Двойная проверка для абсолютной безопасности
                    try:
                        existing_profile = Profile.objects.select_for_update(
                            nowait=True
                        ).get(user=instance)
                        logger.debug(
                            f"Профиль для пользователя {instance.username} уже существует (ID: {existing_profile.id})"
                        )
                        return
                    except ObjectDoesNotExist:
                        # Профиля нет, создаем его - это ожидаемое поведение
                        logger.debug(
                            f"Профиль для пользователя {instance.username} не найден, создаем новый"
                        )

                    # Создаем профиль
                    profile = Profile.objects.create(user=instance)
                    logger.debug(
                        f"Создан профиль (ID: {profile.id}) для пользователя {instance.username}"
                    )
                    return  # Успешно создан, выходим

            except IntegrityError as e:
                # Нарушение уникальности - профиль уже создан другим процессом
                logger.debug(
                    f"Профиль для пользователя {instance.username} уже создан другим процессом: {str(e)}"
                )
                return  # Профиль создан, миссия выполнена

            except OperationalError as e:
                # Блокировка базы данных
                if "database is locked" in str(e).lower() or "locked" in str(e).lower():
                    if attempt < max_retries - 1:
                        # Ждем немного и пробуем снова
                        wait_time = 0.1 * (2**attempt)  # Экспоненциальная задержка
                        logger.debug(
                            f"База заблокирована, повтор через {wait_time}с (попытка {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.warning(
                            f"Не удалось создать профиль для {instance.username} после {max_retries} попыток: {str(e)}"
                        )
                        # Пытаемся создать профиль без транзакции как последняя попытка
                        try:
                            Profile.objects.get_or_create(user=instance)
                            logger.debug(
                                f"Профиль для {instance.username} создан без транзакции"
                            )
                        except Exception as fallback_e:
                            logger.error(
                                f"Финальная попытка создания профиля провалена: {str(fallback_e)}"
                            )
                else:
                    logger.error(
                        f"Ошибка БД при создании профиля для {instance.username}: {str(e)}"
                    )
                    break

            except Exception as e:
                # Любые другие неожиданные ошибки
                logger.error(
                    f"Неожиданная ошибка при создании профиля для {instance.username}: {str(e)}"
                )
                break

        # Финальная проверка - есть ли профиль
        try:
            Profile.objects.get(user=instance)
            logger.debug(
                f"Профиль для {instance.username} найден после завершения процесса"
            )
        except ObjectDoesNotExist:
            logger.warning(
                f"Профиль для {instance.username} не создан и не найден после всех попыток"
            )
