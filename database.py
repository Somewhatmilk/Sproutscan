import sqlite3
from werkzeug.security import generate_password_hash
from datetime import datetime
from security import sec

 
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
                date_deleted TEXT,
                global_crop_id INTEGER
            )
        ''')


        try:
            cursor.execute("ALTER TABLE plantations ADD COLUMN last_updated TEXT")
            print("MIGRATION SUCCESS: Added 'last_updated' column.")
        except sqlite3.OperationalError:
            pass  

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS farm_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                type TEXT DEFAULT 'camera', 
                status TEXT DEFAULT 'Online',
                crop_id INTEGER,
                FOREIGN KEY (farm_id) REFERENCES plantations (id)
            )
        ''')
        try:
            cursor.execute("ALTER TABLE plantations ADD COLUMN global_crop_id INTEGER")
            print("Migrated: Added global_crop_id to plantations")
        except sqlite3.OperationalError: pass  

        try:
            cursor.execute("ALTER TABLE farm_zones ADD COLUMN crop_id INTEGER")
            print("Migrated: Added crop_id to farm_zones")
        except sqlite3.OperationalError: pass

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
            CREATE TABLE IF NOT EXISTS crops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crop_name TEXT NOT NULL,
                category TEXT NOT NULL,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # --- CROP STAGE TABLE ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cropstage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crop_id INTEGER NOT NULL,
                stage_name TEXT,
                expected_days INTEGER,
                ai_confidence REAL,
                status TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (crop_id) REFERENCES crops(id)
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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                remarks TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
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


        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pest_log_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number TEXT NOT NULL,
                name TEXT NOT NULL,
                date_created TEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pest_log_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_id INTEGER NOT NULL,
                plantation INTEGER NOT NULL,
                plant_name TEXT NOT NULL,
                issue TEXT NOT NULL,
                remarks TEXT,
                resolved TEXT DEFAULT 'No',
                staff_name TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                FOREIGN KEY (folder_id) REFERENCES pest_log_folders(id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        conn.close()

class FarmZone:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.farm_id = kwargs.get('farm_id')
        self.name = kwargs.get('name')
        self.type = kwargs.get('type')
        self.status = kwargs.get('status', 'Online')

    @staticmethod
    def get_by_farm(farm_id):
        db = Database()
        conn = db.get_connection()
        
      
        sql = """
            SELECT z.*, c.crop_name 
            FROM farm_zones z 
            LEFT JOIN crops c ON z.crop_id = c.id 
            WHERE z.farm_id=?
        """
        rows = conn.execute(sql, (farm_id,)).fetchall()
        results = [FarmZone(**dict(row)) for row in rows]
        
        # 2. PRESERVE YOUR ORIGINAL LOGIC: If no zones exist, seed defaults
        if not results:
            defaults = [
                ("Topic Area (Broad View)", "master"),
                ("Plantation Alpha", "camera"),
                ("Plantation Beta", "camera"),
                ("Nursery Sector", "camera"),
                ("Storage Feed", "camera")
            ]
            for name, ztype in defaults:
                # We seed with crop_id as NULL initially
                conn.execute("INSERT INTO farm_zones (farm_id, name, type) VALUES (?, ?, ?)", 
                             (farm_id, name, ztype))
            conn.commit()
            
            # 3. RE-FETCH after seeding to get the objects with the JOIN applied
            rows = conn.execute(sql, (farm_id,)).fetchall()
            results = [FarmZone(**dict(row)) for row in rows]
            
        conn.close()
        return results

     
    @staticmethod
    def set_zone_crop(zone_id, crop_id):
        db = Database()
        conn = db.get_connection()
        conn.execute("UPDATE farm_zones SET crop_id = ? WHERE id = ?", (crop_id, zone_id))
        conn.commit()
        conn.close()


    @staticmethod
    def get_by_id(zid):
        db = Database()
        conn = db.get_connection()
        row = conn.execute("SELECT * FROM farm_zones WHERE id=?", (zid,)).fetchone()
        conn.close()
        return FarmZone(**dict(row)) if row else None


class Crop:
    @staticmethod
    def get_all_with_stages():
        db = Database()
        conn = db.get_connection()
        # Complex query to get crop details plus the LATEST stage info
        rows = conn.execute("""
            SELECT
                c.id,
                c.id AS crop_id, -- Ensure compatibility
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

    @staticmethod
    def add_stage(crop_id, stage_name, expected_days=None):
        db = Database()
        conn = db.get_connection()
      
        conn.execute("""
            INSERT INTO cropstage (crop_id, stage_name, expected_days, status)
            VALUES (?, ?, 
                COALESCE(?, (SELECT expected_days FROM cropstage WHERE crop_id=? ORDER BY created_at DESC, id DESC LIMIT 1)), 
                COALESCE((SELECT status FROM cropstage WHERE crop_id=? ORDER BY created_at DESC, id DESC LIMIT 1), 'UNKNOWN'))
        """, (crop_id, stage_name, expected_days, crop_id, crop_id))
        conn.commit()
        conn.close()

class PestLogFolder:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.number = kwargs.get('number')
        self.name = kwargs.get('name')
        self.date_created = kwargs.get('date_created') or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def save(self):
        db = Database()
        conn = db.get_connection()
        if self.id:
            conn.execute('UPDATE pest_log_folders SET name=? WHERE id=?', (self.name, self.id))
        else:
            conn.execute('INSERT INTO pest_log_folders (number, name, date_created) VALUES (?, ?, ?)',
                         (self.number, self.name, self.date_created))
        conn.commit()
        # Get ID if new
        if not self.id:
            self.id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.close()
        return self

    @staticmethod
    def get_all():
        db = Database()
        conn = db.get_connection()
        rows = conn.execute("SELECT * FROM pest_log_folders ORDER BY id DESC").fetchall()
        conn.close()
        return [PestLogFolder(**dict(row)) for row in rows]

    @staticmethod
    def get_by_id(zid):
        db = Database()
        conn = db.get_connection()
        row = conn.execute("SELECT * FROM farm_zones WHERE id=?", (zid,)).fetchone()
        conn.close()
        return FarmZone(**dict(row)) if row else None
    
    @staticmethod
    def delete(fid):
        db = Database()
        conn = db.get_connection()
        conn.execute("DELETE FROM pest_log_entries WHERE folder_id=?", (fid,)) # Cascade manual
        conn.execute("DELETE FROM pest_log_folders WHERE id=?", (fid,))
        conn.commit()
        conn.close()

class PestLogEntry:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.folder_id = kwargs.get('folder_id')
        self.plantation = kwargs.get('plantation')
        self.plant_name = kwargs.get('plant_name')
        self.issue = kwargs.get('issue')
        self.remarks = kwargs.get('remarks', '')
        self.resolved = kwargs.get('resolved', 'No')
        self.staff_name = kwargs.get('staff_name')
        self.entry_time = kwargs.get('entry_time') or datetime.now().strftime("%d/%m/%Y %I:%M %p")
        
        # Virtual for display
        self.folder_name = kwargs.get('folder_name', '')

    def save(self):
        db = Database()
        conn = db.get_connection()
        if self.id:
            conn.execute('''
                UPDATE pest_log_entries 
                SET plantation=?, plant_name=?, issue=?, remarks=?, resolved=?
                WHERE id=?
            ''', (self.plantation, self.plant_name, self.issue, self.remarks, self.resolved, self.id))
        else:
            conn.execute('''
                INSERT INTO pest_log_entries (folder_id, plantation, plant_name, issue, remarks, resolved, staff_name, entry_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (self.folder_id, self.plantation, self.plant_name, self.issue, self.remarks, self.resolved, self.staff_name, self.entry_time))
        conn.commit()
        conn.close()
    
    def to_dict(self):
        return self.__dict__

    @staticmethod
    def get_by_folder(folder_id):
        db = Database()
        conn = db.get_connection()
        rows = conn.execute("SELECT * FROM pest_log_entries WHERE folder_id=? ORDER BY id DESC", (folder_id,)).fetchall()
        conn.close()
        return [PestLogEntry(**dict(row)) for row in rows]

    @staticmethod
    def get_by_id(eid):
        db = Database()
        conn = db.get_connection()
        row = conn.execute("SELECT * FROM pest_log_entries WHERE id=?", (eid,)).fetchone()
        conn.close()
        return PestLogEntry(**dict(row)) if row else None

    @staticmethod
    def delete(eid):
        db = Database()
        conn = db.get_connection()
        conn.execute("DELETE FROM pest_log_entries WHERE id=?", (eid,))
        conn.commit()
        conn.close()

    @staticmethod
    def search(query):
        db = Database()
        conn = db.get_connection()
        q = f"%{query}%"
        sql = '''
            SELECT e.*, f.name as folder_name 
            FROM pest_log_entries e
            JOIN pest_log_folders f ON e.folder_id = f.id
            WHERE e.plant_name LIKE ? OR e.issue LIKE ? OR e.remarks LIKE ? OR e.staff_name LIKE ?
            ORDER BY e.id DESC
        '''
        rows = conn.execute(sql, (q, q, q, q)).fetchall()
        conn.close()
        return [PestLogEntry(**dict(row)) for row in rows]

class Plantation:
   
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.number = kwargs.get('number')
        self.name = kwargs.get('name')
        self.date_created = kwargs.get('date_created') or datetime.now().strftime("%d/%m/%Y")
        self.last_updated = kwargs.get('last_updated')
        self.is_deleted = kwargs.get('is_deleted', 0)
        self.date_deleted = kwargs.get('date_deleted')
        self.global_crop_id = kwargs.get('global_crop_id') 
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


    def get_effective_crop(self, zone_id=None):
        """
        Determines the active crop for AI tracking.
        Hierarchy: 
        1. Check if the specific Zone (Camera) has a manual override.
        2. If not, check the Farm's Global setting.
        3. If no settings exist, return a generic default.
        """
        db = Database()
        conn = db.get_connection()
        
        crop_data = None
        
        try:
            # 1. PRIORITY: Check for Zone-specific override
            if zone_id:
                row = conn.execute("SELECT crop_id FROM farm_zones WHERE id = ?", (zone_id,)).fetchone()
                if row and row['crop_id']:
                    crop_row = conn.execute("SELECT * FROM crops WHERE id = ?", (row['crop_id'],)).fetchone()
                    if crop_row:
                        crop_data = dict(crop_row)

            # 2. FALLBACK: If no zone override, check Farm Global setting
            if not crop_data and self.global_crop_id:
                crop_row = conn.execute("SELECT * FROM crops WHERE id = ?", (self.global_crop_id,)).fetchone()
                if crop_row:
                    crop_data = dict(crop_row)
            
            # 3. FINAL FALLBACK
            if not crop_data:
                crop_data = {"crop_name": "General Detection", "base_confidence": 80}
        
        finally:
            conn.close()  

        return crop_data

 
    @staticmethod
    def set_zone_crop(zone_id, crop_id):
        db = Database()
        conn = db.get_connection()
        # If crop_id is '0' or None, we set it to NULL to revert to Global
        val = crop_id if crop_id and int(crop_id) > 0 else None
        conn.execute("UPDATE farm_zones SET crop_id = ? WHERE id = ?", (val, zone_id))
        conn.commit()
        conn.close()

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
        self.farm_name = kwargs.get('farm_name', 'Unknown Farm') # For Marquee
        
      
        raw_issue = kwargs.get('issue', '')
        raw_remarks = kwargs.get('remarks', '')
        
        try:
 
            self.issue = sec.decrypt_data(raw_issue)
        except Exception:
            self.issue = raw_issue

        try:
            self.remarks = sec.decrypt_data(raw_remarks)
        except Exception:
            self.remarks = raw_remarks

        self.category = kwargs.get('category', 'Other')
        self.severity = kwargs.get('severity', 'Low')
        self.reporter_name = kwargs.get('reporter_name')
        self.entry_time = kwargs.get('entry_time') or datetime.now().strftime('%d/%m/%Y %I:%M %p')
        self.resolved = kwargs.get('resolved', 0)

    def save(self):
        db = Database()
        conn = db.get_connection()
        
 
        encrypted_issue = sec.encrypt_data(self.issue)
        encrypted_remarks = sec.encrypt_data(self.remarks)

 
        try:
            conn.execute("ALTER TABLE pest_logs ADD COLUMN category TEXT DEFAULT 'Other'")
        except:
            pass 

        if self.id:
            conn.execute('''
                UPDATE pest_logs 
                SET issue=?, category=?, severity=?, resolved=?, remarks=? 
                WHERE id=?''', 
                (encrypted_issue, self.category, self.severity, self.resolved, encrypted_remarks, self.id))
        else:
            conn.execute('''
                INSERT INTO pest_logs (plantation_id, issue, category, severity, reporter_name, entry_time, remarks, resolved) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (self.plantation_id, encrypted_issue, self.category, self.severity, self.reporter_name, self.entry_time, encrypted_remarks, self.resolved))
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
 
        rows = conn.execute('''
            SELECT * FROM pest_logs 
            WHERE plantation_id = ? 
            ORDER BY id DESC
        ''', (plantation_id,)).fetchall()
        conn.close()
        return [IncidentLog(**dict(row)) for row in rows]

 

class AIProfile:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.crop_name = kwargs.get('crop_name')
        self.base_confidence = kwargs.get('base_confidence', 95) # e.g. 95%
        self.risk_name = kwargs.get('risk_name', 'Unknown Issue') # e.g. "Fungus"
        self.variance = kwargs.get('variance', 5) # How much it fluctuates
        
        # The logic: If confidence drops below this, trigger the risk
        self.risk_threshold = kwargs.get('risk_threshold', 70) 

    def save(self):
        db = Database()
        conn = db.get_connection()
        
        # Ensure table exists
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ai_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crop_name TEXT NOT NULL,
                base_confidence INTEGER,
                risk_name TEXT,
                variance INTEGER,
                risk_threshold INTEGER
            )
        ''')
        
        if self.id:
            conn.execute('DELETE FROM ai_profiles WHERE id = ?', (self.id,))
            
        conn.execute('''
            INSERT INTO ai_profiles (crop_name, base_confidence, risk_name, variance, risk_threshold)
            VALUES (?, ?, ?, ?, ?)
        ''', (self.crop_name, self.base_confidence, self.risk_name, self.variance, self.risk_threshold))
        
        conn.commit()
        conn.close()

    @staticmethod
    def get_all():
        db = Database()
        conn = db.get_connection()
        # Create table if not exists (lazy init)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ai_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crop_name TEXT NOT NULL,
                base_confidence INTEGER,
                risk_name TEXT,
                variance INTEGER,
                risk_threshold INTEGER
            )
        ''')
        rows = conn.execute("SELECT * FROM ai_profiles").fetchall()
        conn.close()
        
        # If empty, seed default
        if not rows:
            default = AIProfile(crop_name="Tomato (Default)", base_confidence=92, risk_name="Early Blight", variance=10, risk_threshold=75)
            default.save()
            return [default]
            
        return [AIProfile(**dict(row)) for row in rows]

    @staticmethod
    def get_by_name(name):
        profiles = AIProfile.get_all()
        for p in profiles:
            if p.crop_name == name:
                return p
        return profiles[0] # Return first as fallback
    

class Report:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.staff_name = kwargs.get('staff_name')
        self.category = kwargs.get('category')
        self.description = kwargs.get('description')
        self.remarks = kwargs.get('remarks')
        self.created_at = kwargs.get('created_at')

    def save(self):
        db = Database()
        conn = db.get_connection()
        if self.id:
            conn.execute('UPDATE reports SET staff_name=?, category=?, description=?, remarks=? WHERE id=?',
                         (self.staff_name, self.category, self.description, self.remarks, self.id))
        else:
            conn.execute('INSERT INTO reports (staff_name, category, description, remarks) VALUES (?, ?, ?, ?)',
                         (self.staff_name, self.category, self.description, self.remarks))
        conn.commit()
        conn.close()

    @staticmethod
    def get_all(search_query=None):
        db = Database()
        conn = db.get_connection()
        if search_query:
            q = f"%{search_query}%"
            rows = conn.execute("SELECT * FROM reports WHERE staff_name LIKE ? OR description LIKE ? ORDER BY id DESC", (q, q)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM reports ORDER BY id DESC").fetchall()
        conn.close()
        return [Report(**dict(row)) for row in rows]

    @staticmethod
    def get_by_id(report_id):
        db = Database()
        conn = db.get_connection()
        row = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        conn.close()
        return Report(**dict(row)) if row else None

    @staticmethod
    def delete(report_id):
        db = Database()
        conn = db.get_connection()
        conn.execute("DELETE FROM reports WHERE id=?", (report_id,))
        conn.commit()
        conn.close()