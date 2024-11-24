#!/bin/bash

echo "Инициализация проекта Sales Bot..."

# Проверка наличия PostgreSQL
if ! command -v psql &> /dev/null; then
    echo "PostgreSQL не установлен. Установка..."
    sudo apt-get update
    sudo apt-get install -y postgresql postgresql-contrib
fi

# Создание базы данных
echo "Создание базы данных..."
if [ -f "init_db.sql" ]; then
    # Запуск PostgreSQL если не запущен
    sudo service postgresql start

    # Выполняем SQL скрипт
    sudo -u postgres psql -f "$(pwd)/init_db.sql"

    # Проверка результата
    if [ $? -eq 0 ]; then
        echo "База данных успешно создана"
    else
        echo "Ошибка при создании базы данных"
        exit 1
    fi
else
    echo "Ошибка: Файл init_db.sql не найден в текущей директории"
    exit 1
fi

# Создание виртуального окружения
echo "Настройка Python окружения..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Создание директории для логов
echo "Создание директории для логов..."
sudo mkdir -p /var/log/sales_bot
sudo chown $USER:$USER /var/log/sales_bot

echo "Инициализация завершена!"
echo "Для запуска бота:"
echo "1. Установите необходимые переменные окружения"
echo "2. Запустите ./run.sh"
