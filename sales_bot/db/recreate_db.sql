-- First, terminate all connections to the database
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = 'sales_bot'
AND pid <> pg_backend_pid();

-- Drop and recreate database
DROP DATABASE IF EXISTS sales_bot;
CREATE DATABASE sales_bot;

\c sales_bot;

-- Create ENUM types
CREATE TYPE accountstatus AS ENUM (
    'new',
    'code_requested',
    'password_requested',
    'active',
    'disabled',
    'blocked',
    'warming'
);

CREATE TYPE dialogstatus AS ENUM (
    'active',
    'qualified',
    'stopped',
    'failed'
);

CREATE TYPE messagedirection AS ENUM (
    'in',
    'out'
);

-- Create tables
CREATE TABLE accounts (
    id BIGSERIAL PRIMARY KEY,
    phone VARCHAR NOT NULL UNIQUE,
    session_string VARCHAR,
    status accountstatus NOT NULL DEFAULT 'new',
    flood_wait_until TIMESTAMP,
    last_used_at TIMESTAMP,
    last_warmup_at TIMESTAMP,
    messages_sent INTEGER DEFAULT 0,
    is_available BOOLEAN NOT NULL DEFAULT true,
    warmup_count INTEGER DEFAULT 0,
    ban_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dialogs (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT REFERENCES accounts(id),
    target_username VARCHAR NOT NULL,
    status dialogstatus NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    dialog_id BIGINT REFERENCES dialogs(id),
    direction messagedirection NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for query optimization
CREATE INDEX idx_accounts_status_messages ON accounts(status, messages_sent)
WHERE status = 'active';

CREATE INDEX idx_accounts_warmup ON accounts(status, last_warmup_at)
WHERE status = 'active';

CREATE INDEX idx_accounts_last_used ON accounts(status, last_used_at)
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

-- Create function for resetting daily messages
CREATE OR REPLACE FUNCTION reset_daily_messages()
RETURNS void AS $$
BEGIN
    UPDATE accounts SET messages_sent = 0;
END;
$$ LANGUAGE plpgsql;

-- Create status transition check trigger
CREATE OR REPLACE FUNCTION check_account_status_transition()
RETURNS TRIGGER AS $$
BEGIN
    -- If status doesn't change, skip check
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;

    -- Check allowed transitions
    IF (
        -- From new
        (OLD.status = 'new' AND NEW.status IN ('code_requested', 'blocked', 'warming')) OR

        -- From code_requested
        (OLD.status = 'code_requested' AND NEW.status IN ('new', 'password_requested', 'active', 'blocked')) OR

        -- From password_requested
        (OLD.status = 'password_requested' AND NEW.status IN ('new', 'active', 'blocked')) OR

        -- From active
        (OLD.status = 'active' AND NEW.status IN ('disabled', 'blocked')) OR

        -- From disabled
        (OLD.status = 'disabled' AND NEW.status IN ('active', 'blocked')) OR

        -- From blocked
        (OLD.status = 'blocked' AND NEW.status = 'new') OR

        -- From warming
        (OLD.status = 'warming' AND NEW.status IN ('active', 'blocked'))
    ) THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Invalid status transition from % to %', OLD.status, NEW.status;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for status transitions
CREATE TRIGGER account_status_transition_trigger
    BEFORE UPDATE OF status
    ON accounts
    FOR EACH ROW
    EXECUTE FUNCTION check_account_status_transition();

-- Grant privileges
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO postgres;
