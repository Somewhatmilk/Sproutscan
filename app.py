from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, g, Response
from dotenv import load_dotenv  
from authlib.integrations.flask_client import OAuth
from database import Database, Plantation, User, IncidentLog, Crop, AIProfile, PestLogFolder, PestLogEntry, FarmZone, Report
from werkzeug.security import check_password_hash, generate_password_hash
from forms import FarmForm, IncidentForm, ReportForm 
from flask import make_response
from datetime import datetime, timedelta
import cv2   
import threading
import numpy as np
import functools
import sqlite3
import time
import random
import pyotp
import qrcode
import io
import re
import os
import base64


load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key')

# --- CONFIGURE OAUTH DYNAMICALLY ---
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')

# Safety Check (Optional but recommended)
if not app.config['GOOGLE_CLIENT_ID'] or not app.config['GOOGLE_CLIENT_SECRET']:
    print("WARNING: Google OAuth credentials not found in .env file.")

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    client_kwargs={'scope': 'openid email profile'},
)
 

db = Database()

current_tracking_data = {
    "x": 50, # Percentage (0-100)
    "y": 50, # Percentage (0-100)
    "detected": False
}

CROP_CYCLES = {
    'tomato': {'Seedling': 25, 'Vegetative': 35, 'Flowering': 20, 'Fruiting': 30, 'Harvest Ready': 0},
    'lettuce': {'Seedling': 15, 'Vegetative': 25, 'Harvest Ready': 0},
    'wheat': {'Seedling': 14, 'Vegetative': 60, 'Flowering': 30, 'Fruiting': 40, 'Harvest Ready': 0},
    'default': {'Seedling': 20, 'Vegetative': 30, 'Flowering': 20, 'Fruiting': 30, 'Harvest Ready': 0}
}

 
class VideoCamera(object):
    def __init__(self):
        # 0 is usually the default webcam
        self.video = cv2.VideoCapture(0)
        # Load standard face detector (included in cv2)
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    def __del__(self):
        self.video.release()

    def get_frame(self):
        success, image = self.video.read()
        if not success:
            return None
            
        # 1. ACTUAL PYTHON PREDICTION/TRACKING
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
        
        height, width, _ = image.shape
        
        global current_tracking_data
        
        if len(faces) > 0:
            # Get the biggest face (closest "Plant")
            (x, y, w, h) = faces[0]
            
            # Calculate center point in Percentage (for CSS positioning)
            center_x = ((x + (w/2)) / width) * 100
            center_y = ((y + (h/2)) / height) * 100
            
            # Update Global State
            current_tracking_data["x"] = center_x
            current_tracking_data["y"] = center_y
            current_tracking_data["detected"] = True
            
            # Optional: Draw on the video stream itself (Debugging)
            # cv2.rectangle(image, (x, y), (x+w, y+h), (0, 255, 0), 2)
        else:
            current_tracking_data["detected"] = False

        # Encode frame to JPEG
        ret, jpeg = cv2.imencode('.jpg', image)
        return jpeg.tobytes()

# Global camera instance
camera_instance = None

def gen(camera):
    while True:
        frame = camera.get_frame()
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
 
 

LOG_FILE = "ai_logs.txt"

def read_latest_logs_by_crop(limit_lines=5000):
    """
    Parses the local ai_logs.txt file to find confidence scores.
    Integrated Logic: Returns a dict keyed by crop name.
    """
    try:
        if not os.path.exists(LOG_FILE):
            return {}

        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f.readlines() if ln.strip()]

        if not lines: return {}
        
        lines = lines[-limit_lines:]
        pattern = re.compile(
            r'^\[(?P<ts>.*?)\]\s*TARGET:(?P<crop>.*?)\s*\|\s*STATUS:(?P<status>.*?)\s*\|\s*CONF:(?P<conf>\d+)%\s*\|\s*COORD:\((?P<x>-?\d+),(?P<y>-?\d+)\)'
        )

        result = {} 
        for line in reversed(lines):
            m = pattern.search(line)
            if not m: continue

            crop = m.group("crop").strip()
            crop_key = crop.lower()

            if crop_key in result: continue 

            confidence = int(m.group("conf"))
            # THE LOGIC CHECK: 
            growth_status = "Normal" if confidence >= 90 else "Needs to be checked"
            
            # Determine Color for UI based on status
            ai_color = "#2ecc71" if growth_status == "Normal" else "#e74c3c"

            result[crop_key] = {
                "timestamp": m.group("ts").strip(),
                "crop": crop,
                "ai_status": m.group("status").strip(), # e.g. "Healthy"
                "confidence": confidence,
                "growth_status": growth_status,
                "ai_color": ai_color
            }
        return result
    except Exception as e:
        print(f"Log Error: {e}")
        return {}

 
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/pest-logs/folders-json')
@login_required
def get_folders_json():
    folders = PestLogFolder.get_all()
    # Return simple list of dictionaries
    return jsonify([{'id': f.id, 'name': f.name} for f in folders])



@app.route('/pest-logs')
@login_required
def pest_logs():
    folders = PestLogFolder.get_all()
    # Convert string date to object for template if needed, or handle in template
    for f in folders:
        try:
            f.date_obj = datetime.strptime(f.date_created, "%Y-%m-%d %H:%M:%S")
        except:
            f.date_obj = None
    return render_template('pest_logs_list.html', folders=folders)

@app.route('/pest-logs/folder/new', methods=['POST'])
@login_required
def create_pest_log_folder():
    data = request.get_json()
    folder_name = data.get('name')
    
    if not folder_name:
        return jsonify({'error': 'Folder name is required'}), 400
    
    # Generate simple number based on count
    existing = PestLogFolder.get_all()
    next_num = str(len(existing) + 1).zfill(2)
    
    new_folder = PestLogFolder(number=next_num, name=folder_name)
    new_folder.save()
    
    return jsonify(new_folder.__dict__), 201

@app.route('/pest-logs/folder/<int:folder_id>')
@login_required
def view_pest_log_entries(folder_id):
    folder = PestLogFolder.get_by_id(folder_id)
    if not folder: return redirect(url_for('pest_logs'))
    
    entries = PestLogEntry.get_by_folder(folder_id)
    
    # Organize entries by plantation (1-4)
    plantations = {1: [], 2: [], 3: [], 4: []}
    for entry in entries:
        p_num = int(entry.plantation)
        if p_num in plantations:
            plantations[p_num].append(entry)
            
    return render_template('pest_logs_entries.html', folder=folder, plantations=plantations)

@app.route('/pest-logs/entry/new', methods=['POST'])
@login_required
def create_pest_log_entry():
    data = request.get_json()
    
    new_entry = PestLogEntry(
        folder_id=data.get('folder_id'),
        plantation=data.get('plantation'),
        plant_name=data.get('plant_name'),
        issue=data.get('issue'),
        remarks=data.get('remarks', ''),
        resolved=data.get('resolved', 'No'),
        staff_name=g.user.name  # Use logged in user
    )
    new_entry.save()
    return jsonify(new_entry.to_dict()), 201


@app.route('/plantation/<int:farm_id>/log/add', methods=['POST'])
@login_required
def add_pest_log_integrated(farm_id):
    # 1. Get farm details
    farm = Plantation.get_by_id(farm_id)
    
    # 2. Find or Create a "Field Notes" folder for this farm
    db_conn = db.get_connection()
    folder = db_conn.execute("SELECT id FROM pest_log_folders WHERE name = ?", (f"{farm.name} - Logs",)).fetchone()
    
    if not folder:
        # Create folder if missing
        new_f = PestLogFolder(number=farm.number, name=f"{farm.name} - Logs")
        new_f.save()
        folder_id = new_f.id
    else:
        folder_id = folder['id']

    # 3. Create the PestLogEntry
    new_entry = PestLogEntry(
        folder_id=folder_id,
        plantation=1, # Defaulting to sector 1 for quick notes
        plant_name=request.form.get('plant_name', 'General'),
        issue=request.form.get('issue'),
        remarks=request.form.get('remarks'),
        staff_name=g.user.name
    )
    new_entry.save()
    
    return jsonify({"success": True})

@app.route('/api/farms/bulk-delete', methods=['POST'])
@login_required
def bulk_farm_delete():
    data = request.get_json()
    ids = data.get('ids', [])
    if not ids:
        return jsonify({"success": False}), 400
    
    db_conn = db.get_connection()
    # Soft delete logic
    placeholders = ','.join(['?'] * len(ids))
    db_conn.execute(f"UPDATE plantations SET is_deleted = 1, date_deleted = ? WHERE id IN ({placeholders})", 
                    ([datetime.now().strftime("%d/%m/%Y")] + ids))
    db_conn.commit()
    db_conn.close()
    return jsonify({"success": True})

@app.route('/pest-logs/entry/<int:entry_id>/delete', methods=['POST'])
@login_required
def delete_pest_log_entry(entry_id):
    PestLogEntry.delete(entry_id)
    return jsonify({'success': True}), 200

@app.route('/pest-logs/folder/<int:folder_id>/delete', methods=['POST'])
@login_required
def delete_pest_log_folder(folder_id):
    PestLogFolder.delete(folder_id)
    return jsonify({'success': True}), 200

@app.route('/pest-logs/entry/<int:entry_id>/update', methods=['POST'])
@login_required
def update_pest_log_entry(entry_id):
    entry = PestLogEntry.get_by_id(entry_id)
    if not entry: return jsonify({'error': 'Not found'}), 404
    
    data = request.get_json()
    if 'resolved' in data: entry.resolved = data['resolved']
    # Add other fields as needed for edit
    
    entry.save()
    return jsonify(entry.to_dict()), 200

@app.route('/pest-logs/entry/<int:entry_id>')
@login_required
def get_single_entry(entry_id):
    entry = PestLogEntry.get_by_id(entry_id)
    return jsonify(entry.to_dict())

@app.route('/pest-logs/search')
@login_required
def search_pest_logs():
    query = request.args.get('q', '').strip()
    if not query: return jsonify([])
    results = PestLogEntry.search(query)
    return jsonify([r.to_dict() for r in results])

# --- PDF EXPORT (Ported logic, no ORM) ---
@app.route('/pest-logs/folder/<int:folder_id>/export-pdf')
@login_required
def export_folder_pdf(folder_id):
    try:
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.units import inch
    except ImportError:
        return jsonify({'error': 'ReportLab not installed'}), 500
    
    folder = PestLogFolder.get_by_id(folder_id)
    entries = PestLogEntry.get_by_folder(folder_id)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    elements.append(Paragraph(f"PEST LOG: {folder.name}", styles['Heading1']))
    elements.append(Spacer(1, 0.2*inch))
    
    # Table Data
    data = [['Plantation', 'Plant', 'Issue', 'Time', 'Staff', 'Remarks', 'Status']]
    for e in entries:
        data.append([
            f"P-{e.plantation}", e.plant_name, e.issue, 
            e.entry_time, e.staff_name, e.remarks, e.resolved
        ])
    
    table = Table(data, colWidths=[0.8*inch, 1.5*inch, 2*inch, 1.5*inch, 1*inch, 2*inch, 0.8*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 1, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 8),
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    pdf_data = buffer.getvalue()
    buffer.close()
    
    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={folder.name}.pdf'
    return response

@app.route('/video_feed')
@login_required
def video_feed():
    global camera_instance
    if camera_instance is None:
        camera_instance = VideoCamera()
    return Response(gen(camera_instance),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        # Fetch fresh user object
        db_conn = db.get_connection()
        row = db_conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        db_conn.close()
        if row:
            g.user = User(**dict(row))
            g.all_users = User.get_all()
        else:
            g.user = None

@app.route('/api/setup-mfa')
@login_required
def setup_mfa():
    # 1. Generate Secret
    secret = pyotp.random_base32()
    
    # 2. STORE IN SESSION ONLY (Do not save to DB yet!)
    session['temp_mfa_secret'] = secret
    
    # 3. Generate QR Code
    user_email = g.user.email or g.user.username
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user_email, issuer_name="AgriScan AI")
    
    img = qrcode.make(uri)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({
        "secret": secret, 
        "qr_image": f"data:image/png;base64,{img_str}"
    })

@app.route('/api/verify-mfa', methods=['POST'])
@login_required
def verify_mfa_setup():
    data = request.json
    token = data.get('token').replace(" ", "") 
    secret = session.get('temp_mfa_secret')

    if not secret:
        return jsonify({"success": False, "message": "Session expired. Try again."})

    # Verify the token against the temporary secret
    totp = pyotp.TOTP(secret)
    if totp.verify(token):
        conn = db.get_connection()
        conn.execute("UPDATE users SET mfa_secret = ? WHERE id = ?", (secret, session['user_id']))
        conn.commit()
        conn.close()
        session.pop('temp_mfa_secret', None) # Clear temp
        return jsonify({"success": True, "message": "MFA Enabled Successfully!"})
    
    return jsonify({"success": False, "message": "Invalid Code"})

# --- LOGIN LOGIC ---
@app.route('/', methods=['GET', 'POST'])
def login():
    # AJAX Logic (From Secondary Version)
    if request.method == 'POST' and request.is_json:
        data = request.get_json()
        user = User.get_by_username(data.get('username'))
        
        if not user or not check_password_hash(user.password, data.get('password')):
            return jsonify({"success": False, "message": "Invalid credentials"})
            
  
        conn = db.get_connection()
        row = conn.execute("SELECT mfa_secret FROM users WHERE id = ?", (user.id,)).fetchone()
        conn.close()
        
        if row and row['mfa_secret']:
            if not data.get('mfa_token'):
                return jsonify({"success": False, "mfa_required": True})
            if not pyotp.TOTP(row['mfa_secret']).verify(data.get('mfa_token')):
                return jsonify({"success": False, "message": "Invalid MFA Code"})
        
        session['user_id'] = user.id
        session['role'] = user.role
        return jsonify({"success": True, "redirect": url_for('home')})

    return render_template('login.html', users=User.get_all())

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/switch_role', methods=['POST'])
def switch_role():
    data = request.json
    target_username = data.get('username')
    password_attempt = data.get('password')

    user = User.get_by_username(target_username)
    
    if user and check_password_hash(user.password, password_attempt):
        session['user_id'] = user.id
        session['role'] = user.role
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': 'Invalid Password'})

# --- MAIN ROUTES ---

@app.route('/dashboard')
@login_required
def home():
    search_query = request.args.get('q')
    plantations = Plantation.get_all(search_query=search_query)
    return render_template('dashboard.html', plantations=plantations, search_query=search_query)

@app.route('/farms/create', methods=['GET', 'POST'])
@login_required
def create_plantation():
    form = FarmForm(request.form)
    
    if request.method == 'POST':
        if form.validate():
  
            raw_date = form.date_created.data 
            formatted_date = raw_date
            try:
                date_obj = datetime.strptime(raw_date, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d/%m/%Y')
            except ValueError: pass
            
            new_farm = Plantation(
                number=form.number.data, 
                name=form.name.data, 
                date_created=formatted_date
            )
            new_farm.save()

   
            auto_folder = PestLogFolder(
                number=form.number.data,
                name=f"{form.name.data} - Logs"
            )
            auto_folder.save()

            flash("New farm and associated log folder created!", "success")
            return redirect(url_for('home'))
            
    return render_template('update_plantation.html', plantation=None, form=form)



@app.route('/farms')
@login_required
def view_farms():
    plantations = Plantation.get_all()
    return render_template('farms_list.html', plantations=plantations)

@app.route('/maintenance')
@login_required
def maintenance_hub():
    # Use IncidentLog here (Renamed from PestLog)
    incidents = IncidentLog.get_all_active()
    return render_template('maintenance.html', incidents=incidents)


@app.route('/api/farms-json')
@login_required
def get_farms_simple():
    """Returns a simple JSON list of all active farms for dropdowns."""
    farms = Plantation.get_all()
    return jsonify([{'id': f.id, 'name': f.name, 'number': f.number} for f in farms])

@app.route('/api/farms/<int:farm_id>/zones')
@login_required
def get_farm_zones_json(farm_id):
    """Returns zones specific to a farm ID."""
    zones = FarmZone.get_by_farm(farm_id)
    return jsonify([{'id': z.id, 'name': z.name} for z in zones])

@app.route('/farm/<int:farm_id>/set_global_crop', methods=['POST'])
@login_required
def set_global_crop(farm_id):
    crop_id = request.form.get('global_crop_id')
    
    conn = db.get_connection()
    conn.execute("UPDATE plantations SET global_crop_id = ? WHERE id = ?", (crop_id, farm_id))
    conn.commit()
    conn.close()
    
 
    return redirect(url_for('view_farm_overview', farm_id=farm_id))

@app.route('/farm/unit/<int:zone_id>/set_override', methods=['POST'])
@login_required
def set_unit_override(zone_id):
    crop_id = request.form.get('override_crop_id')
    # If crop_id is 0, it clears the override
    FarmZone.set_zone_crop(zone_id, crop_id)
    return redirect(request.referrer)

# --- UPDATE EXISTING ROUTE: view_plantation ---
@app.route('/farm/<int:farm_id>/unit/<int:zone_id>')
@login_required
def view_plantation(farm_id, zone_id):
    plantation = Plantation.get_by_id(farm_id) 
    zone = FarmZone.get_by_id(zone_id)         
    
    if not plantation or not zone:
        return redirect(url_for('home'))
        
    logs = IncidentLog.get_by_plantation(farm_id)
    
 
    active_crop = plantation.get_effective_crop(zone_id)
    
    # Get all crops for the settings modal (Special Cases)
    all_crops = Crop.get_all_with_stages()

    return render_template('view_plantation.html', 
                           plantation=plantation, 
                           active_zone=zone, 
                           logs=logs,
                           active_crop=active_crop,
                           all_crops=all_crops)

 
@app.route('/farm/<int:farm_id>/overview')
@login_required
def view_farm_overview(farm_id):
    farm = Plantation.get_by_id(farm_id)
    if not farm: return redirect(url_for('home'))
 
    logs = IncidentLog.get_by_plantation(farm_id)
    units = FarmZone.get_by_farm(farm_id)
    all_crops = Crop.get_all_with_stages()
    
    return render_template('farm_overview.html', 
                           farm=farm, 
                           units=units, 
                           logs=logs, 
                           crops=all_crops)

 
@app.route('/farm/<int:farm_id>/unit/new', methods=['POST'])
@login_required
def create_farm_unit(farm_id):
    name = request.form.get('name')
    if name:
        # Create the new zone in DB
        # Note: You might need to add a 'save' method to FarmZone in database.py 
        # or use raw SQL here if you haven't updated the class yet.
        db_conn = db.get_connection()
        db_conn.execute("INSERT INTO farm_zones (farm_id, name, type) VALUES (?, ?, ?)", 
                        (farm_id, name, 'camera'))
        db_conn.commit()
        db_conn.close()
        
        flash(f"Unit '{name}' added to grid.", "success")
    return redirect(url_for('view_farm_overview', farm_id=farm_id))


@app.route('/plantation/<int:plantation_id>/log/add', methods=['POST'])
@login_required
def add_pest_log(plantation_id):
    # This uses the new WTForms validation
    form = IncidentForm(request.form) 
    
    if form.validate():
        log = IncidentLog(
            plantation_id=plantation_id,
            issue=form.issue.data,
            category=form.category.data,  
            severity=form.severity.data,
            reporter_name=g.user.name,
            remarks=form.remarks.data
        )
        log.save()
        flash("Incident Ticket Created", "success")
    else:
        flash("Error creating ticket: " + str(form.errors), "error")
        
    return redirect(url_for('view_plantation', plantation_id=plantation_id))

@app.route('/log/<int:log_id>/toggle', methods=['POST'])
@login_required
def toggle_log_status(log_id):
    conn = db.get_connection()
    # Ensure table name matches database.py (pest_logs)
    conn.execute("UPDATE pest_logs SET resolved = NOT resolved WHERE id = ?", (log_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer)

@app.route('/plantation/<int:plantation_id>/update', methods=['GET', 'POST'])
@login_required
def update_plantation(plantation_id):
    plantation = Plantation.get_by_id(plantation_id)
    if not plantation:
        return redirect(url_for('view_farms'))
    
    form = FarmForm(request.form)

    if request.method == 'POST' and form.validate():
        # Same Date Conversion Logic
        raw_date = form.date_created.data 
        formatted_date = raw_date
        try:
            date_obj = datetime.strptime(raw_date, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d/%m/%Y')
        except ValueError:
            pass

        plantation.number = form.number.data
        plantation.name = form.name.data
        plantation.date_created = formatted_date
        plantation.save()
        
        flash('Farm updated successfully!', 'success')
        return redirect(url_for('view_farms'))
    
    # PRE-FILL LOGIC (IMPORTANT)
    if request.method == 'GET':
        form.number.data = plantation.number
        form.name.data = plantation.name
        
      
        try:
            db_date = datetime.strptime(plantation.date_created, '%d/%m/%Y')
            # We inject a temporary attribute 'date_created_iso' to use in the template
            plantation.date_created_iso = db_date.strftime('%Y-%m-%d')
        except:
            plantation.date_created_iso = ""

    return render_template('update_plantation.html', plantation=plantation, form=form)

@app.route("/plantations/<int:plantation_id>/delete", methods=["POST"])
@login_required
def delete_plantation(plantation_id):
    p = Plantation.get_by_id(plantation_id)
    if p: p.soft_delete()
    return redirect(url_for("view_farms"))

@app.route("/farms/deleted")
@login_required
def deleted_farms():
    conn = db.get_connection()
    rows = conn.execute("SELECT * FROM plantations WHERE is_deleted = 1").fetchall()
    conn.close()
    plantations = [Plantation(**dict(row)) for row in rows]
    return render_template("deleted_farms.html", plantations=plantations)

@app.route("/plantations/<int:plantation_id>/restore", methods=["POST"])
@login_required
def restore_plantation(plantation_id):
    conn = db.get_connection()
    conn.execute("UPDATE plantations SET is_deleted = 0, date_deleted = NULL WHERE id = ?", (plantation_id,))
    conn.commit()
    conn.close()
    flash("Farm recovered successfully!", "success")
    return redirect(url_for("deleted_farms"))

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.form.get('email')
    flash(f'Password reset link sent to {email}', 'success')
    return redirect(url_for('login'))
 

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Handle Password Change
        new_pass = request.form.get('new_password')
        if new_pass:
            hashed = generate_password_hash(new_pass)
            conn = db.get_connection()
            conn.execute("UPDATE users SET password = ? WHERE id = ?", (hashed, session['user_id']))
            conn.commit()
            conn.close()
            flash("Password updated successfully.", "success")
        return redirect(url_for('profile'))
        
    return render_template('profile.html', user=g.user)

@app.route('/users/<int:user_id>/update', methods=['POST'])
@login_required
def update_user(user_id):
    if g.user.role != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    # Get data using .get() to avoid crashes
    name = request.form.get('name')
    email = request.form.get('email')
    role = request.form.get('role')
    bio = request.form.get('bio', '')

    conn = db.get_connection()
    try:
        conn.execute(
            "UPDATE users SET name=?, email=?, role=?, bio=? WHERE id=?", 
            (name, email, role, bio, user_id)
        )
        conn.commit()
        flash(f"User {name} updated successfully.", "success")
    except Exception as e:
        flash("Error updating user.", "error")
    finally:
        conn.close()

    return redirect(url_for('manage_users'))

@app.route('/users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if g.user.role != 'admin':
        flash("Access Denied: Admins Only", "error")
        return redirect(url_for('home'))

    if request.method == 'POST':
        default_pw = "123"
        bio = request.form.get('bio', '') 
        success = User.create(
            request.form['username'], 
            request.form['email'], 
            default_pw,
            request.form['role'], 
            request.form['name'],
            bio,
            "#" + "".join([random.choice('0123456789ABCDEF') for j in range(6)])
        )
        if success:
            flash(f"User created. Setup email sent to {request.form['email']}.", "success")
        else:
            flash("Username already exists.", "error")
    
    return render_template('users.html', users=User.get_all())

@app.route("/cropstage")
@login_required
def cropstage_view():
    crops = Crop.get_all_with_stages()
    return render_template("cropstage.html", crops=crops)

@app.route("/add-crop")
@login_required
def add_crop_page():
    return render_template("cropstage_add.html")

@app.route("/api/crops", methods=['GET', 'POST'])
@login_required
def handle_crops():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        crop_name = (data.get("crop_name") or "").strip()
        category = (data.get("category") or "").strip()
        notes = (data.get("notes") or "").strip()

        if not crop_name or not category:
            return jsonify({"error": "Crop name and category are required"}), 400

        Crop.create(crop_name, category, notes)
        return jsonify({"message": "Crop created"}), 201
    
    # GET
    crops = Crop.get_all_with_stages()
    return jsonify(crops)



@app.route("/api/crops/<int:crop_id>", methods=["DELETE"])
@login_required
def delete_crop(crop_id):
    Crop.delete(crop_id)
    return jsonify({"message": "Crop deleted"}), 200

@app.get("/crop_view")
def view_list():
    with sqlite3.connect('plantations.db') as conn:
        conn.row_factory = sqlite3.Row
        # We fetch the 'created_at' of the STAGE to calculate days elapsed
        rows = conn.execute("""
            SELECT
                c.id AS crop_id,
                c.crop_name,
                c.category,
                c.notes,
                COALESCE(cs.stage_name, 'Seedling') AS stage_name,
                COALESCE(cs.created_at, c.created_at) AS stage_start_date,
                COALESCE(cs.ai_confidence, 0) AS ai_confidence,
                COALESCE(cs.status, 'Pending') AS status
            FROM crops c
            LEFT JOIN cropstage cs
              ON cs.id = (
                SELECT id FROM cropstage WHERE crop_id = c.id ORDER BY created_at DESC LIMIT 1
              )
            ORDER BY c.crop_name ASC
        """).fetchall()

    # --- MATHEMATICAL CALCULATIONS ---
    processed_crops = []
    for row in rows:
        crop_data = dict(row)
        
        # 1. Normalize name for lookup
        name_key = crop_data['crop_name'].lower()
        if 'tomato' in name_key: cycle_key = 'tomato'
        elif 'lettuce' in name_key: cycle_key = 'lettuce'
        elif 'wheat' in name_key: cycle_key = 'wheat'
        else: cycle_key = 'default'
        
        current_stage = crop_data['stage_name']
        cycle_data = CROP_CYCLES.get(cycle_key, CROP_CYCLES['default'])
        
        # 2. Calculate Days Elapsed since stage change
        try:
            # Parse DB timestamp (Handles "YYYY-MM-DD HH:MM:SS" or similar)
            start_dt = datetime.strptime(crop_data['stage_start_date'], '%Y-%m-%d %H:%M:%S')
        except:
            try: 
                 start_dt = datetime.strptime(crop_data['stage_start_date'], '%Y-%m-%d')
            except:
                 start_dt = datetime.now() # Fallback

        days_elapsed = (datetime.now() - start_dt).days
        if days_elapsed < 0: days_elapsed = 0
        
        # 3. Get Expected Duration for current stage
        expected_duration = cycle_data.get(current_stage, 30)
        
        # 4. Calculate Progress Percentage
        if expected_duration > 0:
            progress = int((days_elapsed / expected_duration) * 100)
        else:
            progress = 100 # Harvest Ready

        # Cap progress at 99% if not manually moved
        progress = min(progress, 99) if current_stage != 'Harvest Ready' else 100
        
        # 5. Calculate Days to Harvest (Sum of remaining stages)
        days_to_harvest = 0
        found_current = False
        for stage, duration in cycle_data.items():
            if stage == current_stage:
                found_current = True
                remaining_in_stage = max(0, duration - days_elapsed)
                days_to_harvest += remaining_in_stage
            elif found_current:
                days_to_harvest += duration
        
 
        
        crop_data['calc_progress'] = progress
        crop_data['days_elapsed'] = days_elapsed
        crop_data['days_to_harvest'] = days_to_harvest
        
        processed_crops.append(crop_data)

    return render_template("viewcrops.html", crops=processed_crops)

@app.route("/api/log_map")
@login_required
def log_map():
    """Endpoint used by viewcrops.html to update UI via AJAX"""
    data = read_latest_logs_by_crop()
    return jsonify({"success": True, "data": data})

@app.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if g.user.role != 'admin':
        return redirect(url_for('home'))
    User.delete(user_id)
    flash("User deleted", "success")
    return redirect(url_for('manage_users'))

@app.route('/reports/create', methods=['GET', 'POST'])
@login_required
def create_report():
    form = ReportForm(request.form)
    if request.method == 'POST' and form.validate():
        new_report = Report(
            staff_name=form.staff_name.data,
            category=form.category.data,
            description=form.description.data,
            remarks=form.remarks.data
        )
        new_report.save()
        flash('Report created successfully!', 'success')
        return redirect(url_for('retrieve_reports'))
    return render_template('createReport.html', form=form)

@app.route('/reports')
@login_required
def retrieve_reports():
    query = request.args.get('q')
    reports = Report.get_all(search_query=query)
    return render_template('retrieveReports.html', reports_list=reports)

@app.route('/reports/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update_report(id):
    report = Report.get_by_id(id)
    form = ReportForm(request.form)
    if request.method == 'POST' and form.validate():
        report.staff_name = form.staff_name.data
        report.category = form.category.data
        report.description = form.description.data
        report.remarks = form.remarks.data
        report.save()
        flash('Report updated!', 'success')
        return redirect(url_for('retrieve_reports'))
    
    # Pre-fill
    form.staff_name.data = report.staff_name
    form.category.data = report.category
    form.description.data = report.description
    form.remarks.data = report.remarks
    return render_template('updateReport.html', form=form)

@app.route('/reports/delete/<int:id>', methods=['POST'])
@login_required
def delete_report(id):
    Report.delete(id)
    flash('Report deleted', 'danger')
    return redirect(url_for('retrieve_reports'))

@app.route('/liveSearch')
def live_search():
    query = request.args.get('q', '')
    reports = Report.get_all(search_query=query)
    return jsonify([{'id': r.id, 'staff_name': r.staff_name, 'category': r.category, 'description': r.description, 'created_at': r.created_at} for r in reports])

@app.route('/api/ai-profiles', methods=['GET', 'POST'])
@login_required
def handle_ai_profiles():
    if request.method == 'POST':
        data = request.json
        profile = AIProfile(
            crop_name=data['crop_name'],
            base_confidence=int(data['base_confidence']),
            risk_name=data['risk_name'],
            risk_threshold=int(data['risk_threshold']),
            variance=int(data['variance'])
        )
        profile.save()
        return jsonify({"success": True})
    
    # GET
    profiles = AIProfile.get_all()
    return jsonify([p.__dict__ for p in profiles])

@app.route('/api/admin/audit')
@login_required
def security_audit():
    if g.user.role != 'admin': return jsonify([])
    
    # Fetch raw users to show hashed passwords
    conn = db.get_connection()
    users = conn.execute("SELECT username, password FROM users").fetchall()
    
    # Fetch raw logs to show encrypted text
    logs = conn.execute("SELECT issue, remarks FROM pest_logs").fetchall()
    conn.close()
    
    return jsonify({
        "users": [dict(u) for u in users],
        "logs": [dict(l) for l in logs]
    })


def write_detailed_log(crop, status, confidence, x, y):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] TARGET:{crop} | STATUS:{status} | CONF:{confidence}% | COORD:({int(x)},{int(y)}) | LOG: Saved\n"
    try:
        with open("ai_logs.txt", "a") as f:
            f.write(log_line)
    except: pass

@app.route('/api/snapshot', methods=['POST'])
@login_required
def save_snapshot():
    global camera_instance
    if not camera_instance:
        camera_instance = VideoCamera()
        
    # Get the raw frame (not the bytes for browser, but the numpy array)
    success, image = camera_instance.video.read()
    
    if success:
        # Create folder if not exists
        folder = os.path.join('static', 'snapshots')
        if not os.path.exists(folder):
            os.makedirs(folder)
            
        # Generate filename
        filename = f"snap_{int(time.time())}.jpg"
        path = os.path.join(folder, filename)
        
        # Save
        cv2.imwrite(path, image)
        return jsonify({"success": True, "file": filename})
    
    return jsonify({"success": False, "message": "Camera Error"})

@app.route("/api/crops/<int:crop_id>/stage", methods=["POST"])
@login_required
def update_crop_stage(crop_id):
    data = request.get_json(silent=True) or {}
    stage_name = data.get("stage_name")

    if not stage_name:
        return jsonify({"success": False, "message": "Stage name required"}), 400

    # Delegate to Database Class
    Crop.add_stage(crop_id, stage_name)
    return jsonify({"success": True}), 200
 
@app.route('/api/live-data')
@login_required
def live_data():
    crop_name = request.args.get('crop', 'Unknown')
    profile = AIProfile.get_by_name(crop_name)
    
 
    box_x = current_tracking_data["x"]
    box_y = current_tracking_data["y"]
    is_detected = current_tracking_data["detected"]
    
    # 2. Logic: If detected, Confidence is HIGH. If not, LOW.
    req_base = request.args.get('base_override')
    base = int(req_base) if req_base else profile.base_confidence
    
    if is_detected:
        # High confidence because we found the object/face
        fluctuation = random.uniform(-2, 2)
        current_confidence = round(base + fluctuation, 1)
        status = "TARGET LOCKED"
        color = "#2ecc71" # Green
        insight = f"Object detected at {int(box_x)}%, {int(box_y)}%. Assessing health..."
    else:
        # Low confidence because screen is empty
        current_confidence = round(random.uniform(5, 15), 1) 
        status = "SCANNING..."
        color = "#e74c3c" # Red
        insight = "No active targets in sector. Searching..."
        
     
        box_x = 50
        box_y = 50

    current_confidence = max(0, min(100, current_confidence))
    
    # Write logs
    write_detailed_log(crop_name, status, current_confidence, int(box_x), int(box_y))

    return jsonify({
        "status": status,
        "confidence": current_confidence,
        "insight": insight,
        "color": color,
        "box": { "x": box_x, "y": box_y } # THIS NOW SENDS REAL COORDINATES
    })


if __name__ == '__main__':
    app.run(debug=True, port=5500)