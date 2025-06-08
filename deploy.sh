#!/bin/bash

# Скрипт развертывания Django проекта в продакшене
# Использование: ./deploy.sh

set -e  # Остановиться при первой ошибке

echo "🚀 Начинаем развертывание Megano Shop..."

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден!"
    echo "Создайте файл .env со следующим содержимым:"
    echo "SECRET_KEY=your-strong-secret-key"
    echo "DEBUG=False"
    echo "ALLOWED_HOSTS=your-domain.com,127.0.0.1"
    exit 1
fi

# Проверяем виртуальное окружение
if [ ! -d ".venv" ]; then
    echo "📦 Создаем виртуальное окружение..."
    python3 -m venv .venv
fi

echo "🔧 Активируем виртуальное окружение..."
source .venv/bin/activate

echo "📥 Устанавливаем зависимости..."
pip install -r requirements.txt

echo "🗃️ Применяем миграции..."
python manage.py migrate

echo "📊 Загружаем данные из фикстур..."
chmod +x restore_fixtures.sh
./restore_fixtures.sh

echo "📁 Собираем статические файлы..."
python manage.py collectstatic --noinput

echo "✅ Развертывание завершено!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Настройте nginx согласно README.md"
echo "2. Запустите с Gunicorn: gunicorn --bind 127.0.0.1:8000 mysite.wsgi:application"
echo ""
echo "👤 Администратор создан: логин 'admin', пароль 'admin'"
echo ""
echo "🌐 Конфигурация nginx находится в файле nginx.conf" 