# Интернет-магазин Megano

Django-приложение интернет-магазина с REST API и готовым фронтендом.

## Возможности

- 🛍️ Каталог товаров с фильтрацией и сортировкой
- 🛒 Корзина покупок
- 👤 Личный кабинет пользователя
- 📦 Система заказов
- 💳 Имитация платежной системы
- 🔧 Админ-панель Django
- 📱 Адаптивный дизайн

## Системные требования

- Python 3.8+
- Django 5.2.2
- SQLite3 (по умолчанию)
- Nginx (для продакшена)

## Быстрый старт (разработка)

1. **Клонирование репозитория:**
```bash
git clone <repository-url>
cd python_django_diploma
```

2. **Создание виртуального окружения:**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или
.venv\Scripts\activate     # Windows
```

3. **Установка зависимостей:**
```bash
pip install -r requirements.txt
```

4. **Настройка переменных окружения:**
Создайте файл `.env` в корне проекта со следующим содержимым:
```
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

5. **Применение миграций:**
```bash
python manage.py migrate
```

6. **Загрузка тестовых данных:**
```bash
./restore_fixtures.sh
# Этот скрипт создаст администратора (admin/admin) и загрузит все тестовые данные
```

8. **Запуск сервера разработки:**
```bash
python manage.py runserver 127.0.0.1:8000
```

Сайт будет доступен по адресу: http://127.0.0.1:8000

### 👤 Тестовые учетные записи

После загрузки фикстур доступны:
- **Администратор:** admin / admin
- **Тестовые покупатели:** user1@example.com, user2@example.com и т.д. / password123

## Развертывание в продакшене

### 1. Подготовка проекта

```bash
# Клонирование проекта
git clone <repository-url>
cd python_django_diploma

# Создание виртуального окружения
python -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Создайте файл `.env` в корне проекта:
```
SECRET_KEY=your-strong-secret-key-for-production
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,127.0.0.1
```

### 3. Подготовка статических файлов

```bash
# Применение миграций
python manage.py migrate

# Загрузка данных из фикстур (включая администратора)
./restore_fixtures.sh

# Сборка статических файлов
python manage.py collectstatic --noinput
```

### 4. Настройка Nginx

Создайте файл конфигурации nginx (например, `/etc/nginx/sites-available/megano-shop`):

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    
    # Максимальный размер загружаемых файлов
    client_max_body_size 20M;
    
    # Логи
    access_log /var/log/nginx/megano_shop_access.log;
    error_log /var/log/nginx/megano_shop_error.log;
    
    # Статические файлы
    location /static/ {
        alias /path/to/your/project/static_collected/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Медиа файлы
    location /media/ {
        alias /path/to/your/project/media/;
        expires 1y;
        add_header Cache-Control "public";
    }
    
    # Основное приложение Django
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
    
    # Безопасность
    location ~ /\.(?!well-known).* {
        deny all;
    }
    
    location ~ \.(txt|md)$ {
        deny all;
    }
}
```

### 5. Активация конфигурации Nginx

```bash
# Создание символической ссылки
sudo ln -s /etc/nginx/sites-available/megano-shop /etc/nginx/sites-enabled/

# Проверка конфигурации
sudo nginx -t

# Перезагрузка nginx
sudo systemctl reload nginx
```

### 6. Запуск Django с Gunicorn

```bash
# Запуск через Gunicorn
gunicorn --bind 127.0.0.1:8000 --workers 3 mysite.wsgi:application

# Или в фоновом режиме
nohup gunicorn --bind 127.0.0.1:8000 --workers 3 mysite.wsgi:application > gunicorn.log 2>&1 &
```

### 7. Настройка автозапуска (systemd)

Создайте файл `/etc/systemd/system/megano-shop.service`:

```ini
[Unit]
Description=Megano Shop Django App
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/your/project
Environment=PATH=/path/to/your/project/.venv/bin
ExecStart=/path/to/your/project/.venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 3 mysite.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

Активация службы:
```bash
sudo systemctl daemon-reload
sudo systemctl enable megano-shop.service
sudo systemctl start megano-shop.service
sudo systemctl status megano-shop.service
```

## Структура проекта

```
python_django_diploma/
├── mysite/              # Настройки Django
├── users/               # Приложение пользователей
├── catalog/             # Каталог товаров
├── basket/              # Корзина
├── orders/              # Заказы
├── payments/            # Платежи
├── media/               # Загруженные файлы
├── static_collected/    # Собранная статика
├── fixtures/            # Тестовые данные
├── logs/                # Логи приложения
├── requirements.txt     # Зависимости Python
├── nginx.conf           # Пример конфигурации Nginx
└── manage.py           # Django CLI
```

## API Endpoints

- `/api/categories/` - Категории товаров
- `/api/catalog/` - Каталог товаров
- `/api/product/{id}/` - Детали товара
- `/api/basket/` - Корзина
- `/api/orders/` - Заказы
- `/api/sign-in/` - Авторизация
- `/api/sign-up/` - Регистрация
- `/api/profile/` - Профиль пользователя

## Админ-панель

Доступна по адресу: `/admin/`

Возможности:
- Управление товарами и категориями
- Просмотр и управление заказами
- Управление пользователями
- Просмотр отзывов

## Особенности

- ✅ Мягкое удаление для товаров, категорий, пользователей
- ✅ Система скидок и акций
- ✅ Загрузка изображений товаров
- ✅ Фильтрация и сортировка товаров
- ✅ Корзина для неавторизованных пользователей
- ✅ История заказов
- ✅ Имитация платежной системы

## Тестовые данные

Фикстуры включают:
- **30 товаров** в 5 категориях
- **9 категорий** товаров  
- **59 отзывов** пользователей
- **10 активных скидок**
- **6 пользователей** с профилями
- **Администратор** со всеми правами

## Безопасность

В продакшене включены:
- CSRF защита
- XSS защита
- Защита от clickjacking
- Валидация загружаемых файлов
- Ограничение размера загружаемых файлов

## Логирование

Логи приложения сохраняются в:
- `logs/django.log` - основные логи Django
- Console output - для отладки

## Поддержка

При возникновении проблем проверьте:
1. Логи nginx: `/var/log/nginx/megano_shop_error.log`
2. Логи Django: `logs/django.log`
3. Статус systemd службы: `sudo systemctl status megano-shop.service`

