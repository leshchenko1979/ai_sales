#!/bin/bash

# Проверяем наличие виртуального окружения
if [ ! -d "venv" ]; then
    echo "Создаем виртуальное окружение..."
    python3 -m venv venv
fi

# Активируем виртуальное окружение
source venv/bin/activate

# Проверяем/устанавливаем зависимости
if [ ! -f "requirements.txt" ]; then
    echo "Ошибка: файл requirements.txt не найден"
    exit 1
fi

echo "Проверяем зависимости..."
pip install -r requirements.txt

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "Копируем .env.example в .env..."
    cp .env.example .env
    echo "Пожалуйста, настройте параметры в файле .env"
    exit 1
fi

# Останавливаем предыдущий процесс бота если он запущен
BOT_PID=$(pgrep -f "python.*main.py")
if [ ! -z "$BOT_PID" ]; then
    echo "Останавливаем предыдущий процесс бота (PID: $BOT_PID)..."
    kill $BOT_PID
    sleep 2
fi

# Запускаем бота
echo "Запускаем бота..."
python sales_bot/main.py
