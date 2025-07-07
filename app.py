

# Standard library imports
import os
import json
import sqlite3
import string
import random
import uuid
from datetime import datetime, timedelta
from io import BytesIO

# Flask imports
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from flask_session import Session
from werkzeug.utils import secure_filename

# Third-party imports
import qrcode
from itsdangerous import URLSafeSerializer
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Application imports
from utils.email_notification import send_email
from utils.flight_api import get_flight_info
from extensions import get_db_connection

# Create the Flask app
app = Flask(__name__)

# Configure session
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key

# Email settings file path
EMAIL_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), 'email_settings.json')

# Register blueprints - AFTER app is created
from routes.housing import housing_bp
app.register_blueprint(housing_bp, url_prefix='/housing')

# Load email settings function
def load_email_settings():
    if os.path.exists(EMAIL_SETTINGS_PATH):
        with open(EMAIL_SETTINGS_PATH, 'r') as f:
            return json.load(f)
    return {
        'smtp_server': '',
        'smtp_port': '',
        'smtp_email': '',
        'smtp_password': '',
        'smtp_tls': True
    }

def save_email_settings(settings):
    with open(EMAIL_SETTINGS_PATH, 'w') as f:
        json.dump(settings, f)

# Settings page for email configuration
@app.route('/dashboard/settings', methods=['GET', 'POST'])
def dashboard_settings():
    if request.method == 'POST':
        settings = {
            'smtp_server': request.form['smtp_server'],
            'smtp_port': int(request.form['smtp_port']),
            'smtp_email': request.form['smtp_email'],
            'smtp_password': request.form['smtp_password'],
            'smtp_tls': request.form['smtp_tls'] == '1'
        }
        save_email_settings(settings)
        flash('Email settings saved!', 'success')
        return redirect(url_for('dashboard_settings'))
    settings = load_email_settings()
    return render_template('settings.html', settings=settings, title='Email Settings')

# Database initialization
def init_db():
    """Initialize the SQLite database"""
    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hackathons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            location TEXT,
            max_participants INTEGER,
            prize_pool TEXT,
            rules TEXT,
            contact_email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hackathon_code TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            team_name TEXT,
            skills TEXT,
            experience_level TEXT,
            interests TEXT,
            dietary_restrictions TEXT,
            tshirt_size TEXT,
            emergency_contact TEXT,
            newsletter TEXT,
            code_of_conduct TEXT,
            ticket_id TEXT UNIQUE,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hackathon_code) REFERENCES hackathons (code)
        )
    ''')

    # Add housing table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hackathon_code TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            image_url TEXT,
            address TEXT,
            capacity INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hackathon_code) REFERENCES hackathons (code)
        )
    ''')
    
    # Add capacity column to existing housing table if it doesn't exist
    try:
        cursor.execute('ALTER TABLE housing ADD COLUMN capacity INTEGER')
    except Exception:
        pass
    
    # Add house column to participants if not exists
    try:
        cursor.execute('ALTER TABLE participants ADD COLUMN house TEXT')
    except Exception:
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS login_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_email TEXT NOT NULL,
            code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            is_used BOOLEAN DEFAULT FALSE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checklists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER NOT NULL,
            item_description TEXT NOT NULL,
            is_completed BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (participant_id) REFERENCES participants (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hackathon_checklist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hackathon_code TEXT NOT NULL,
            item_description TEXT NOT NULL,
            FOREIGN KEY (hackathon_code) REFERENCES hackathons (code)
        )
    ''')
    
    # Clear existing data
    cursor.execute('DELETE FROM hackathons')
    cursor.execute('DELETE FROM participants')
    cursor.execute('DELETE FROM checklists')
    cursor.execute('DELETE FROM hackathon_checklist_items')
    
    # Insert Demo Hackathon
    demo_hackathon_code = 'DEMO01'
    cursor.execute('''
        INSERT INTO hackathons (code, name, description, start_date, end_date, location, max_participants, prize_pool, rules, contact_email)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        demo_hackathon_code, 
        'Tommy Timecrunch Demo Hackathon', 
        'A fun-filled weekend of coding and innovation!',
        '2025-08-15', 
        '2025-08-17', 
        'Virtual', 
        100, 
        '$5,000', 
        '1. Be respectful. 2. Have fun. 3. Code something amazing.', 
        'julianstosse@icloud.com'
    ))

    # Insert Demo Participant
    demo_ticket_id = str(uuid.uuid4())
    cursor.execute('''
        INSERT INTO participants (hackathon_code, name, email, phone, team_name, skills, experience_level, interests, dietary_restrictions, tshirt_size, emergency_contact, newsletter, code_of_conduct, ticket_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        demo_hackathon_code,
        'Julian Stosse',
        'julianstosse@icloud.com',
        '123-456-7890',
        'The Coders',
        'Python, Flask, JavaScript',
        'Intermediate',
        'AI, Web Dev',
        'None',
        'L',
        'Jane Doe - 555-555-5555',
        'on',
        'on',
        demo_ticket_id
    ))

    # Get demo participant ID
    cursor.execute("SELECT id FROM participants WHERE email = 'julianstosse@icloud.com'")
    demo_participant_id = cursor.fetchone()[0]

    # Insert Demo General Checklist Items for the hackathon
    default_checklist_items = [
        "Book flights and accommodation",
        "Join the official hackathon Discord server",
        "Brainstorm project ideas",
        "Form or join a team",
        "Pack your bags (don't forget your laptop charger!)"
    ]
    for item in default_checklist_items:
        cursor.execute("INSERT INTO hackathon_checklist_items (hackathon_code, item_description) VALUES (?, ?)", (demo_hackathon_code, item))


    conn.commit()
    conn.close()

def generate_hackathon_code():
    """Generate a unique 6-character alphanumeric code"""
    characters = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(characters, k=6))
        # Check if code already exists
        conn = sqlite3.connect('hackathons.db')
        cursor = conn.cursor()
        cursor.execute('SELECT code FROM hackathons WHERE code = ?', (code,))
        if not cursor.fetchone():
            conn.close()
            return code
        conn.close()

def get_hackathon_by_code(code):
    """Get hackathon details by code"""
    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM hackathons WHERE code = ?', (code,))
    hackathon = cursor.fetchone()
    conn.close()
    return hackathon

@app.route('/')
def index():
    """Home page route"""
    return render_template('index.html', title='Welcome to Tommy Timecrunch')

@app.route('/about')
def about():
    """About page route"""
    return render_template('about.html', title='About Tommy Timecrunch')

@app.route('/contact')
def contact():
    """Contact page route"""
    contact_info = {
        'email': 'tommy@timecrunch.com',
        'phone': '(555) 123-4567',
        'address': '123 Main St, Anytown, USA'
    }
    return render_template('contact.html', title='Contact Us', contact=contact_info)

@app.route('/create-hackathon')
def create_hackathon():
    """Create hackathon page route"""
    return render_template('create_hackathon.html', title='Create Hackathon')

@app.route('/create-hackathon', methods=['POST'])
def create_hackathon_post():
    """Handle hackathon creation"""
    try:
        # Get form data
        name = request.form['name']
        description = request.form['description']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        location = request.form['location']
        max_participants = request.form['max_participants']
        prize_pool = request.form['prize_pool']
        rules = request.form['rules']
        contact_email = request.form['contact_email']

        # Generate unique code
        code = generate_hackathon_code()

        # Insert into database
        conn = sqlite3.connect('hackathons.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO hackathons (code, name, description, start_date, end_date, 
                                  location, max_participants, prize_pool, rules, contact_email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (code, name, description, start_date, end_date, location, 
              max_participants, prize_pool, rules, contact_email))

        conn.commit()
        conn.close()

        # Send email notification to organizer (optional, do not fail if email fails)
        try:
            email_subject = f"Your Hackathon '{name}' Has Been Created!"
            email_body = render_template('email/hackathon_created.html', 
                                         hackathon_name=name, 
                                         hackathon_code=code, 
                                         dashboard_link=url_for('dashboard_view', _external=True))
            send_email(contact_email, email_subject, email_body)
        except Exception as email_exc:
            print("[WARN] Could not send hackathon created email:", email_exc)

        flash(f'Hackathon created successfully! Your code is: {code}', 'success')
        return redirect(url_for('hackathon_created', code=code))

    except Exception as e:
        print("[ERROR] Create hackathon error:", e)
        flash(f'Error creating hackathon: {str(e)}', 'error')
        return redirect(url_for('create_hackathon'))

@app.route('/hackathon-created/<code>')
def hackathon_created(code):
    """Show hackathon created confirmation"""
    hackathon = get_hackathon_by_code(code)
    if not hackathon:
        flash('Hackathon not found', 'error')
        return redirect(url_for('index'))
    
    return render_template('hackathon_created.html', title='Hackathon Created', code=code, hackathon=hackathon)

@app.route('/dashboard')
def dashboard():
    """Dashboard login page"""
    return render_template('dashboard_login.html', title='Dashboard Login')

@app.route('/dashboard', methods=['POST'])
def dashboard_login():
    """Handle dashboard login and send verification code."""
    code = request.form['code'].upper()
    hackathon = get_hackathon_by_code(code)

    if not hackathon:
        flash('Invalid hackathon code.', 'error')
        return redirect(url_for('dashboard'))

    # hackathon tuple indices: 0:id, 1:code, 2:name, ..., 10:contact_email
    contact_email = hackathon[10]
    if not contact_email:
        flash(f"No contact email is configured for hackathon '{code}'. Cannot send login code.", 'error')
        return redirect(url_for('dashboard'))

    # Generate and store login code
    login_code = ''.join(random.choices(string.digits, k=6))
    expires_at = datetime.now() + timedelta(minutes=15)

    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    # Store the code, associating it with the admin's email (the hackathon contact email)
    cursor.execute("""
        INSERT INTO login_codes (participant_email, code, expires_at)
        VALUES (?, ?, ?)
    """, (contact_email, login_code, expires_at))
    conn.commit()
    conn.close()

    # Send login code via email
    email_subject = f"Your Admin Login Code for {hackathon[2]}"
    email_body = render_template('email/login_code.html', login_code=login_code)
    email_settings = load_email_settings()

    # Print the code to terminal for debugging/development
    print(f"\n----- VERIFICATION CODE -----")
    print(f"Email: {contact_email}")
    print(f"Code: {login_code}")
    print(f"Hackathon Code: {code}")
    print(f"---------------------------\n")

    if not send_email(contact_email, email_subject, email_body, email_settings=email_settings):
        flash('Failed to send verification code. Please check the email settings and server logs.', 'error')
        return redirect(url_for('dashboard'))

    flash(f'A verification code has been sent to {contact_email}.', 'success')
    # Redirect to the verification page
    return redirect(url_for('dashboard_verify_code', code=code))


@app.route('/dashboard/verify/<code>', methods=['GET', 'POST'])
def dashboard_verify_code(code):
    """Verify admin login code"""
    hackathon = get_hackathon_by_code(code)
    if not hackathon:
        flash('Invalid hackathon code.', 'error')
        return redirect(url_for('dashboard'))

    contact_email = hackathon[10]

    if request.method == 'POST':
        verification_code = request.form['verification_code']

        conn = sqlite3.connect('hackathons.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM login_codes
            WHERE participant_email = ? AND code = ? AND is_used = FALSE
        ''', (contact_email, verification_code))
        login_code_data = cursor.fetchone()

        if login_code_data:
            expires_at = datetime.fromisoformat(login_code_data[4])
            if datetime.now() > expires_at:
                flash('Login code has expired. Please request a new one.', 'error')
                return redirect(url_for('dashboard'))

            # Mark code as used
            cursor.execute('UPDATE login_codes SET is_used = TRUE WHERE id = ?', (login_code_data[0],))
            conn.commit()
            conn.close()

            # Log the user in
            session['hackathon_code'] = code.upper()
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard_view', code=code))
        else:
            conn.close()
            flash('Invalid login code.', 'error')
            return redirect(url_for('dashboard_verify_code', code=code))

    return render_template('dashboard_verify_code.html', title='Verify Admin Login', code=code, email=contact_email)


@app.route('/dashboard/view/<string:code>')
def dashboard_view(code):
    """Dashboard view for managing hackathon"""
    if 'hackathon_code' not in session:
        flash('Please login to access the dashboard', 'error')
        return redirect(url_for('dashboard'))
    
    code = session['hackathon_code']
    hackathon = get_hackathon_by_code(code)
    
    if not hackathon:
        flash('Hackathon not found', 'error')
        session.pop('hackathon_code', None)
        return redirect(url_for('dashboard'))
    
    # Convert tuple to dict for easier template access
    hackathon_dict = {
        'id': hackathon[0],
        'code': hackathon[1],
        'name': hackathon[2],
        'description': hackathon[3],
        'start_date': hackathon[4],
        'end_date': hackathon[5],
        'location': hackathon[6],
        'max_participants': hackathon[7],
        'prize_pool': hackathon[8],
        'rules': hackathon[9],
        'contact_email': hackathon[10],
        'created_at': hackathon[11]
    }
    
    # Fetch general checklist items for this hackathon
    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, item_description FROM hackathon_checklist_items WHERE hackathon_code = ?", (code,))
    checklist_items = [{'id': row[0], 'item_description': row[1]} for row in cursor.fetchall()]
    conn.close()

    # Fetch housing locations for this hackathon
    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, image_url, address, capacity FROM housing WHERE hackathon_code = ?", (code,))
    housing_locations = [{'id': row[0], 'name': row[1], 'description': row[2], 'image_url': row[3], 'address': row[4], 'capacity': row[5]} for row in cursor.fetchall()]
    conn.close()

    return render_template('dashboard.html', title='Hackathon Dashboard', hackathon=hackathon_dict, checklist_items=checklist_items, housing_locations=housing_locations)

@app.route('/dashboard/edit-checklist', methods=['POST'])
def edit_checklist():
    """Add a new item to the general hackathon checklist"""
    if 'hackathon_code' not in session:
        flash('Please login to access the dashboard', 'error')
        return redirect(url_for('dashboard'))
    code = session['hackathon_code']
    new_item = request.form.get('new_item')
    if not new_item:
        flash('Please enter a checklist item.', 'error')
        return redirect(url_for('dashboard_view'))
    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO hackathon_checklist_items (hackathon_code, item_description) VALUES (?, ?)", (code, new_item))
    conn.commit()
    conn.close()
    flash('Checklist item added!', 'success')
    return redirect(url_for('dashboard_view'))

@app.route('/dashboard/delete-checklist-item/<int:item_id>', methods=['POST'])
def delete_checklist_item(item_id):
    """Delete a checklist item from the general hackathon checklist"""
    if 'hackathon_code' not in session:
        flash('Please login to access the dashboard', 'error')
        return redirect(url_for('dashboard'))
    code = session['hackathon_code']
    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM hackathon_checklist_items WHERE id = ? AND hackathon_code = ?", (item_id, code))
    conn.commit()
    conn.close()
    flash('Checklist item deleted.', 'success')
    return redirect(url_for('dashboard_view'))

@app.route('/dashboard/send-email', methods=['GET', 'POST'])
def send_mass_email():
    """Send mass email to participants"""
    if 'hackathon_code' not in session:
        flash('Please login to access the dashboard', 'error')
        return redirect(url_for('dashboard'))

    code = session['hackathon_code']
    hackathon = get_hackathon_by_code(code)

    if not hackathon:
        flash('Hackathon not found', 'error')
        session.pop('hackathon_code', None)
        return redirect(url_for('dashboard'))

    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, email FROM participants WHERE hackathon_code = ?', (code,))
    participants = cursor.fetchall()
    conn.close()

    if request.method == 'POST':
        subject = request.form['subject']
        body = request.form['body']
        recipients = request.form.getlist('recipients')
        attachment = request.files.get('attachment')

        if not recipients:
            flash('Please select at least one recipient.', 'error')
            return redirect(url_for('send_mass_email'))

        attachment_path = None
        if attachment and attachment.filename:
            upload_folder = os.path.join(app.root_path, 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            attachment_path = os.path.join(upload_folder, attachment.filename)
            attachment.save(attachment_path)

        # Use custom email settings if available
        email_settings = load_email_settings()
        success = send_email(recipients, subject, body, attachment_path, email_settings=email_settings)

        if attachment_path:
            os.remove(attachment_path)  # Clean up the uploaded file

        if success:
            flash('Emails sent successfully!', 'success')
        else:
            flash('An error occurred while sending emails.', 'error')
        
        return redirect(url_for('dashboard_view'))

    return render_template('send_email.html', title='Send Email to Participants', hackathon_name=hackathon[2], participants=participants)


@app.route('/logout')
def logout():
    """Logout from dashboard"""
    session.pop('hackathon_code', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/qr-generator')
def qr_generator():
    """QR Code generator page"""
    hackathon = None
    if 'hackathon_code' in session:
        hackathon = get_hackathon_by_code(session['hackathon_code'])
        if hackathon:
            hackathon = {
                'code': hackathon[1],
                'name': hackathon[2]
            }
    return render_template('qr_generator.html', title='QR Code Generator', hackathon=hackathon)

@app.route('/qr-display')
def qr_display():
    """QR Code display page for current hackathon"""
    if 'hackathon_code' not in session:
        flash('Please log in to view QR code', 'error')
        return redirect(url_for('dashboard_login'))
    
    hackathon = get_hackathon_by_code(session['hackathon_code'])
    if not hackathon:
        flash('Hackathon not found', 'error')
        return redirect(url_for('dashboard_login'))
    
    hackathon_dict = {
        'code': hackathon[1],
        'name': hackathon[2],
        'description': hackathon[3]
    }
    
    return render_template('qr_display.html', title=f'QR Code - {hackathon[2]}', hackathon=hackathon_dict)

@app.route('/register/<code>')
def participant_register(code):
    """Participant registration form"""
    hackathon = get_hackathon_by_code(code.upper())
    if not hackathon:
        flash('Invalid hackathon code', 'error')
        return redirect(url_for('index'))
    
    # Convert tuple to dict for easier template access
    hackathon_dict = {
        'code': hackathon[1],
        'name': hackathon[2],
        'description': hackathon[3],
        'start_date': hackathon[4],
        'end_date': hackathon[5],
        'location': hackathon[6]
    }
    
    return render_template('participant_register.html', title='Register for Hackathon', hackathon=hackathon_dict)

@app.route('/register/<code>', methods=['POST'])
def participant_register_submit(code):
    """Handle participant registration"""
    hackathon = get_hackathon_by_code(code.upper())
    if not hackathon:
        flash('Invalid hackathon code', 'error')
        return redirect(url_for('index'))
    
    # Get form data
    name = request.form['name']
    email = request.form['email']
    phone = request.form.get('phone', '')
    team_name = request.form.get('team_name', '')
    skills = request.form.get('skills', '')
    experience_level = request.form.get('experience_level', '')
    interests = request.form.get('interests_data', '')
    dietary_restrictions = request.form.get('dietary_restrictions', '')
    tshirt_size = request.form.get('tshirt_size', '')
    emergency_contact = request.form.get('emergency_contact', '')
    newsletter = request.form.get('newsletter', '')
    code_of_conduct = request.form.get('code_of_conduct', '')
    ticket_id = str(uuid.uuid4())
    
    # Check if participant already registered
    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM participants WHERE hackathon_code = ? AND email = ?', (code.upper(), email))
    if cursor.fetchone():
        conn.close()
        flash('You are already registered for this hackathon', 'error')
        return redirect(url_for('participant_register', code=code))
    
    # Insert participant
    cursor.execute('''
        INSERT INTO participants (hackathon_code, name, email, phone, team_name, skills, experience_level, 
                                interests, dietary_restrictions, tshirt_size, emergency_contact, newsletter, code_of_conduct, ticket_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (code.upper(), name, email, phone, team_name, skills, experience_level, 
          interests, dietary_restrictions, tshirt_size, emergency_contact, newsletter, code_of_conduct, ticket_id))
    
    # Get the new participant's ID
    participant_id = cursor.lastrowid

    # No per-participant checklist; general checklist is now per hackathon


    conn.commit()
    conn.close()

    # Send confirmation email to participant
    email_subject = f"You are registered for {hackathon[2]}!"
    email_body = render_template('email/participant_registered.html', 
                                 hackathon_name=hackathon[2], 
                                 participant_name=name)
    send_email(email, email_subject, email_body)
    
    flash('Registration successful!', 'success')
    return render_template('registration_success.html', title='Registration Successful', hackathon_name=hackathon[2])

@app.route('/dashboard/participants')
def dashboard_participants():
    """View participants for hackathon"""
    if 'hackathon_code' not in session:
        flash('Please login to access the dashboard', 'error')
        return redirect(url_for('dashboard'))

    code = session['hackathon_code']
    hackathon = get_hackathon_by_code(code)

    if not hackathon:
        flash('Hackathon not found', 'error')
        session.pop('hackathon_code', None)
        return redirect(url_for('dashboard'))

    # Get participants
    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, email, phone, team_name, skills, experience_level, interests, 
               dietary_restrictions, tshirt_size, emergency_contact, newsletter, code_of_conduct, registered_at
        FROM participants 
        WHERE hackathon_code = ?
        ORDER BY registered_at DESC
    ''', (code,))
    participants_data = cursor.fetchall()
    conn.close()

    # Convert to list of dictionaries
    participants = []
    for p in participants_data:
        participants.append({
            'id': p[0],
            'name': p[1],
            'email': p[2],
            'phone': p[3],
            'team_name': p[4],
            'skills': p[5],
            'experience_level': p[6],
            'interests': p[7],
            'dietary_restrictions': p[8],
            'tshirt_size': p[9],
            'emergency_contact': p[10],
            'newsletter': p[11],
            'code_of_conduct': p[12],
            'registered_at': p[13]
        })

    hackathon_dict = {
        'code': hackathon[1],
        'name': hackathon[2],
        'max_participants': hackathon[7]
    }

    registration_link = request.url_root + 'register/' + code

    return render_template('dashboard_participants.html', 
                         title='Participants', 
                         hackathon=hackathon_dict, 
                         participants=participants,
                         registration_link=registration_link,
                         participant_count=len(participants))

# --- VISA LETTER FEATURE ---
from itsdangerous import URLSafeSerializer
from flask import send_file as flask_send_file
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

visa_secret = app.secret_key + "visa"
visa_serializer = URLSafeSerializer(visa_secret)


# --- FLIGHT INFO FEATURE ---
from itsdangerous import URLSafeSerializer as URLSafeSerializer2
flight_secret = app.secret_key + "flight"
flight_serializer = URLSafeSerializer2(flight_secret)

@app.route('/dashboard/send-visa-letter/<int:participant_id>', methods=['POST'])
def send_visa_letter(participant_id):
    if 'hackathon_code' not in session:
        flash('Please login to access the dashboard', 'error')
        return redirect(url_for('dashboard'))
    code = session['hackathon_code']
    # Get participant info
    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, email FROM participants WHERE id = ? AND hackathon_code = ?', (participant_id, code))
    row = cursor.fetchone()
    conn.close()
    if not row:
        flash('Participant not found.', 'error')
        return redirect(url_for('dashboard_participants'))
    participant_name, participant_email = row
    # Generate secure links
    visa_token = visa_serializer.dumps({'participant_id': participant_id, 'email': participant_email})
    visa_form_link = url_for('visa_letter_form', token=visa_token, _external=True)
    flight_token = flight_serializer.dumps({'participant_id': participant_id, 'email': participant_email})
    flight_form_link = url_for('flight_info_form', token=flight_token, _external=True)
    # Send visa email
    visa_email_body = render_template('visa_letter_email.html', participant_name=participant_name, form_link=visa_form_link)
    flight_email_body = render_template('flight_info_email.html', participant_name=participant_name, form_link=flight_form_link)
    success1 = send_email([participant_email], 'Visa Letter Request', visa_email_body)
    success2 = send_email([participant_email], 'Submit Your Flight Information', flight_email_body)
    if success1 and success2:
        flash('Visa letter and flight info request links sent to participant.', 'success')
    else:
        flash('Failed to send one or both emails. Check email settings and logs.', 'error')
    return redirect(url_for('dashboard_participants'))

# Flight info form route
@app.route('/flight-info/<token>', methods=['GET', 'POST'])
def flight_info_form(token):
    try:
        data = flight_serializer.loads(token)
        participant_id = data['participant_id']
        participant_email = data['email']
    except Exception:
        flash('Invalid or expired link.', 'error')
        return redirect(url_for('index'))
    if request.method == 'POST':
        flight_number = request.form['flight_number']
        departure_day = request.form['departure_day']
        departure_airport = request.form['departure_airport']
        # Save flight info to DB
        conn = sqlite3.connect('hackathons.db')
        cursor = conn.cursor()
        # Add columns if not exist (for legacy DBs)
        try:
            cursor.execute('ALTER TABLE participants ADD COLUMN flight_number TEXT')
        except Exception:
            pass
        try:
            cursor.execute('ALTER TABLE participants ADD COLUMN departure_day TEXT')
        except Exception:
            pass
        try:
            cursor.execute('ALTER TABLE participants ADD COLUMN departure_airport TEXT')
        except Exception:
            pass
        try:
            cursor.execute('UPDATE participants SET flight_number = ?, departure_day = ?, departure_airport = ? WHERE id = ?', (flight_number, departure_day, departure_airport, participant_id))
            conn.commit()
        except Exception:
            pass
        conn.close()
        flash('Flight information submitted!', 'success')
        return render_template('visa_letter_sent.html')
    return render_template('flight_info_form.html')

@app.route('/visa-letter/<token>', methods=['GET', 'POST'])
def visa_letter_form(token):
    try:
        data = visa_serializer.loads(token)
        participant_id = data['participant_id']
        participant_email = data['email']
    except Exception:
        flash('Invalid or expired link.', 'error')
        return redirect(url_for('index'))

    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.name, h.name, h.start_date, h.end_date, h.location, h.contact_email
        FROM participants p
        JOIN hackathons h ON p.hackathon_code = h.code
        WHERE p.id = ?
    ''', (participant_id,))
    participant_data = cursor.fetchone()
    conn.close()

    if not participant_data:
        flash('Participant not found.', 'error')
        return redirect(url_for('index'))

    participant_name, hackathon_name, start_date, end_date, location, contact_email = participant_data

    if request.method == 'POST':
        # Get data from form
        full_name = request.form['full_name']
        dob = request.form['dob']
        passport_number = request.form['passport_number']
        nationality = request.form['nationality']
        issue_date = request.form['issue_date']
        expiry_date = request.form['expiry_date']
        address = request.form['address']

        # Load visa template
        template_path = os.path.join(os.path.dirname(__file__), 'visa_template.json')
        with open(template_path, 'r') as f:
            template_content = json.load(f)['template']

        # Replace placeholders
        letter_content = template_content.replace("{{participant_name}}", full_name)\
                                       .replace("{{dob}}", dob)\
                                       .replace("{{passport_number}}", passport_number)\
                                       .replace("{{nationality}}", nationality)\
                                       .replace("{{issue_date}}", issue_date)\
                                       .replace("{{expiry_date}}", expiry_date)\
                                       .replace("{{address}}", address)\
                                       .replace("{{hackathon_name}}", hackathon_name)\
                                       .replace("{{start_date}}", start_date)\
                                       .replace("{{end_date}}", end_date)\
                                       .replace("{{location}}", location)\
                                       .replace("{{contact_email}}", contact_email)

        # Generate PDF
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        text = p.beginText(40, 750)
        text.setFont("Helvetica", 12)
        for line in letter_content.split('\n'):
            text.textLine(line)
        p.drawText(text)
        p.showPage()
        p.save()
        buffer.seek(0)

        # Send PDF as an attachment
        send_email(
            recipient=participant_email,
            subject=f"Your Visa Invitation Letter for {hackathon_name}",
            body="Please find your visa invitation letter attached.",
            attachment_content=buffer.getvalue(),
            attachment_filename=f"Visa_Letter_{full_name}.pdf"
        )

        flash('Your visa letter has been generated and sent to your email!', 'success')
        return render_template('visa_letter_sent.html', title='Visa Letter Sent')

    return render_template('visa_letter_form.html',
                             title='Visa Letter Application',
                             participant_name=participant_name,
                             hackathon_name=hackathon_name,
                             token=token)


@app.route('/participant/select-housing', methods=['POST'])
def participant_select_housing():
    if 'participant_email' not in session:
        flash('Please login to select housing.', 'error')
        return redirect(url_for('participant_login'))

    email = session['participant_email']
    housing_id = request.form.get('housing_id')
    hackathon_code = request.form.get('hackathon_code')

    if not housing_id or not hackathon_code:
        flash('Invalid request.', 'error')
        return redirect(url_for('participant_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get participant id
    cursor.execute("SELECT id FROM participants WHERE email = ? AND hackathon_code = ?", (email, hackathon_code))
    participant_result = cursor.fetchone()
    if not participant_result:
        flash('Participant not found for this hackathon.', 'error')
        conn.close()
        return redirect(url_for('participant_dashboard'))
    participant_id = participant_result[0]

    # Check housing capacity
    cursor.execute("SELECT capacity FROM housing WHERE id = ?", (housing_id,))
    housing_result = cursor.fetchone()
    if housing_result and housing_result[0] is not None:
        cursor.execute("SELECT COUNT(id) as count FROM participants WHERE house = ? AND hackathon_code = ?", (housing_id, hackathon_code))
        assigned_count_result = cursor.fetchone()
        assigned_count = assigned_count_result[0] if assigned_count_result else 0
        if assigned_count >= housing_result[0]:
            flash('This housing location is already full.', 'error')
            conn.close()
            return redirect(url_for('participant_dashboard'))

    # Assign house to participant
    cursor.execute("UPDATE participants SET house = ? WHERE id = ?", (housing_id, participant_id))
    conn.commit()
    conn.close()

    flash('Your housing has been selected successfully!', 'success')
    return redirect(url_for('participant_dashboard'))


@app.route('/participant/login', methods=['GET', 'POST'])
def participant_login():
    """Participant login page"""
    if request.method == 'POST':
        email = request.form['email']
        code = request.form['code']

        # Validate email and code
        if not email or not code:
            flash('Please enter both email and code.', 'error')
            return redirect(url_for('participant_login'))

        # Check if the code is valid
        conn = sqlite3.connect('hackathons.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM login_codes
            WHERE participant_email = ? AND code = ? AND is_used = FALSE
        ''', (email, code))
        login_code_data = cursor.fetchone()

        if login_code_data:
            expires_at = datetime.fromisoformat(login_code_data[4])
            if datetime.now() > expires_at:
                conn.close()
                flash('Login code has expired. Please request a new one.', 'error')
                return redirect(url_for('participant_login'))

            # Mark code as used
            cursor.execute('UPDATE login_codes SET is_used = TRUE WHERE id = ?', (login_code_data[0],))
            
            # Get participant ID
            cursor.execute('SELECT id FROM participants WHERE email = ?', (email,))
            participant = cursor.fetchone()
            
            conn.commit()
            conn.close()

            if not participant:
                flash('Participant not found.', 'error')
                return redirect(url_for('participant_login'))

            # Log the user in
            session['participant_id'] = participant[0]
            session['participant_email'] = email
            flash('Login successful!', 'success')
            return redirect(url_for('participant_dashboard'))
        else:
            conn.close()
            flash('Invalid login code. Please try again.', 'error')
            return redirect(url_for('participant_login'))

    return render_template('participant_login.html', title='Participant Login')

@app.route('/participant/verify-code', methods=['POST'])
def participant_verify_code():
    """Verify participant login code"""
    data = request.get_json()
    if not data or 'email' not in data or 'code' not in data:
        return jsonify({'success': False, 'message': 'Email and code are required.'}), 400

    email = data['email']
    code = data['code']

    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM login_codes
        WHERE participant_email = ? AND code = ? AND is_used = FALSE
    ''', (email, code))
    login_code_data = cursor.fetchone()

    if login_code_data:
        expires_at = datetime.fromisoformat(login_code_data[4])
        if datetime.now() > expires_at:
            conn.close()
            return jsonify({'success': False, 'message': 'Login code has expired. Please request a new one.'})

        # Mark code as used
        cursor.execute('UPDATE login_codes SET is_used = TRUE WHERE id = ?', (login_code_data[0],))
        # Get participant ID
        cursor.execute('SELECT id FROM participants WHERE email = ?', (email,))
        participant = cursor.fetchone()
        conn.commit()
        conn.close()

        if not participant:
            return jsonify({'success': False, 'message': 'Participant not found.'})

        # Log the user in
        session['participant_id'] = participant[0]
        session['participant_email'] = email
        return jsonify({'success': True, 'redirect_url': url_for('participant_dashboard')})
    else:
        conn.close()
        return jsonify({'success': False, 'message': 'Invalid login code.'})

@app.route('/participant/logout')
def participant_logout():
    """Logout participant"""
    session.pop('participant_email', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/participant/send-verification-code', methods=['POST'])
def participant_send_verification_code():
    """Send verification code to participant email"""
    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({'message': 'Email is required.'}), 400

    email = data['email']

    # Check if participant is registered for any hackathon
    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM participants WHERE email = ?', (email,))
    participant = cursor.fetchone()
    
    if not participant:
        conn.close()
        return jsonify({'message': 'This email is not registered for any hackathon.'}), 404

    # Generate and store login code
    login_code = ''.join(random.choices(string.digits, k=6))
    expires_at = datetime.now() + timedelta(minutes=15) # Code expires in 15 minutes

    cursor.execute('''
        INSERT INTO login_codes (participant_email, code, expires_at)
        VALUES (?, ?, ?)
    ''', (email, login_code, expires_at))
    conn.commit()
    conn.close()

    # Send login code via email
    email_subject = "Your Login Code for Tommy Timecrunch"
    email_body = render_template('email/login_code.html', login_code=login_code)
    
    # Load email settings from the root directory
    email_settings = load_email_settings()
    
    # Print the code to terminal for debugging/development
    print(f"\n----- PARTICIPANT VERIFICATION CODE -----")
    print(f"Email: {email}")
    print(f"Code: {login_code}")
    print(f"---------------------------\n")

    if not send_email(email, email_subject, email_body, email_settings=email_settings):
        return jsonify({'message': 'Failed to send verification code. Email server might be down or incorrectly configured.'}), 500

    return jsonify({'message': f'Verification code sent to {email}.'})


@app.route('/participant/dashboard')
def participant_dashboard():
    if 'participant_id' not in session:
        flash('Please login to view your dashboard.', 'error')
        return redirect(url_for('participant_login'))

    participant_id = session['participant_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get participant's email
    cursor.execute('SELECT email FROM participants WHERE id = ?', (participant_id,))
    participant_email_row = cursor.fetchone()
    if not participant_email_row:
        flash('Participant not found.', 'error')
        session.pop('participant_id', None)
        conn.close()
        return redirect(url_for('participant_login'))
    participant_email = participant_email_row[0]

    # Get all registrations for this participant by email
    cursor.execute('''
        SELECT p.id, p.hackathon_code, p.name, p.email, p.phone, p.team_name, p.skills, 
               p.experience_level, p.interests, p.dietary_restrictions, p.tshirt_size, 
               p.emergency_contact, p.newsletter, p.code_of_conduct, p.ticket_id, 
               p.registered_at, p.house, h.name as hackathon_name, h.start_date, h.end_date
        FROM participants p
        JOIN hackathons h ON p.hackathon_code = h.code
        WHERE p.email = ?
        ORDER BY h.start_date DESC
    ''', (participant_email,))
    registrations_data = cursor.fetchall()

    # For each registration, fetch available housing for that hackathon
    registrations = []
    checklist_items_by_hackathon = {}
    for reg in registrations_data:
        # Fetch housing options for this hackathon
        cursor2 = get_db_connection().cursor()
        cursor2.execute("SELECT id, name, description, image_url, address, capacity FROM housing WHERE hackathon_code = ?", (reg[1],))
        housing_options = [
            {'id': row[0], 'name': row[1], 'description': row[2], 'image_url': row[3], 'address': row[4], 'capacity': row[5]}
            for row in cursor2.fetchall()
        ]
        # Fetch checklist items for this hackathon
        cursor2.execute("SELECT id, item_description FROM hackathon_checklist_items WHERE hackathon_code = ?", (reg[1],))
        checklist_items = [{'id': row[0], 'item_description': row[1]} for row in cursor2.fetchall()]
        checklist_items_by_hackathon[reg[1]] = checklist_items
        cursor2.connection.close()
        registrations.append({
            'id': reg[0],
            'hackathon_code': reg[1],
            'name': reg[2],
            'email': reg[3],
            'phone': reg[4],
            'team_name': reg[5],
            'skills': reg[6],
            'experience_level': reg[7],
            'interests': reg[8],
            'dietary_restrictions': reg[9],
            'tshirt_size': reg[10],
            'emergency_contact': reg[11],
            'newsletter': reg[12],
            'code_of_conduct': reg[13],
            'ticket_id': reg[14],
            'registered_at': reg[15],
            'house': reg[16],
            'hackathon_name': reg[17],
            'hackathon_start_date': reg[18],
            'hackathon_end_date': reg[19],
            'housing_options': housing_options,
            'checklist_items': checklist_items
        })

    # Assuming the primary participant details are the same across registrations,
    # we can take them from the first registration.
    participant = registrations[0] if registrations else None

    return render_template('participant_dashboard.html',
                           title='My Dashboard',
                           participant=participant,
                           registrations=registrations)

# Ticket verification route for admin dashboard QR scanner
@app.route('/dashboard/verify-ticket/<ticket_id>')
def dashboard_verify_ticket(ticket_id):
    # Only allow access if admin is logged in for a hackathon
    if 'hackathon_code' not in session:
        return '<div class="alert alert-danger">Not authorized. Please log in to the dashboard.</div>'
    code = session['hackathon_code']
    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT name, email FROM participants WHERE ticket_id = ? AND hackathon_code = ?
    ''', (ticket_id, code))
    participant = cursor.fetchone()
    conn.close()
    if participant:
        return f'''
        <div class="alert alert-success">
            <h6><i class="fas fa-check-circle me-2"></i> Valid Ticket</h6>
            <p><strong>Participant:</strong> <span class="participant-name">{participant[0]}</span></p>
            <p><strong>Email:</strong> {participant[1]}</p>
            <p><strong>Ticket ID:</strong> {ticket_id}</p>
        </div>
        '''
    else:
        return f'''
        <div class="alert alert-danger">
            <h6><i class="fas fa-times-circle me-2"></i> Invalid Ticket</h6>
            <p>Ticket ID: {ticket_id}</p>
            <p>This ticket is not valid for this hackathon.</p>
        </div>
        '''

# Participant profile route for admin dashboard
@app.route('/dashboard/participant/<int:participant_id>')
def participant_profile(participant_id):
    if 'hackathon_code' not in session:
        flash('Please login to access the dashboard', 'error')
        return redirect(url_for('dashboard'))
    code = session['hackathon_code']
    conn = sqlite3.connect('hackathons.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, email, phone, team_name, skills, experience_level, interests,
               dietary_restrictions, tshirt_size, emergency_contact, newsletter, code_of_conduct, registered_at,
               flight_number, departure_day, departure_airport, ticket_id
        FROM participants WHERE id = ? AND hackathon_code = ?
    ''', (participant_id, code))
    row = cursor.fetchone()
    conn.close()
    participant = None
    flight_info = None
    flight_map_url = None
    if row:
        participant = {
            'id': row[0],
            'name': row[1],
            'email': row[2],
            'phone': row[3],
            'team_name': row[4],
            'skills': row[5],
            'experience_level': row[6],
            'interests': row[7],
            'dietary_restrictions': row[8],
            'tshirt_size': row[9],
            'emergency_contact': row[10],
            'newsletter': row[11],
            'code_of_conduct': row[12],
            'registered_at': row[13],
            'flight_number': row[14] if len(row) > 14 else None,
            'departure_day': row[15] if len(row) > 15 else None,
            'departure_airport': row[16] if len(row) > 16 else None,
            'ticket_id': row[17] if len(row) > 17 else None
        }
        # Query OpenSky (via get_flight_info) if flight_number is present
        if participant['flight_number']:
            try:
                flight_info = get_flight_info(participant['flight_number'], participant['departure_day'])
                # Optionally, build a map URL if coordinates are available
                if flight_info and 'departure' in flight_info and 'arrival' in flight_info:
                    dep = flight_info['departure']
                    arr = flight_info['arrival']
                    if dep.get('airport', {}).get('lat') and arr.get('airport', {}).get('lat'):
                        dep_lat = dep['airport']['lat']
                        dep_lon = dep['airport']['lon']
                        arr_lat = arr['airport']['lat']
                        arr_lon = arr['airport']['lon']
                        flight_map_url = f"https://static-maps.yandex.ru/1.x/?l=map&pt={dep_lon},{dep_lat},pm2blm~{arr_lon},{arr_lat},pm2grm&z=3&size=650,300"
            except Exception as e:
                print(f"Flight info error: {e}")
    print(f"Participant profile accessed: {participant['name'] if participant else 'Unknown'}, flight info: {flight_info}, flight map URL: {flight_map_url}")
    return render_template('participant_profile.html', participant=participant, flight_info=flight_info, flight_map_url=flight_map_url, title='Participant Profile')


# Serve QR code image for a participant's ticket
@app.route('/qr/ticket/<ticket_id>')
def generate_ticket_qr(ticket_id):
    # Generate a QR code image for the ticket_id
    import qrcode
    from flask import send_file
    import io
    img = qrcode.make(ticket_id)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')


# --- MAIN ENTRY POINT ---
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Tommy Timecrunch Hackathon App')
    parser.add_argument('--init-db', action='store_true', help='Initialize the database and exit')
    parser.add_argument('--host', default='127.0.0.1', help='Host to run the server on')
    parser.add_argument('--port', default=5000, type=int, help='Port to run the server on')
    parser.add_argument('--debug', action='store_true', help='Run Flask in debug mode')
    args = parser.parse_args()

    if args.init_db:
        print('Initializing database...')
        init_db()
        print('Database initialized.')
    else:
        app.run(host=args.host, port=args.port, debug=args.debug)