-- Создание базы данных
CREATE DATABASE sales_bot;

-- Подключение к базе
\c sales_bot

-- Создание таблиц
CREATE TABLE dialogs (
    id BIGSERIAL PRIMARY KEY,
    target_username TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    dialog_id BIGINT REFERENCES dialogs(id),
    direction TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание индексов
CREATE INDEX idx_messages_dialog_id ON messages(dialog_id);
CREATE INDEX idx_dialogs_status ON dialogs(status);
CREATE INDEX idx_dialogs_username ON dialogs(target_username);
