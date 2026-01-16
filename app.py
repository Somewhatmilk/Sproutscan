from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, g
from database import Database, Plantation, User

from werkzeug.security import check_password_hash
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

# Initialize DB
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
        # We need to fetch the fresh user object to get current role/details
        # In a real app, cache this. Here we fetch from DB.
        db_conn = db.get_connection()
        row = db_conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        db_conn.close()
        if row:
            g.user = User(**dict(row))
            # Also inject a list of all users for the role switcher
            g.all_users = User.get_all()
        else:
            g.user = None

 
@app.route('/api/setup-mfa')
@login_required
def setup_mfa():
    # Generate a random secret for the user
    secret = pyotp.random_base32()
    
    # Save secret to DB (In real app, confirm before saving, but for demo we save now)
    conn = db.get_connection()
    conn.execute("UPDATE users SET mfa_secret = ? WHERE id = ?", (secret, session['user_id']))
    conn.commit()
    conn.close()
    
    # Generate QR Code
    user_email = g.user.email if g.user.email else g.user.username
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user_email, issuer_name="AgriScan AI")
    
    img = qrcode.make(uri)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({"secret": secret, "qr_image": f"data:image/png;base64,{img_str}"})

# --- UPDATED LOGIN LOGIC (AJAX) ---
@app.route('/', methods=['GET', 'POST'])
def login():
    # If it's a JSON request (AJAX), handle logic
    if request.method == 'POST' and request.is_json:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        mfa_token = data.get('mfa_token') # Optional
        
        user = User.get_by_username(username)
        
        # 1. Validate Password
        if not user or not check_password_hash(user.password, password):
            return jsonify({"success": False, "message": "Invalid credentials"})
            
        # 2. Check MFA
        # Fetch the real user row to check mfa_secret (User object needs updating or fetch direct)
        conn = db.get_connection()
        row = conn.execute("SELECT mfa_secret FROM users WHERE id = ?", (user.id,)).fetchone()
        conn.close()
        mfa_secret = row['mfa_secret'] if row else None
        
        # If user has MFA enabled but didn't send token yet
        if mfa_secret and not mfa_token:
            return jsonify({"success": False, "mfa_required": True})
            
        # If user sent token, verify it
        if mfa_secret and mfa_token:
            totp = pyotp.TOTP(mfa_secret)
            if not totp.verify(mfa_token):
                return jsonify({"success": False, "message": "Invalid Authenticator Code"})
        
        # 3. Success
        session['user_id'] = user.id
        session['role'] = user.role
        return jsonify({"success": True, "redirect": url_for('home')})

    # Standard GET request returns HTML
    return render_template('login.html', users=User.get_all())

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/switch_role', methods=['POST'])
def switch_role():
    """API endpoint to switch user identity via password check"""
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
    plantations = Plantation.get_all()
    return render_template('dashboard.html', plantations=plantations)

# Add a placeholder route for creating a farm if you don't have one yet
@app.route('/farms/create', methods=['GET', 'POST'])
@login_required
def create_plantation():
    if request.method == 'POST':
        # Logic to add farm to DB (You can implement the DB insert here)
        # For now, just redirect back
        flash("New farm created successfully!", "success")
        return redirect(url_for('home'))
    return render_template('update_plantation.html', plantation=None)

@app.route('/farms')
@login_required
def view_farms():
    plantations = Plantation.get_all()
    return render_template('farms_list.html', plantations=plantations)

@app.route('/plantation/<int:plantation_id>')
@login_required
def view_plantation(plantation_id):
    plantation = Plantation.get_by_id(plantation_id)
    if not plantation:
        flash('Plantation not found', 'error')
        return redirect(url_for('view_farms'))
    return render_template('view_plantation.html', plantation=plantation)

@app.route('/plantation/<int:plantation_id>/update', methods=['GET', 'POST'])
@login_required
def update_plantation(plantation_id):
    plantation = Plantation.get_by_id(plantation_id)
    if not plantation:
        flash('Plantation not found', 'error')
        return redirect(url_for('view_farms'))
    
    if request.method == 'POST':
        # logic to support the Jinja2 errors object in your HTML
        errors = {}
        number = request.form.get('number')
        name = request.form.get('name')
        date_created = request.form.get('date_created')

        if not number: errors['number'] = ['Serial Number is required.']
        if not name: errors['name'] = ['Farm Name is required.']
        
        # Date regex validation (Basic DD/MM/YYYY)
        if not re.match(r'\d{2}/\d{2}/\d{4}', date_created):
             errors['date_created'] = ['Format must be DD/MM/YYYY']

        if errors:
            return render_template('update_plantation.html', plantation=plantation, errors=errors, form_data=request.form)

        plantation.number = number
        plantation.name = name
        plantation.date_created = date_created
        plantation.update()
        
        flash('Farm updated successfully!', 'success')
        return redirect(url_for('view_farms'))
    
    return render_template('update_plantation.html', plantation=plantation)

 
@app.route("/plantations/<int:plantation_id>/delete", methods=["POST"])
@login_required
def delete_plantation(plantation_id):
    conn = db.get_connection()
    conn.execute(
        "UPDATE plantations SET is_deleted = 1, date_deleted = ? WHERE id = ?",
        (datetime.now().strftime("%d/%m/%Y"), plantation_id)
    )
    conn.commit()
    conn.close()
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
    # In a real app, you would verify email exists in DB here
    # For now, we simulate the success
    flash(f'Password reset link sent to {email}', 'success')
    return redirect(url_for('login'))
 
@app.route('/users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if g.user.role != 'admin':
        flash("Access Denied: Admins Only", "error")
        return redirect(url_for('home'))

    if request.method == 'POST':
        # Default password is always 123 for new users
        default_pw = "123"
        
        success = User.create(
            request.form['username'], 
            request.form['email'], # New Field
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
    """Simulates the Real-time AI Library"""
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