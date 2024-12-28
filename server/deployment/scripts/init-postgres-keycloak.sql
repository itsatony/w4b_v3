# /server/deployment/scripts/init-postgres-keycloak.sql

-- Keycloak will handle its own schema initialization
-- This file is for any additional customizations or extensions

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create custom audit schema for additional logging
CREATE SCHEMA IF NOT EXISTS keycloak_audit;

-- Create audit table for custom events
CREATE TABLE IF NOT EXISTS keycloak_audit.custom_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,
    realm_id TEXT,
    user_id TEXT,
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_custom_events_type 
    ON keycloak_audit.custom_events(event_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_custom_events_realm 
    ON keycloak_audit.custom_events(realm_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_custom_events_user 
    ON keycloak_audit.custom_events(user_id, timestamp DESC);