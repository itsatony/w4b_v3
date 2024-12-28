# /server/deployment/scripts/init-postgres-app.sql

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create schemas
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS audit;

-- User preferences and settings
CREATE TABLE IF NOT EXISTS app.user_preferences (
    user_id UUID PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    settings JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Application configurations
CREATE TABLE IF NOT EXISTS app.configurations (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Audit logging
CREATE TABLE IF NOT EXISTS audit.events (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    user_id UUID,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    old_value JSONB,
    new_value JSONB,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON audit.events(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit.events(resource_type, resource_id, timestamp DESC);

-- Update trigger
CREATE OR REPLACE FUNCTION app.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_user_preferences_timestamp
    BEFORE UPDATE ON app.user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION app.update_updated_at();

CREATE TRIGGER update_configurations_timestamp
    BEFORE UPDATE ON app.configurations
    FOR EACH ROW
    EXECUTE FUNCTION app.update_updated_at();

-- Initial configurations
INSERT INTO app.configurations (key, value, description)
VALUES 
    ('email_notifications', 
     '{"enabled": true, "daily_digest": true}',
     'Global email notification settings'),
    ('monitoring_thresholds',
     '{"cpu_warning": 80, "memory_warning": 80, "disk_warning": 90}',
     'System monitoring thresholds')
ON CONFLICT (key) DO NOTHING;

