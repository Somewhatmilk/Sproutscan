import sqlite3
from werkzeug.security import generate_password_hash

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
        
        # --- PLANTATIONS TABLE ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plantations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number TEXT NOT NULL,
                name TEXT NOT NULL,
                date_created TEXT NOT NULL,
                is_deleted INTEGER DEFAULT 0,
                date_deleted TEXT
            )
        ''')

        # --- USERS TABLE (New) ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                name TEXT NOT NULL,
                bio TEXT,
                avatar_color TEXT
            )
        ''')
        
        # Seed Plantations
        cursor.execute('SELECT COUNT(*) FROM plantations')
        if cursor.fetchone()[0] == 0:
            sample_data = [
                ('01', 'PLANTATION LETTUCE', '18/12/2025', 0, None),
                ('02', 'PLANTATION BOKCHOY', '20/12/2025', 0, None)
            ]
            cursor.executemany(
                'INSERT INTO plantations (number, name, date_created, is_deleted, date_deleted) VALUES (?, ?, ?, ?, ?)',
                sample_data
            )

        # Seed Users
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            users_data = [
                ('admin', '123', 'admin', 'System Admin', 'Full Hardware Access & User Mgmt', '#c0392b'),
                ('jane', '123', 'expert', 'Jane Doe', 'Senior Agronomist / Analyst', '#2980b9'),
                ('john', '123', 'farmer', 'Farmer John', 'Field Operations Specialist', '#27ae60')
            ]
            cursor.executemany(
                'INSERT INTO users (username, password, role, name, bio, avatar_color) VALUES (?, ?, ?, ?, ?, ?)',
                users_data
            )
        users_data = [
            ('admin', generate_password_hash('123'), 'admin', 'System Admin', 'Full Hardware Access & User Mgmt', '#c0392b'),
            ('jane', generate_password_hash('123'), 'expert', 'Jane Doe', 'Senior Agronomist / Analyst', '#2980b9'),
            ('john', generate_password_hash('123'), 'farmer', 'Farmer John', 'Field Operations Specialist', '#27ae60')
            ]
        conn.commit()
        conn.close()

class Plantation:
    def __init__(self, id, number, name, date_created, is_deleted=0, date_deleted=None):
        self.id = id
        self.number = number
        self.name = name
        self.date_created = date_created
        self.is_deleted = is_deleted
        self.date_deleted = date_deleted
    
    @staticmethod
    def get_all():
        db = Database()
        conn = db.get_connection()
        rows = conn.execute("SELECT * FROM plantations WHERE is_deleted = 0 ORDER BY id").fetchall()
        conn.close()
        return [Plantation(**dict(row)) for row in rows]

    @staticmethod
    def get_by_id(plantation_id):
        db = Database()
        conn = db.get_connection()
        row = conn.execute('SELECT * FROM plantations WHERE id = ?', (plantation_id,)).fetchone()
        conn.close()
        return Plantation(**dict(row)) if row else None
    
    def update(self):
        db = Database()
        conn = db.get_connection()
        conn.execute(
            'UPDATE plantations SET number=?, name=?, date_created=? WHERE id=?',
            (self.number, self.name, self.date_created, self.id)
        )
        conn.commit()
        conn.close()

class User:
    def __init__(self, id, username, password, role, name, bio, avatar_color):
        self.id = id
        self.username = username
        self.password = password
        self.role = role
        self.name = name
        self.bio = bio
        self.avatar_color = avatar_color

    @staticmethod
    def get_by_username(username):
        db = Database()
        conn = db.get_connection()
        row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        return User(**dict(row)) if row else None
    
    @staticmethod
    def get_all():
        db = Database()
        conn = db.get_connection()
        rows = conn.execute('SELECT * FROM users').fetchall()
        conn.close()
        return [User(**dict(row)) for row in rows]

    @staticmethod
    def create(username, password, role, name, bio, color):
        db = Database()
        conn = db.get_connection()
        hashed_pw = generate_password_hash(password) 
        try:
            conn.execute(
                'INSERT INTO users (username, password, role, name, bio, avatar_color) VALUES (?, ?, ?, ?, ?, ?)',
                (username, hashed_pw, role, name, bio, color)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError: 
            return False
        finally:
            conn.close()

    @staticmethod
    def delete(user_id):
        db = Database()
        conn = db.get_connection()
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()