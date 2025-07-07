import os
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, session
from werkzeug.utils import secure_filename
from datetime import datetime
from extensions import get_db_connection

# Create the blueprint
housing_bp = Blueprint('housing', __name__)

# Helper function to save uploaded images
def save_image(file):
    if not file:
        return None, None
    
    filename = secure_filename(file.filename)
    # Generate unique filename to prevent conflicts
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    
    # Create uploads directory if it doesn't exist
    uploads_dir = os.path.join(current_app.root_path, 'static/uploads/housing')
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Save the file
    file_path = os.path.join(uploads_dir, unique_filename)
    file.save(file_path)
    
    # Generate URL for the image
    image_url = url_for('static', filename=f'uploads/housing/{unique_filename}')
    
    return unique_filename, image_url

# Route to add housing
@housing_bp.route('/add-housing', methods=['GET', 'POST'])
def add_housing():
    if 'hackathon_code' not in session:
        flash('Please login to access the dashboard', 'error')
        return redirect(url_for('dashboard'))
    
    code = session['hackathon_code']
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        address = request.form['address']
        capacity = request.form.get('capacity')
        if capacity:
            capacity = int(capacity)
        else:
            capacity = None
        image = request.files.get('image')
        
        image_url = None
        if image and image.filename:
            _, image_url = save_image(image)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO housing (hackathon_code, name, description, image_url, address, capacity)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (code, name, description, image_url, address, capacity))
        conn.commit()
        conn.close()
        
        flash('Housing location added successfully!', 'success')
        return redirect(url_for('dashboard_view', code=code))
    
    return render_template('add_housing.html', title='Add Housing')

# Route to edit housing
@housing_bp.route('/edit-housing/<int:housing_id>', methods=['GET', 'POST'])
def edit_housing(housing_id):
    if 'hackathon_code' not in session:
        flash('Please login to access the dashboard', 'error')
        return redirect(url_for('dashboard'))
    
    code = session['hackathon_code']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM housing WHERE id = ? AND hackathon_code = ?', (housing_id, code))
    house = cursor.fetchone()
    conn.close()
    
    if not house:
        flash('Housing not found or you do not have permission to edit it', 'error')
        return redirect(url_for('dashboard_view', code=code))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        address = request.form['address']
        capacity = request.form.get('capacity')
        if capacity:
            capacity = int(capacity)
        else:
            capacity = None
        image = request.files.get('image')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if image and image.filename:
            _, image_url = save_image(image)
            cursor.execute('''
                UPDATE housing 
                SET name = ?, description = ?, address = ?, image_url = ?, capacity = ? 
                WHERE id = ? AND hackathon_code = ?
            ''', (name, description, address, image_url, capacity, housing_id, code))
        else:
            cursor.execute('''
                UPDATE housing 
                SET name = ?, description = ?, address = ?, capacity = ? 
                WHERE id = ? AND hackathon_code = ?
            ''', (name, description, address, capacity, housing_id, code))
        
        conn.commit()
        conn.close()
        
        flash('Housing updated successfully!', 'success')
        return redirect(url_for('dashboard_view', code=code))
    
    return render_template('edit_housing.html', house=house, code=code)

# Route to delete housing
@housing_bp.route('/delete-housing/<int:housing_id>', methods=['POST'])
def delete_housing(housing_id):
    if 'hackathon_code' not in session:
        flash('Please login to access the dashboard', 'error')
        return redirect(url_for('dashboard'))
    
    code = session['hackathon_code']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM housing WHERE id = ? AND hackathon_code = ?', (housing_id, code))
    conn.commit()
    conn.close()
    
    flash('Housing deleted successfully', 'success')
    return redirect(url_for('dashboard_view', code=code))

# Route for housing details
@housing_bp.route('/housing-details/<int:housing_id>')
def housing_details(housing_id):
    if 'hackathon_code' not in session:
        flash('Please login to access the dashboard', 'error')
        return redirect(url_for('dashboard'))
    
    code = session['hackathon_code']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get hackathon details
    cursor.execute('SELECT * FROM hackathons WHERE code = ?', (code,))
    hackathon = cursor.fetchone()
    
    cursor.execute('SELECT * FROM housing WHERE id = ? AND hackathon_code = ?', (housing_id, code))
    house_row = cursor.fetchone()
    
    if not house_row:
        conn.close()
        flash('Housing not found', 'error')
        return redirect(url_for('dashboard_view', code=code))
    
    # Get assigned participants count and list
    cursor.execute('SELECT COUNT(id) as count FROM participants WHERE house = ? AND hackathon_code = ?', (housing_id, code))
    assigned_count = cursor.fetchone()['count']

    cursor.execute('SELECT name, email, team_name FROM participants WHERE house = ? AND hackathon_code = ?', (housing_id, code))
    assigned_participants = cursor.fetchall()

    conn.close()

    house = dict(house_row)
    if house.get('created_at'):
        try:
            house['created_at'] = datetime.strptime(house['created_at'], '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            pass

    return render_template('housing_details.html', house=house, code=code, hackathon=hackathon, assigned_count=assigned_count, assigned_participants=assigned_participants)
