from flask import Flask, render_template, request, redirect, url_for, flash
from database import Database, Plantation
import re
from datetime import datetime
from flask import flash

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Required for flash messages

# Initialize database
db = Database()

def validate_serial_number(number):
    """Validate serial number"""
    errors = []
    
    if not number or number.strip() == '':
        errors.append('Serial number is required')
        return errors
    
    number = number.strip()
    
    if len(number) < 2:
        errors.append('Serial number must be at least 2 characters')
    
    if len(number) > 10:
        errors.append('Serial number must not exceed 10 characters')
    
    if not re.match(r'^[a-zA-Z0-9]+$', number):
        errors.append('Serial number must contain only letters and numbers')
    
    return errors

def validate_farm_name(name):
    """Validate farm name"""
    errors = []
    
    if not name or name.strip() == '':
        errors.append('Farm name is required')
        return errors
    
    name = name.strip()
    
    if len(name) < 3:
        errors.append('Farm name must be at least 3 characters')
    
    if len(name) > 100:
        errors.append('Farm name must not exceed 100 characters')
    
    return errors

def validate_date(date_str):
    """Validate date in DD/MM/YYYY format"""
    errors = []
    
    if not date_str or date_str.strip() == '':
        errors.append('Date is required')
        return errors
    
    date_str = date_str.strip()
    
    # Check format
    date_pattern = r'^(\d{2})/(\d{2})/(\d{4})$'
    match = re.match(date_pattern, date_str)
    
    if not match:
        errors.append('Date must be in DD/MM/YYYY format')
        return errors
    
    day, month, year = match.groups()
    day, month, year = int(day), int(month), int(year)
    
    # Validate ranges
    if day < 1 or day > 31:
        errors.append('Day must be between 01 and 31')
    
    if month < 1 or month > 12:
        errors.append('Month must be between 01 and 12')
    
    if year < 2000 or year > 2100:
        errors.append('Year must be between 2000 and 2100')
    
    # Check if date is valid
    try:
        datetime(year, month, day)
    except ValueError:
        errors.append('Please enter a valid date')
    
    return errors

@app.route('/')
def home():
    return render_template('farmmap.html')

@app.route('/farms')
def view_farms():
    plantations = Plantation.get_all()
    return render_template('farms_list.html', plantations=plantations)

@app.route('/plantation/<int:plantation_id>')
def view_plantation(plantation_id):
    plantation = Plantation.get_by_id(plantation_id)
    if not plantation:
        flash('Plantation not found', 'error')
        return redirect(url_for('view_farms'))
    return render_template('view_plantation.html', plantation=plantation)

@app.route('/plantation/<int:plantation_id>/update', methods=['GET', 'POST'])
def update_plantation(plantation_id):
    plantation = Plantation.get_by_id(plantation_id)
    
    if not plantation:
        flash('Plantation not found', 'error')
        return redirect(url_for('view_farms'))
    
    if request.method == 'POST':
        # Get form data
        number = request.form.get('number', '').strip()
        name = request.form.get('name', '').strip()
        date_created = request.form.get('date_created', '').strip()
        
        # Validate all fields
        errors = {}
        
        serial_errors = validate_serial_number(number)
        if serial_errors:
            errors['number'] = serial_errors
        
        name_errors = validate_farm_name(name)
        if name_errors:
            errors['name'] = name_errors
        
        date_errors = validate_date(date_created)
        if date_errors:
            errors['date_created'] = date_errors
        
        # If there are errors, re-render the form with errors
        if errors:
            return render_template('update_plantation.html', 
                                 plantation=plantation, 
                                 errors=errors,
                                 form_data={
                                     'number': number,
                                     'name': name,
                                     'date_created': date_created
                                 })
        
        # Update plantation
        plantation.number = number
        plantation.name = name
        plantation.date_created = date_created
        plantation.update()
        
        flash('Farm updated successfully!', 'success')
        return redirect(url_for('view_farms'))
    
    return render_template('update_plantation.html', plantation=plantation)

@app.route("/plantations/<int:plantation_id>/delete", methods=["POST"])
def delete_plantation(plantation_id):
    conn = db.get_connection()

    conn.execute(
        """
        UPDATE plantations
        SET is_deleted = 1,
            date_deleted = ?
        WHERE id = ?
        """,
        (datetime.now().strftime("%d/%m/%Y"), plantation_id)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("view_farms"))

@app.route("/farms/deleted")
def deleted_farms():
    conn = db.get_connection()
    plantations = conn.execute(
        "SELECT * FROM plantations WHERE is_deleted = 1"
    ).fetchall()
    conn.close()

    return render_template("deleted_farms.html", plantations=plantations)

@app.route("/plantations/<int:plantation_id>/restore", methods=["POST"])
def restore_plantation(plantation_id):
    conn = db.get_connection()
    conn.execute(
        "UPDATE plantations SET is_deleted = 0, date_deleted = NULL WHERE id = ?",
        (plantation_id,)
    )
    conn.commit()
    conn.close()

    flash("Farm recovered successfully!", "success")  # ✅ ADD THIS
    return redirect(url_for("deleted_farms"))


@app.route('/pestlogs')
def pest_logs():
    return render_template('pestlog.html')

@app.route('/cropstage')
def crop_stage():
    return render_template('cropstage.html')

@app.route('/reporterror')
def report_error():
    return render_template('reporterror.html')

if __name__ == '__main__':
    app.run(debug=True, port=5500)