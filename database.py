import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_name='plantations.db'):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row  
        return conn
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create plantations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plantations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number TEXT NOT NULL,
                name TEXT NOT NULL,
                date_created TEXT NOT NULL
            )
        ''')
        
        # Insert sample data if empty
        cursor.execute('SELECT COUNT(*) FROM plantations')
        if cursor.fetchone()[0] == 0:
            sample_data = [
                ('01', 'PLANTATION LETTUCE', '18/12/2025'),
                ('02', 'PLANTATION BOKCHOY', '20/12/2025'),
                ('03', 'PLANTATION KALE', '20/12/2025'),
                ('04', 'PLANTATION SPINACH', '22/12/2025'),
                ('05', 'PLANTATION CARROT', '25/12/2025')
            ]
            cursor.executemany(
                'INSERT INTO plantations (number, name, date_created) VALUES (?, ?, ?)',
                sample_data
            )
        
        conn.commit()
        conn.close()

class Plantation:
    def __init__(self, id, number, name, date_created):
        self.id = id
        self.number = number
        self.name = name
        self.date_created = date_created
    
    @staticmethod
    def get_all():
        db = Database()
        conn = db.get_connection()

        rows = conn.execute("""
            SELECT id, number, name, date_created
            FROM plantations
            WHERE is_deleted = 0
            ORDER BY id
        """).fetchall()

        conn.close()
        return [Plantation(row[0], row[1], row[2], row[3]) for row in rows]

    @staticmethod
    def get_by_id(plantation_id):
        db = Database()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM plantations WHERE id = ?', (plantation_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Plantation(row[0], row[1], row[2], row[3])
        return None
    
    def update(self):
        db = Database()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE plantations SET number=?, name=?, date_created=? WHERE id=?',
            (self.number, self.name, self.date_created, self.id)
        )
        conn.commit()
        conn.close()
    
    @staticmethod
    def delete(plantation_id):
        db = Database()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM plantations WHERE id = ?', (plantation_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_deleted():
        db = Database()
        conn = db.get_connection()
        rows = conn.execute(
            "SELECT * FROM plantations WHERE is_deleted = 1"
        ).fetchall()
        conn.close()

        return [Plantation(row[0], row[1], row[2], row[3]) for row in rows]
