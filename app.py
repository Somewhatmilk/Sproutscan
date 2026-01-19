from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, g
# Make sure to import IncidentLog and IncidentForm
from database import Database, Plantation, User, IncidentLog 
from werkzeug.security import check_password_hash
from forms import FarmForm, IncidentForm
from datetime import datetime
import random
import functools
import re
import pyotp
import qrcode
import io
import base64

app = Flask(__name__)
app.secret_key = 'super-secret-key-agriscan'

# Initialize DB once
db = Database()

# --- AUTH DECORATOR ---
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- CONTEXT PROCESSOR (Global User) ---
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
    secret = pyotp.random_base32()
    conn = db.get_connection()
    conn.execute("UPDATE users SET mfa_secret = ? WHERE id = ?", (secret, session['user_id']))
    conn.commit()
    conn.close()
    
    user_email = g.user.email if g.user.email else g.user.username
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user_email, issuer_name="AgriScan AI")
    
    img = qrcode.make(uri)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({"secret": secret, "qr_image": f"data:image/png;base64,{img_str}"})

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
    if request.method == 'POST' and form.validate():
        # Ideally you should save the farm here using the form data
        # new_farm = Plantation(number=form.number.data, name=form.name.data, date_created=form.date_created.data)
        # new_farm.save()
        flash("New farm created successfully!", "success")
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

@app.route('/plantation/<int:plantation_id>')
@login_required
def view_plantation(plantation_id):
    plantation = Plantation.get_by_id(plantation_id)
    if not plantation:
        flash('Plantation not found', 'error')
        return redirect(url_for('home'))
    
    # Use IncidentLog here instead of PestLog
    logs = IncidentLog.get_by_plantation(plantation_id)
    return render_template('view_plantation.html', plantation=plantation, logs=logs)

# --- INCIDENT LOG ROUTES (Corrected) ---
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
        plantation.number = form.number.data
        plantation.name = form.name.data
        plantation.date_created = form.date_created.data
        plantation.save()
        
        flash('Farm updated successfully!', 'success')
        return redirect(url_for('view_farms'))
    
    # Pre-fill form if GET request
    if request.method == 'GET':
        form.number.data = plantation.number
        form.name.data = plantation.name
        form.date_created.data = plantation.date_created

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
 
@app.route('/users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if g.user.role != 'admin':
        flash("Access Denied: Admins Only", "error")
        return redirect(url_for('home'))

    if request.method == 'POST':
        default_pw = "123"
        success = User.create(
            request.form['username'], 
            request.form['email'], 
            default_pw,
            request.form['role'], 
            request.form['name'],
            request.form['bio'], 
            "#" + "".join([random.choice('0123456789ABCDEF') for j in range(6)])
        )
        if success:
            flash(f"User created. Setup email sent to {request.form['email']}.", "success")
        else:
            flash("Username already exists.", "error")
    
    return render_template('users.html', users=User.get_all())

@app.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if g.user.role != 'admin':
        return redirect(url_for('home'))
    User.delete(user_id)
    flash("User deleted", "success")
    return redirect(url_for('manage_users'))

# --- API FOR LIVE DATA (Simulated AI) ---
@app.route('/api/live-data')
@login_required
def live_data():
    status_options = ["Healthy", "Healthy", "Healthy", "Early Blight", "Rust Fungus"]
    status = random.choice(status_options)
    
    return jsonify({
        "status": status,
        "confidence": random.uniform(0.75, 0.99),
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "color": "green" if status == "Healthy" else "red"
    })

if __name__ == '__main__':
    app.run(debug=True, port=5500)