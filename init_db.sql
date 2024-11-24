-- Drop existing database and user if they exist
DROP DATABASE IF EXISTS sales_bot;
DROP USER IF EXISTS sales_bot;

-- Create user and database
CREATE USER sales_bot WITH PASSWORD 'sales_bot';
CREATE DATABASE sales_bot OWNER sales_bot;

-- Connect to the new database
\c sales_bot

-- Create tables
CREATE TABLE dialogs (
    id BIGSERIAL PRIMARY KEY,
    target_username TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    dialog_id BIGINT REFERENCES dialogs(id),
    direction TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Grant privileges
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sales_bot;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sales_bot;
