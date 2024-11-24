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
    # Выполняем SQL скрипт из текущей директории
    sudo -u postgres psql -f "$(pwd)/init_db.sql"
else
    echo "Ошибка: Файл init_db.sql не найден в текущей директории"
    exit 1
fi

# Создание виртуального окружения
echo "Настройка Python окружения..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Создание .env файла если его нет
if [ ! -f ".env" ]; then
    echo "Создание .env файла..."
    cp .env.example .env
    echo "Пожалуйста, заполните данные в файле .env"
fi

# Создание директории для логов
echo "Создание директории для логов..."
sudo mkdir -p /var/log/sales_bot
sudo chown $USER:$USER /var/log/sales_bot

echo "Инициализация завершена!"
echo "Для запуска бота:"
echo "1. Заполните данные в файле .env"
echo "2. Запустите ./run.sh"
