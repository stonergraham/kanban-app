"""
Migration: Add deadline column to cards table.
Run once from the project root: python migrate_add_deadline.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'kanban.db')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check if column already exists
cursor.execute("PRAGMA table_info(cards)")
columns = [row[1] for row in cursor.fetchall()]

if 'deadline' not in columns:
    cursor.execute("ALTER TABLE cards ADD COLUMN deadline DATE")
    conn.commit()
    print("✅ Added 'deadline' column to cards table.")
else:
    print("ℹ️  'deadline' column already exists, skipping.")

conn.close()
