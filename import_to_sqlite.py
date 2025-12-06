import sqlite3
import json
import sys
import os
from datetime import datetime

DB_FILE = "buct_gallery.db"
SCHEMA_FILE = "schema.sql"

def init_db():
    """Initialize the database with schema."""
    if not os.path.exists(SCHEMA_FILE):
        print(f"Error: {SCHEMA_FILE} not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    
    try:
        cursor.executescript(sql_script)
        conn.commit()
        print(f"Database initialized: {DB_FILE}")
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        conn.close()

def import_json(json_path):
    """Import validated JSON data into SQLite."""
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    count = 0
    for item in data:
        try:
            # Extract fields
            uuid_str = item.get("uuid")
            filename = item.get("filename")
            original_path = item.get("original_path")
            processed_path = item.get("processed_path")
            thumb_path = item.get("thumb_path")
            width = item.get("width")
            height = item.get("height")

            tags = item.get("tags", {})
            attrs = tags.get("attributes", {})
            campus = attrs.get("campus")
            season = attrs.get("season")
            category = attrs.get("category")

            # JSON serialization for lists/dicts
            keywords = json.dumps(tags.get("keywords", []), ensure_ascii=False)
            meta = json.dumps(tags.get("meta", {}), ensure_ascii=False)
            
            # Timestamp
            annotated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Upsert (Insert or Replace)
            cursor.execute("""
                INSERT OR REPLACE INTO photos (
                    uuid, filename, original_path, processed_path, thumb_path, 
                    width, height, campus, season, category, keywords, meta, annotated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uuid_str, filename, original_path, processed_path, thumb_path,
                width, height, campus, season, category, keywords, meta, annotated_at
            ))
            
            count += 1
        except Exception as e:
            print(f"Error inserting item {item.get('uuid')}: {e}")

    conn.commit()
    conn.close()
    print(f"Successfully imported {count} items into {DB_FILE}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_to_sqlite.py [init|import <json_file>]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        init_db()
    elif command == "import":
        if len(sys.argv) < 3:
            print("Usage: python import_to_sqlite.py import <json_file>")
        else:
            import_json(sys.argv[2])
    else:
        print("Unknown command.")
