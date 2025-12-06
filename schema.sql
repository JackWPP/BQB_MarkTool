-- Database Schema for BUCT Tagger (SQLite Version)

CREATE TABLE IF NOT EXISTS photos (
    uuid TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    original_path TEXT,
    processed_path TEXT,
    thumb_path TEXT,
    width INTEGER,
    height INTEGER,
    
    -- Attributes
    campus TEXT,
    season TEXT,
    category TEXT,
    
    -- Keywords (Stored as JSON array string: '["a", "b"]')
    keywords TEXT,
    
    -- Meta info (Stored as JSON string)
    meta TEXT,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    annotated_at DATETIME
);

-- Indexes for faster searching
CREATE INDEX IF NOT EXISTS idx_photos_campus ON photos(campus);
CREATE INDEX IF NOT EXISTS idx_photos_season ON photos(season);
CREATE INDEX IF NOT EXISTS idx_photos_category ON photos(category);
