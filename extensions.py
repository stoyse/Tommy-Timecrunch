import sqlite3

def get_db_connection():
    """Get a connection to the SQLite database"""
    conn = sqlite3.connect('hackathons.db')
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn
