import sqlite3
import sys

def migrate():
    try:
        conn = sqlite3.connect('chat_server.db')
        cursor = conn.cursor()
        cursor.execute('ALTER TABLE statuses ADD COLUMN parent_id INTEGER REFERENCES statuses(id);')
        cursor.execute('ALTER TABLE statuses ADD COLUMN moment_type VARCHAR DEFAULT "WORK";')
        cursor.execute('ALTER TABLE statuses ADD COLUMN audience VARCHAR DEFAULT "FRIENDS";')
        cursor.execute('ALTER TABLE statuses ADD COLUMN duration_type VARCHAR DEFAULT "FIXED_DURATION";')
        cursor.execute('ALTER TABLE statuses ADD COLUMN duration_value VARCHAR;')
        conn.commit()
        conn.close()
        print('DB Altered successfully!')
    except Exception as e:
        print('Error:', e)
        sys.exit(1)

if __name__ == '__main__':
    migrate()
