#!/bin/bash

# Скрипт для создания полных дампов базы данных
# Использование: ./create_fixtures.sh

echo "🚀 Создание дампов базы данных..."

# Создаем директорию для фикстур
mkdir -p fixtures

# Проверяем, что виртуальное окружение активно
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "❌ Ошибка: Виртуальное окружение не активировано!"
    echo "Выполните: source .venv/bin/activate"
    exit 1
fi

# Проверяем, что Django проект доступен
if ! python manage.py check > /dev/null 2>&1; then
    echo "❌ Ошибка: Django проект недоступен или есть ошибки!"
    exit 1
fi

# Проверяем состояние миграций
echo "🔍 Проверка состояния миграций..."
if ! python manage.py showmigrations --plan | grep -q "\[X\]"; then
    echo "⚠️  Внимание: Не все миграции применены!"
    echo "Выполните: python manage.py migrate"
    read -p "Продолжить создание дампов? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Проверяем наличие DeliverySettings
echo "🔧 Проверка настроек доставки..."
DELIVERY_SETTINGS_COUNT=$(python manage.py shell --verbosity=0 -c "from orders.models import DeliverySettings; print(DeliverySettings.objects.count())" 2>/dev/null | tail -n 1 | tr -d '[:space:]' || echo "0")
if [ "$DELIVERY_SETTINGS_COUNT" = "0" ]; then
    echo "⚠️  DeliverySettings не найдены, создаём запись по умолчанию..."
    python manage.py shell --verbosity=0 -c "from orders.models import DeliverySettings; DeliverySettings.get_settings(); print('✅ DeliverySettings созданы')" 2>/dev/null
elif [ "$DELIVERY_SETTINGS_COUNT" != "1" ]; then
    echo "⚠️  Обнаружено $DELIVERY_SETTINGS_COUNT записей DeliverySettings (должна быть 1)"
    echo "Это может указывать на проблему с singleton constraint"
fi

echo "📊 Создание полного дампа базы данных..."
python manage.py dumpdata --indent=2 --output=fixtures/full_database_dump.json
echo "✅ Полный дамп создан: $(du -h fixtures/full_database_dump.json | cut -f1)"

echo "🧹 Создание чистого дампа (без системных таблиц)..."
python manage.py dumpdata --indent=2 \
    --exclude=auth.permission \
    --exclude=contenttypes \
    --exclude=admin.logentry \
    --exclude=sessions.session \
    --output=fixtures/clean_database_dump.json
echo "✅ Чистый дамп создан: $(du -h fixtures/clean_database_dump.json | cut -f1)"

echo "📦 Создание дампов по приложениям..."

# Каталог товаров
echo "  🛍️  Каталог..."
python manage.py dumpdata catalog --indent=2 --output=fixtures/catalog_dump.json
echo "     ✅ $(du -h fixtures/catalog_dump.json | cut -f1)"

# Пользователи
echo "  👥 Пользователи..."
python manage.py dumpdata users --indent=2 --output=fixtures/users_dump.json
echo "     ✅ $(du -h fixtures/users_dump.json | cut -f1)"

# Заказы (включая DeliverySettings)
echo "  📋 Заказы и настройки доставки..."
python manage.py dumpdata orders --indent=2 --output=fixtures/orders_dump.json
echo "     ✅ $(du -h fixtures/orders_dump.json | cut -f1)"

# Платежи
echo "  💳 Платежи..."
python manage.py dumpdata payments --indent=2 --output=fixtures/payments_dump.json
echo "     ✅ $(du -h fixtures/payments_dump.json | cut -f1)"

# Корзина
echo "  🛒 Корзина..."
python manage.py dumpdata basket --indent=2 --output=fixtures/basket_dump.json
echo "     ✅ $(du -h fixtures/basket_dump.json | cut -f1)"

# Авторизация
echo "  🔐 Авторизация..."
python manage.py dumpdata auth.user auth.group --indent=2 --output=fixtures/auth_dump.json
echo "     ✅ $(du -h fixtures/auth_dump.json | cut -f1)"

# Создаем специальный дамп только DeliverySettings для быстрого восстановления
echo "  ⚙️  Настройки доставки (отдельно)..."
python manage.py dumpdata orders.deliverysettings --indent=2 --output=fixtures/delivery_settings_dump.json
echo "     ✅ $(du -h fixtures/delivery_settings_dump.json | cut -f1)"

echo ""
echo "📈 Статистика дампов:"
echo "┌──────────────────────────────────────┬──────────┐"
echo "│ Файл                                 │ Размер   │"
echo "├──────────────────────────────────────┼──────────┤"
ls -lh fixtures/*.json | awk '{printf "│ %-36s │ %8s │\n", $9, $5}'
echo "└──────────────────────────────────────┴──────────┘"

# Проверяем корректность DeliverySettings в дампе
echo ""
echo "🔍 Проверка корректности DeliverySettings в дампах..."
DELIVERY_IN_ORDERS=$(grep -c "orders.deliverysettings" fixtures/orders_dump.json 2>/dev/null || echo "0")
DELIVERY_IN_CLEAN=$(grep -c "orders.deliverysettings" fixtures/clean_database_dump.json 2>/dev/null || echo "0")
DELIVERY_IN_FULL=$(grep -c "orders.deliverysettings" fixtures/full_database_dump.json 2>/dev/null || echo "0")

if [ "$DELIVERY_IN_ORDERS" = "1" ] && [ "$DELIVERY_IN_CLEAN" = "1" ] && [ "$DELIVERY_IN_FULL" = "1" ]; then
    echo "✅ DeliverySettings корректно включены во все дампы"
else
    echo "⚠️  Проблема с DeliverySettings в дампах:"
    echo "   orders_dump.json: $DELIVERY_IN_ORDERS записей"
    echo "   clean_database_dump.json: $DELIVERY_IN_CLEAN записей"
    echo "   full_database_dump.json: $DELIVERY_IN_FULL записей"
fi

echo ""
echo "🎉 Все дампы успешно созданы!"
echo "📁 Файлы сохранены в директории: fixtures/"
echo ""
echo "📝 Для восстановления используйте:"
echo "   ./restore_fixtures.sh"
echo ""
