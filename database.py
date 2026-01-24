import sqlite3
from werkzeug.security import generate_password_hash
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
        
        # 1. PLANTATIONS
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


        try:
            cursor.execute("ALTER TABLE plantations ADD COLUMN last_updated TEXT")
            print("MIGRATION SUCCESS: Added 'last_updated' column.")
        except sqlite3.OperationalError:
            pass # Column already exists, ignore error


        # 2. USERS  
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

        # 3. INCIDENT LOGS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pest_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plantation_id INTEGER NOT NULL,
                issue TEXT NOT NULL,
                category TEXT DEFAULT 'Other',
                severity TEXT NOT NULL, 
                reporter_name TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                remarks TEXT,
                resolved INTEGER DEFAULT 0,
                FOREIGN KEY (plantation_id) REFERENCES plantations (id)
            )
        ''')
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crop_name TEXT NOT NULL,
                category TEXT NOT NULL,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cropstage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crop_id INTEGER NOT NULL,
                stage_name TEXT NOT NULL,
                expected_days INTEGER,
                ai_confidence INTEGER,
                status TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (crop_id) REFERENCES crops(id)
            )
        """)

        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            default_pw = generate_password_hash('123')
            users_data = [
                ('admin', 'admin@agriscan.com', default_pw, 'admin', 'System Admin', 'Full Access', '#c0392b'),
                ('jane', 'jane@agriscan.com', default_pw, 'expert', 'Jane Doe', 'Agronomist', '#2980b9'),
                ('john', 'john@agriscan.com', default_pw, 'farmer', 'Farmer John', 'Field Op', '#27ae60')
            ]
            cursor.executemany(
                'INSERT INTO users (username, email, password, role, name, bio, avatar_color) VALUES (?, ?, ?, ?, ?, ?, ?)',
                users_data
            )
            print("Default users seeded.")

        conn.commit()
        conn.close()

class Plantation:
    # UPDATED: Use **kwargs to prevent AttributeError if DB schema creates new columns
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.number = kwargs.get('number')
        self.name = kwargs.get('name')
        self.date_created = kwargs.get('date_created') or datetime.now().strftime("%d/%m/%Y")
        self.last_updated = kwargs.get('last_updated')
        self.is_deleted = kwargs.get('is_deleted', 0)
        self.date_deleted = kwargs.get('date_deleted')
        
        # Virtual Property for status
        self._status = None 

    @property
    def status(self):
        """Dynamic Status based on active High Severity tickets"""
        if self._status is None and self.id:
            db = Database()
            conn = db.get_connection()
            # Check for unresolved HIGH severity tickets
            row = conn.execute('''
                SELECT COUNT(*) FROM pest_logs 
                WHERE plantation_id = ? AND resolved = 0 AND severity = 'High'
            ''', (self.id,)).fetchone()
            conn.close()
            
            if row and row[0] > 0:
                self._status = 'Error'
            else:
                self._status = 'Online'
        return self._status

    def save(self):
        db = Database()
        conn = db.get_connection()
        if self.id:
            current_time = datetime.now().strftime("%d/%m/%Y %H:%M")
            conn.execute(
                'UPDATE plantations SET number=?, name=?, date_created=?, last_updated=? WHERE id=?',
                (self.number, self.name, self.date_created, current_time, self.id)
            )
        else:
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
            rows = conn.execute("SELECT * FROM plantations WHERE is_deleted = 1 ORDER BY date_deleted DESC").fetchall()
   
        elif search_query:
            q = f"%{search_query}%"
            rows = conn.execute(
                "SELECT * FROM plantations WHERE is_deleted = 0 AND (name LIKE ? OR number LIKE ?) ORDER BY id", 
                (q, q)
            ).fetchall()
        else:
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
    # UPDATED: Use **kwargs to safely handle 'mfa_secret' existence
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.username = kwargs.get('username')
        self.email = kwargs.get('email', '')
        self.password = kwargs.get('password')
        self.role = kwargs.get('role')
        self.name = kwargs.get('name')
        self.bio = kwargs.get('bio')
        self.avatar_color = kwargs.get('avatar_color')
        self.mfa_secret = kwargs.get('mfa_secret')

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

class IncidentLog:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.plantation_id = kwargs.get('plantation_id')
        self.issue = kwargs.get('issue')
        self.category = kwargs.get('category', 'Other') 
        self.severity = kwargs.get('severity')
        self.reporter_name = kwargs.get('reporter_name')
        self.entry_time = kwargs.get('entry_time') or datetime.now().strftime('%Y-%m-%d %H:%M')
        self.remarks = kwargs.get('remarks')
        self.resolved = kwargs.get('resolved', 0)

    def save(self):
        db = Database()
        conn = db.get_connection()
        
        # Robust column check
        try:
            conn.execute("ALTER TABLE pest_logs ADD COLUMN category TEXT DEFAULT 'Other'")
        except:
            pass 

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
        db = Database()
        conn = db.get_connection()
        sql = '''
            SELECT p.*, f.name as farm_name 
            FROM pest_logs p 
            JOIN plantations f ON p.plantation_id = f.id 
            WHERE p.resolved = 0 
            ORDER BY p.severity = 'High' DESC, p.entry_time DESC
        '''
        rows = conn.execute(sql).fetchall()
        conn.close()
        return rows 
    
    @staticmethod
    def get_by_plantation(plantation_id):
        db = Database()
        conn = db.get_connection()
        rows = conn.execute('SELECT * FROM pest_logs WHERE plantation_id = ? ORDER BY entry_time DESC', (plantation_id,)).fetchall()
        conn.close()
        return [IncidentLog(**dict(row)) for row in rows]

class Crop:
    @staticmethod
    def get_all_with_stages():
        db = Database()
        conn = db.get_connection()
        rows = conn.execute("""
            SELECT
                c.id,
                c.crop_name,
                c.category,
                c.notes,
                COALESCE(cs.stage_name, '') AS stage_name,
                COALESCE(cs.expected_days, '') AS expected_days,
                COALESCE(cs.ai_confidence, '') AS ai_confidence,
                COALESCE(cs.status, '') AS status
            FROM crops c
            LEFT JOIN cropstage cs
              ON cs.id = (
                SELECT id
                FROM cropstage
                WHERE crop_id = c.id
                ORDER BY created_at DESC, id DESC
                LIMIT 1
              )
            ORDER BY c.id DESC
        """).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def create(name, category, notes):
        db = Database()
        conn = db.get_connection()
        conn.execute(
            "INSERT INTO crops (crop_name, category, notes) VALUES (?, ?, ?)",
            (name, category, notes)
        )
        conn.commit()
        conn.close()
    
    @staticmethod
    def delete(crop_id):
        db = Database()
        conn = db.get_connection()
        conn.execute("DELETE FROM cropstage WHERE crop_id = ?", (crop_id,))
        conn.execute("DELETE FROM crops WHERE id = ?", (crop_id,))
        conn.commit()
        conn.close()