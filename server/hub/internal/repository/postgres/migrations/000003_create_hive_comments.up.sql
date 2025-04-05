CREATE TABLE IF NOT EXISTS hive_comments (
    id VARCHAR(20) PRIMARY KEY,
    hive_id VARCHAR(20) NOT NULL REFERENCES hives(id) ON DELETE CASCADE,
    user_id VARCHAR(36) NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_hive_comments_hive_id ON hive_comments(hive_id);
CREATE INDEX idx_hive_comments_created_at ON hive_comments(created_at);
