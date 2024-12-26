-- Create Schema Versioning Table
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    description TEXT
);

-- Check current schema version before applying changes
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_version WHERE version = 1) THEN

        -- Marker Icon Table
        CREATE TABLE marker_icon (
            id SERIAL PRIMARY KEY,
            colour VARCHAR(50) NOT NULL,
            icon VARCHAR(50) NOT NULL,
            prefix VARCHAR(50) NOT NULL,
            UNIQUE (colour, icon, prefix)
        );

        -- Marker Table
        CREATE TABLE marker (
            id SERIAL PRIMARY KEY,
            name VARCHAR(500) NOT NULL,
            latitude FLOAT NOT NULL,
            longitude FLOAT NOT NULL,
            icon_id INTEGER REFERENCES marker_icon(id) DEFAULT 0
        );

        -- Place Table
        CREATE TABLE place (
            id SERIAL PRIMARY KEY,
            link VARCHAR(800) NOT NULL,
            latitude FLOAT NOT NULL,
            longitude FLOAT NOT NULL,
            name VARCHAR(150) NOT NULL DEFAULT 'Unknown',
            open_time TIME,
            close_time TIME,
            marker_id INTEGER REFERENCES marker(id),
            UNIQUE (link)
        );

        -- Insert Initial Version Record
        INSERT INTO schema_version (version, description) VALUES (1, 'Initial schema creation');

    END IF;
END $$;
