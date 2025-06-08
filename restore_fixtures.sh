#!/bin/bash

# Скрипт для восстановления базы данных из дампов
# Использование: ./restore_fixtures.sh [опции]

show_help() {
    echo "🔄 Скрипт восстановления базы данных из фикстур"
    echo ""
    echo "Использование: $0 [опции]"
    echo ""
    echo "Опции:"
    echo "  --full              Восстановить полный дамп (по умолчанию)"
    echo "  --clean             Восстановить чистый дамп (без системных таблиц)"
    echo "  --apps              Восстановить по приложениям"
    echo "  --catalog-only      Восстановить только каталог"
    echo "  --users-only        Восстановить только пользователей"
    echo "  --delivery-only     Восстановить только настройки доставки"
    echo "  --verify-delivery   Проверить состояние DeliverySettings"
    echo "  --help, -h          Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0                        # Полное восстановление"
    echo "  $0 --clean               # Восстановление без системных данных"
    echo "  $0 --catalog-only        # Только каталог товаров"
    echo "  $0 --delivery-only       # Только настройки доставки"
    echo "  $0 --verify-delivery     # Проверка DeliverySettings"
    echo ""
}

# Функция для проверки DeliverySettings
verify_delivery_settings() {
    echo "🔧 Проверка состояния DeliverySettings..."
    
    # Проверяем количество записей - извлекаем только последнюю строку с числом
    local count_output=$(python manage.py shell --verbosity=0 -c "from orders.models import DeliverySettings; print(DeliverySettings.objects.count())" 2>/dev/null)
    local count=$(echo "$count_output" | tail -n 1 | tr -d '[:space:]')
    
    if [ -z "$count" ] || [ "$count" = "error" ]; then
        echo "❌ Ошибка при проверке DeliverySettings"
        return 1
    elif [ "$count" = "0" ]; then
        echo "⚠️  DeliverySettings не найдены"
        echo "   Создаём запись по умолчанию..."
        python manage.py shell --verbosity=0 -c "from orders.models import DeliverySettings; ds = DeliverySettings.get_settings(); print(f'✅ Создана запись ID={ds.id}')" 2>/dev/null
    elif [ "$count" = "1" ]; then
        echo "✅ DeliverySettings в порядке (1 запись)"
        python manage.py shell --verbosity=0 -c "from orders.models import DeliverySettings; ds = DeliverySettings.get_settings(); print(f'   ID: {ds.id}, Express: {ds.express_delivery_cost}, Regular: {ds.regular_delivery_cost}')" 2>/dev/null
    else
        echo "⚠️  Найдено $count записей DeliverySettings (должна быть 1)"
        echo "   Это нарушает singleton constraint!"
        
        # Пытаемся исправить ситуацию
        echo "   Попытка исправления..."
        python manage.py shell --verbosity=0 -c "
from orders.models import DeliverySettings
from django.db import transaction

with transaction.atomic():
    # Удаляем все записи кроме первой
    extra_records = DeliverySettings.objects.exclude(pk=1)
    if extra_records.exists():
        count = extra_records.count()
        extra_records.delete()
        print(f'✅ Удалено {count} лишних записей')
    
    # Проверяем/создаем основную запись
    ds = DeliverySettings.get_settings()
    print(f'✅ Основная запись ID={ds.id} в порядке')
" 2>/dev/null
    fi
}

# Функция для очистки базы данных
clear_database() {
    echo "🗑️  Очистка базы данных..."
    
    # Удаляем старую базу данных
    if [ -f "db.sqlite3" ]; then
        rm db.sqlite3
        echo "   ✅ Старая база данных удалена"
    fi
    
    # Создаем новую базу данных
    echo "   🔨 Создание новой базы данных..."
    python manage.py migrate --verbosity=0
    echo "   ✅ Новая база данных создана"
    
    # Автоматически создаём DeliverySettings для совместимости
    echo "   🔧 Инициализация DeliverySettings..."
    python manage.py shell --verbosity=0 -c "from orders.models import DeliverySettings; ds = DeliverySettings.get_settings(); print(f'   ✅ DeliverySettings инициализированы (ID={ds.id})')" 2>/dev/null
}

# Функция для восстановления полного дампа
restore_full() {
    echo "📊 Восстановление полного дампа..."
    if [ ! -f "fixtures/full_database_dump.json" ]; then
        echo "❌ Файл fixtures/full_database_dump.json не найден!"
        exit 1
    fi
    
    clear_database
    python manage.py loaddata fixtures/full_database_dump.json
    echo "✅ Полный дамп восстановлен"
    
    # Проверяем DeliverySettings после восстановления
    verify_delivery_settings
}

# Функция для восстановления чистого дампа
restore_clean() {
    echo "🧹 Восстановление чистого дампа..."
    if [ ! -f "fixtures/clean_database_dump.json" ]; then
        echo "❌ Файл fixtures/clean_database_dump.json не найден!"
        exit 1
    fi
    
    clear_database
    python manage.py loaddata fixtures/clean_database_dump.json
    echo "✅ Чистый дамп восстановлен"
    
    # Проверяем DeliverySettings после восстановления
    verify_delivery_settings
}

# Функция для восстановления по приложениям
restore_apps() {
    echo "📦 Восстановление по приложениям..."
    
    clear_database
    
    # Порядок загрузки важен из-за зависимостей
    local apps=("auth_dump" "users_dump" "catalog_dump" "orders_dump" "payments_dump" "basket_dump")
    local names=("🔐 Авторизация" "👥 Пользователи" "🛍️  Каталог" "📋 Заказы" "💳 Платежи" "🛒 Корзина")
    
    for i in "${!apps[@]}"; do
        local app="${apps[$i]}"
        local name="${names[$i]}"
        local file="fixtures/${app}.json"
        
        if [ -f "$file" ]; then
            echo "   $name..."
            python manage.py loaddata "$file"
            echo "     ✅ Загружено"
        else
            echo "     ⚠️  Файл $file не найден, пропускаем"
        fi
    done
    
    echo "✅ Восстановление по приложениям завершено"
    
    # Проверяем DeliverySettings после восстановления
    verify_delivery_settings
}

# Функция для восстановления только каталога
restore_catalog_only() {
    echo "🛍️  Восстановление только каталога..."
    
    if [ ! -f "fixtures/catalog_dump.json" ]; then
        echo "❌ Файл fixtures/catalog_dump.json не найден!"
        exit 1
    fi
    
    # Не очищаем всю базу, только загружаем каталог
    python manage.py loaddata fixtures/catalog_dump.json
    echo "✅ Каталог восстановлен"
}

# Функция для восстановления только пользователей
restore_users_only() {
    echo "👥 Восстановление только пользователей..."
    
    local files=("fixtures/auth_dump.json" "fixtures/users_dump.json")
    
    for file in "${files[@]}"; do
        if [ -f "$file" ]; then
            python manage.py loaddata "$file"
        else
            echo "⚠️  Файл $file не найден, пропускаем"
        fi
    done
    
    echo "✅ Пользователи восстановлены"
}

# Функция для восстановления только настроек доставки
restore_delivery_only() {
    echo "⚙️  Восстановление только настроек доставки..."
    
    if [ -f "fixtures/delivery_settings_dump.json" ]; then
        echo "   Загружаем из отдельного дампа..."
        python manage.py loaddata fixtures/delivery_settings_dump.json
    elif [ -f "fixtures/orders_dump.json" ]; then
        echo "   Загружаем из дампа заказов..."
        # Создаем временный файл только с DeliverySettings
        python manage.py shell --verbosity=0 -c "
import json
with open('fixtures/orders_dump.json', 'r') as f:
    data = json.load(f)
delivery_data = [item for item in data if item['model'] == 'orders.deliverysettings']
if delivery_data:
    with open('/tmp/temp_delivery.json', 'w') as f:
        json.dump(delivery_data, f, indent=2)
    print('✅ Временный файл создан')
else:
    print('❌ DeliverySettings не найдены в orders_dump.json')
" 2>/dev/null
        
        if [ -f "/tmp/temp_delivery.json" ]; then
            python manage.py loaddata /tmp/temp_delivery.json
            rm /tmp/temp_delivery.json
            echo "✅ Настройки доставки восстановлены"
        else
            echo "❌ Не удалось извлечь настройки доставки"
        fi
    else
        echo "❌ Файлы с настройками доставки не найдены!"
        echo "   Создаём настройки по умолчанию..."
        python manage.py shell --verbosity=0 -c "from orders.models import DeliverySettings; ds = DeliverySettings.get_settings(); print(f'✅ Созданы настройки по умолчанию (ID={ds.id})')" 2>/dev/null
    fi
    
    # Проверяем результат
    verify_delivery_settings
}

# Проверяем предварительные условия
check_prerequisites() {
    # Проверяем виртуальное окружение
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        echo "❌ Ошибка: Виртуальное окружение не активировано!"
        echo "Выполните: source .venv/bin/activate"
        exit 1
    fi
    
    # Проверяем Django проект
    if ! python manage.py check > /dev/null 2>&1; then
        echo "❌ Ошибка: Django проект недоступен или есть ошибки!"
        exit 1
    fi
    
    # Проверяем директорию fixtures (кроме verify-delivery)
    if [ "$1" != "--verify-delivery" ] && [ ! -d "fixtures" ]; then
        echo "❌ Ошибка: Директория fixtures не найдена!"
        echo "Сначала создайте дампы с помощью ./create_fixtures.sh"
        exit 1
    fi
    
    # Проверяем применение миграций
    echo "🔍 Проверка миграций..."
    if ! python manage.py showmigrations orders | grep -q "\[X\].*0001_initial"; then
        echo "⚠️  Внимание: Начальная миграция orders не применена!"
        echo "   Выполните: python manage.py migrate"
        read -p "   Продолжить восстановление? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Показываем статистику после восстановления
show_stats() {
    echo ""
    echo "📈 Статистика восстановленной базы данных:"
    echo "┌──────────────────────────────────────┬──────────┐"
    echo "│ Модель                               │ Записей  │"
    echo "├──────────────────────────────────────┼──────────┤"
    
    # Подсчитываем записи в основных моделях с фиксированным форматированием
    local models=("auth.User:Пользователи" "catalog.Product:Товары" "catalog.Category:Категории" "orders.Order:Заказы" "payments.Payment:Платежи" "orders.DeliverySettings:Настройки доставки")
    local names=("Пользователи                         " "Товары                               " "Категории                            " "Заказы                               " "Платежи                              " "Настройки доставки                  ")
    
    for i in "${!models[@]}"; do
        local model="${models[$i]%%:*}"
        local name="${names[$i]}"
        # Извлекаем только последнюю строку с числом
        local count_output=$(python manage.py shell --verbosity=0 -c "from django.apps import apps; print(apps.get_model('${model}').objects.count())" 2>/dev/null)
        local count=$(echo "$count_output" | tail -n 1 | tr -d '[:space:]')
        # Если не удалось получить число, показываем 0
        if ! [[ "$count" =~ ^[0-9]+$ ]]; then
            count="0"
        fi
        printf "│ %s │ %8s │\n" "${name:0:36}" "$count"
    done
    
    echo "└──────────────────────────────────────┴──────────┘"
    echo ""
    
    # Финальная проверка DeliverySettings
    verify_delivery_settings
    
    echo ""
    echo "🎉 Восстановление завершено успешно!"
}

# Основная логика
main() {
    echo "🔄 Восстановление базы данных из фикстур..."
    echo ""
    
    check_prerequisites "$1"
    
    case "$1" in
        --help|-h)
            show_help
            exit 0
            ;;
        --verify-delivery)
            verify_delivery_settings
            exit 0
            ;;
        --clean)
            restore_clean
            ;;
        --apps)
            restore_apps
            ;;
        --catalog-only)
            restore_catalog_only
            ;;
        --users-only)
            restore_users_only
            ;;
        --delivery-only)
            restore_delivery_only
            ;;
        --full|"")
            restore_full
            ;;
        *)
            echo "❌ Неизвестная опция: $1"
            echo "Используйте --help для справки"
            exit 1
            ;;
    esac
    
    # Показываем статистику только для полных восстановлений
    case "$1" in
        --catalog-only|--users-only|--delivery-only|--verify-delivery)
            echo "✅ Операция завершена"
            ;;
        *)
            show_stats
            ;;
    esac
}

# Запускаем основную функцию
main "$@" 