#!/bin/bash

# Проверка наличия необходимых переменных окружения
if [ -z "$DEPLOY_HOST" ] || [ -z "$DEPLOY_USER" ]; then
    echo "Ошибка: Установите переменные DEPLOY_HOST и DEPLOY_USER"
    exit 1
fi

# Директории
REMOTE_DIR="/opt/sales_bot"
LOG_DIR="/var/log/sales_bot"
VENV_DIR="$REMOTE_DIR/venv"

echo "Начинаем деплой на $DEPLOY_HOST..."

# Создание необходимых директорий
ssh $DEPLOY_USER@$DEPLOY_HOST << 'EOF'
    # Создание директорий
    sudo mkdir -p /opt/sales_bot
    sudo mkdir -p /var/log/sales_bot

    # Настройка прав
    sudo chown -R $USER:$USER /opt/sales_bot
    sudo chown -R $USER:$USER /var/log/sales_bot

    # Установка системных зависимостей
    sudo apt-get update
    sudo apt-get install -y python3-venv python3-pip postgresql postgresql-contrib
EOF

# Копирование файлов проекта
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '.env' \
    ./sales_bot/ $DEPLOY_USER@$DEPLOY_HOST:$REMOTE_DIR/

# Настройка виртуального окружения и установка зависимостей
ssh $DEPLOY_USER@$DEPLOY_HOST << EOF
    cd $REMOTE_DIR

    # Создание виртуального окружения
    python3 -m venv $VENV_DIR
    source $VENV_DIR/bin/activate

    # Установка зависимостей
    pip install -r requirements.txt

    # Копирование .env файла если его нет
    if [ ! -f .env ]; then
        cp .env.example .env
        echo "Создан .env файл. Пожалуйста, настройте его!"
    fi
EOF

# Создание systemd сервиса
cat << EOF | ssh $DEPLOY_USER@$DEPLOY_HOST "sudo tee /etc/systemd/system/sales_bot.service"
[Unit]
Description=Sales Bot
After=network.target postgresql.service

[Service]
Type=simple
User=$DEPLOY_USER
WorkingDirectory=$REMOTE_DIR
Environment=PATH=$VENV_DIR/bin
ExecStart=$VENV_DIR/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Настройка и запуск сервиса
ssh $DEPLOY_USER@$DEPLOY_HOST << 'EOF'
    # Перезагрузка systemd
    sudo systemctl daemon-reload

    # Включение и запуск сервиса
    sudo systemctl enable sales_bot
    sudo systemctl restart sales_bot

    # Проверка статуса
    sudo systemctl status sales_bot
EOF

echo "Деплой завершен!"
