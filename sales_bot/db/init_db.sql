-- Drop existing database and user if they exist
DROP DATABASE IF EXISTS sales_bot;
DROP USER IF EXISTS sales_bot;

-- Create user and database
CREATE USER sales_bot WITH PASSWORD 'sales_bot';
CREATE DATABASE sales_bot OWNER sales_bot;

-- Connect to the new database
\c sales_bot

-- Create enum types
CREATE TYPE account_status AS ENUM ('active', 'disabled', 'blocked');
CREATE TYPE dialog_status AS ENUM ('active', 'qualified', 'stopped', 'failed');
CREATE TYPE message_direction AS ENUM ('in', 'out');

-- Create tables
CREATE TABLE accounts (
    id BIGSERIAL PRIMARY KEY,
    phone TEXT NOT NULL UNIQUE,
    session_string TEXT,
    status account_status NOT NULL DEFAULT 'active',
    last_used TIMESTAMP WITH TIME ZONE,
    last_warmup TIMESTAMP WITH TIME ZONE,
    daily_messages INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dialogs (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT REFERENCES accounts(id),
    target_username TEXT NOT NULL,
    status dialog_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    dialog_id BIGINT REFERENCES dialogs(id),
    direction message_direction NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_accounts_status_messages ON accounts(status, daily_messages)
WHERE status = 'active';

CREATE INDEX idx_accounts_warmup ON accounts(status, last_warmup)
WHERE status = 'active';

CREATE INDEX idx_dialogs_status ON dialogs(status)
WHERE status = 'active';

CREATE INDEX idx_messages_dialog_time ON messages(dialog_id, timestamp);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
CREATE TRIGGER update_accounts_updated_at
    BEFORE UPDATE ON accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_dialogs_updated_at
    BEFORE UPDATE ON dialogs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant privileges
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sales_bot;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sales_bot;

-- Create function for resetting daily messages
CREATE OR REPLACE FUNCTION reset_daily_messages()
RETURNS void AS $$
BEGIN
    UPDATE accounts SET daily_messages = 0;
END;
$$ LANGUAGE plpgsql;

-- Add comments
COMMENT ON TABLE accounts IS 'Пользовательские аккаунты Telegram для отправки сообщений';
COMMENT ON TABLE dialogs IS 'Активные диалоги с целевыми пользователями';
COMMENT ON TABLE messages IS 'История сообщений в диалогах';

COMMENT ON COLUMN accounts.phone IS 'Номер телефона аккаунта';
COMMENT ON COLUMN accounts.session_string IS 'Строка сессии Pyrogram';
COMMENT ON COLUMN accounts.status IS 'Статус аккаунта: active, disabled, blocked';
COMMENT ON COLUMN accounts.daily_messages IS 'Количество сообщений за текущий день';
COMMENT ON COLUMN accounts.last_warmup IS 'Время последнего прогрева аккаунта';

COMMENT ON COLUMN dialogs.target_username IS 'Username целевого пользователя';
COMMENT ON COLUMN dialogs.status IS 'Статус диалога: active, qualified, stopped, failed';

COMMENT ON COLUMN messages.direction IS 'Направление сообщения: in (входящее), out (исходящее)';
