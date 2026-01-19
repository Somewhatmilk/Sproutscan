import sqlite3
from werkzeug.security import generate_password_hash
from datetime import datetime

from cropstage import cropstage

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
        
        # --- 1. PLANTATIONS TABLE ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plantations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number TEXT NOT NULL,
                name TEXT NOT NULL,
                date_created TEXT NOT NULL,
                last_updated TEXT, 
                is_deleted INTEGER DEFAULT 0,
                date_deleted TEXT
            )
        ''')

        # 2. USERS TABLE (Kept from Primary)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                name TEXT NOT NULL,
                bio TEXT,
                avatar_color TEXT,
                mfa_secret TEXT  
            )
        ''')

        # --- 3. PEST LOGS TABLE (NEW FEATURE) ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pest_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plantation_id INTEGER NOT NULL,
                issue TEXT NOT NULL,
                severity TEXT NOT NULL, 
                reporter_name TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                remarks TEXT,
                resolved INTEGER DEFAULT 0,
                FOREIGN KEY (plantation_id) REFERENCES plantations (id)
            )
        ''')
        
        # cropstage.py
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                name TEXT,
                role TEXT,
                avatar_color TEXT
            )
        """)

        # Seed Admin if not exists
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            default_pw = generate_password_hash('123')
            # Seeding basic users
            users_data = [
                ('admin', 'admin@agriscan.com', default_pw, 'admin', 'System Admin', 'Full Hardware Access & User Mgmt', '#c0392b'),
                ('jane', 'jane@agriscan.com', default_pw, 'expert', 'Jane Doe', 'Senior Agronomist / Analyst', '#2980b9'),
                ('john', 'john@agriscan.com', default_pw, 'farmer', 'Farmer John', 'Field Operations Specialist', '#27ae60')
            ]
            cursor.executemany(
                'INSERT INTO users (username, email, password, role, name, bio, avatar_color) VALUES (?, ?, ?, ?, ?, ?, ?)',
                users_data
            )
            
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            users_data = [
                ('admin', 'System Admin', 'admin', '#c0392b'),
                ('jane', 'Jane Doe', 'expert', '#2980b9'),
                ('john', 'Farmer John', 'farmer', '#27ae60')
            ]
            conn.executemany(
                "INSERT INTO users (username, name, role, avatar_color) VALUES (?, ?, ?, ?)", 
                users_data
            )
        conn.commit()
        conn.close()

class Plantation:
    def __init__(self, id=None, number=None, name=None, date_created=None, last_updated=None, is_deleted=0, date_deleted=None):
        self.id = id
        self.number = number
        self.name = name
        self.date_created = date_created or datetime.now().strftime("%d/%m/%Y")
        self.last_updated = last_updated
        self.is_deleted = is_deleted
        self.date_deleted = date_deleted
    
    def save(self):
        """Modified: Handles Insert OR Update with Timestamp"""
        db = Database()
        conn = db.get_connection()
        if self.id:
            # Update Logic
            current_time = datetime.now().strftime("%d/%m/%Y %H:%M")
            conn.execute(
                'UPDATE plantations SET number=?, name=?, date_created=?, last_updated=? WHERE id=?',
                (self.number, self.name, self.date_created, current_time, self.id)
            )
        else:
            # Insert Logic
            conn.execute(
                'INSERT INTO plantations (number, name, date_created) VALUES (?, ?, ?)',
                (self.number, self.name, self.date_created)
            )
        conn.commit()
        conn.close()

    def soft_delete(self):
        db = Database()
        conn = db.get_connection()
        conn.execute(
            "UPDATE plantations SET is_deleted = 1, date_deleted = ? WHERE id = ?",
            (datetime.now().strftime("%d/%m/%Y"), self.id)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def permanent_delete(plantation_id):
        """New: From Secondary Version"""
        db = Database()
        conn = db.get_connection()
        conn.execute("DELETE FROM plantations WHERE id = ?", (plantation_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def restore(plantation_id):
        db = Database()
        conn = db.get_connection()
        conn.execute("UPDATE plantations SET is_deleted = 0, date_deleted = NULL WHERE id = ?", (plantation_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_all(search_query=None, include_deleted=False):
        db = Database()
        conn = db.get_connection()
        
        if include_deleted:
            # Logic for Deleted Farms Page
            rows = conn.execute("SELECT * FROM plantations WHERE is_deleted = 1 ORDER BY date_deleted DESC").fetchall()
        elif search_query:
            # Logic for Dashboard Search
            q = f"%{search_query}%"
            rows = conn.execute(
                "SELECT * FROM plantations WHERE is_deleted = 0 AND (name LIKE ? OR number LIKE ?) ORDER BY id", 
                (q, q)
            ).fetchall()
        else:
            # Default Logic (Show all active)
            rows = conn.execute("SELECT * FROM plantations WHERE is_deleted = 0 ORDER BY id").fetchall()
            
        conn.close()
        return [Plantation(**dict(row)) for row in rows]
    
    @staticmethod
    def get_by_id(pid):
        db = Database()
        conn = db.get_connection()
        row = conn.execute("SELECT * FROM plantations WHERE id=?", (pid,)).fetchone()
        conn.close()
        return Plantation(**dict(row)) if row else None

class User:
    def __init__(self, id, username, password, role, name, bio, avatar_color, email="", mfa_secret=None):
        self.id = id
        self.username = username
        self.email = email
        self.password = password
        self.role = role
        self.name = name
        self.bio = bio
        self.avatar_color = avatar_color
        self.mfa_secret = mfa_secret

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
    def create(username, email, password, role, name, bio, color):
        db = Database()
        conn = db.get_connection()
        hashed_pw = generate_password_hash(password) 
        try:
            conn.execute(
                'INSERT INTO users (username, email, password, role, name, bio, avatar_color, mfa_secret) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (username, email, hashed_pw, role, name, bio, color, None)
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

class PestLog:
    def __init__(self, id=None, plantation_id=None, issue=None, severity="Medium", reporter_name=None, entry_time=None, remarks=None, resolved=0):
        self.id = id
        self.plantation_id = plantation_id
        self.issue = issue
        self.severity = severity
        self.reporter_name = reporter_name
        self.entry_time = entry_time or datetime.now().strftime('%Y-%m-%d %H:%M')
        self.remarks = remarks
        self.resolved = resolved

    def save(self):
        db = Database()
        conn = db.get_connection()
        if self.id:
            conn.execute('UPDATE pest_logs SET issue=?, severity=?, resolved=?, remarks=? WHERE id=?', 
                         (self.issue, self.severity, self.resolved, self.remarks, self.id))
        else:
            conn.execute('INSERT INTO pest_logs (plantation_id, issue, severity, reporter_name, entry_time, remarks, resolved) VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (self.plantation_id, self.issue, self.severity, self.reporter_name, self.entry_time, self.remarks, self.resolved))
        conn.commit()
        conn.close()

    @staticmethod
    def get_by_plantation(plantation_id):
        db = Database()
        conn = db.get_connection()
        rows = conn.execute('SELECT * FROM pest_logs WHERE plantation_id = ? ORDER BY entry_time DESC', (plantation_id,)).fetchall()
        conn.close()
        return [PestLog(**dict(row)) for row in rows]
    
 

class IncidentLog: # Renamed from PestLog to be more generic
    def __init__(self, id=None, plantation_id=None, issue=None, category="Other", severity="Medium", reporter_name=None, entry_time=None, remarks=None, resolved=0):
        self.id = id
        self.plantation_id = plantation_id
        self.issue = issue
        self.category = category # Added this field
        self.severity = severity
        self.reporter_name = reporter_name
        self.entry_time = entry_time or datetime.now().strftime('%Y-%m-%d %H:%M')
        self.remarks = remarks
        self.resolved = resolved

    def save(self):
        db = Database()
        conn = db.get_connection()
        
        # Ensure table exists with new column (Quick migration hack for SQLite)
        try:
            conn.execute("ALTER TABLE pest_logs ADD COLUMN category TEXT DEFAULT 'Other'")
        except:
            pass # Column likely exists

        if self.id:
            conn.execute('''
                UPDATE pest_logs 
                SET issue=?, category=?, severity=?, resolved=?, remarks=? 
                WHERE id=?''', 
                (self.issue, self.category, self.severity, self.resolved, self.remarks, self.id))
        else:
            conn.execute('''
                INSERT INTO pest_logs (plantation_id, issue, category, severity, reporter_name, entry_time, remarks, resolved) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (self.plantation_id, self.issue, self.category, self.severity, self.reporter_name, self.entry_time, self.remarks, self.resolved))
        conn.commit()
        conn.close()

    @staticmethod
    def get_all_active():
        """New method to get all open tickets for the global maintenance page"""
        db = Database()
        conn = db.get_connection()
        # JOIN to get farm name
        sql = '''
            SELECT p.*, f.name as farm_name 
            FROM pest_logs p 
            JOIN plantations f ON p.plantation_id = f.id 
            WHERE p.resolved = 0 
            ORDER BY p.severity = 'High' DESC, p.entry_time DESC
        '''
        rows = conn.execute(sql).fetchall()
        conn.close()
        return rows # Returns dictionaries