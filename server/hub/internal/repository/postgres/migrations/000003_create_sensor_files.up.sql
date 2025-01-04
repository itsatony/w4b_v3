CREATE TABLE IF NOT EXISTS sensor_files (
    id TEXT PRIMARY KEY,
    hive_id TEXT NOT NULL REFERENCES hives(id) ON DELETE CASCADE,
    sensor_id TEXT NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    path TEXT NOT NULL,
    size BIGINT NOT NULL,
    mime_type TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT sensor_files_type_check CHECK (type IN ('image', 'sound'))
);

CREATE INDEX idx_sensor_files_hive_id ON sensor_files(hive_id);
CREATE INDEX idx_sensor_files_sensor_id ON sensor_files(sensor_id);
CREATE INDEX idx_sensor_files_type ON sensor_files(type);
CREATE INDEX idx_sensor_files_timestamp ON sensor_files(timestamp);
