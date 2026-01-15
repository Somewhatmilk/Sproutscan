from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, g
from database import Database, Plantation, User
import re
from werkzeug.security import check_password_hash
from datetime import datetime
import random
import functools

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

# --- AUTH ROUTES ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.get_by_username(username)
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials', 'error')
            
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
    return render_template('farmmap.html')

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

# --- USER MANAGEMENT (Admin Only) ---
@app.route('/users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if g.user.role != 'admin':
        flash("Access Denied: Admins Only", "error")
        return redirect(url_for('home'))

    if request.method == 'POST':
        # Simple Add User Logic
        User.create(
            request.form['username'], request.form['password'],
            request.form['role'], request.form['name'],
            request.form['bio'], "#" + "".join([random.choice('0123456789ABCDEF') for j in range(6)])
        )
        flash("User added successfully", "success")
    
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