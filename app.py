#!/usr/bin/env python3
"""
INET Dashboard - Flask application with real-time equipment monitoring
"""

import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from threading import Lock
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables from .env file
load_dotenv()

# Import scraper from local directory
try:
    from inet_scraper_async_table import WebScraperAsync, check_if_logged_in
except ImportError:
    print("Warning: Could not import inet_scraper_async_table. Make sure inet_scraper_async_table.py is in the same directory.")
    WebScraperAsync = None
    check_if_logged_in = None

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['CONFIG_FILE'] = 'config.json'

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Thread-safe data storage
data_lock = Lock()
equipment_data = {
    'instruments': [],
    'docking_stations': [],
    'last_update': None
}

# Scheduler
scheduler = BackgroundScheduler()


class User(UserMixin):
    """Simple user model for admin authentication"""
    def __init__(self, id):
        self.id = id


@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login"""
    if user_id == '1':
        return User('1')
    return None


def load_config():
    """Load configuration from JSON file"""
    default_config = {
        'admin_username': 'admin',
        'admin_password_hash': generate_password_hash('admin'),
        'inet_username': '',
        'inet_password': '',
        'update_frequency': 60,  # minutes
        'calibration_due_soon_days': 170,
        'calibration_overdue_days': 180,
    }
    
    try:
        if os.path.exists(app.config['CONFIG_FILE']):
            with open(app.config['CONFIG_FILE'], 'r') as f:
                config = json.load(f)
                # Ensure all keys exist
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            save_config(default_config)
            return default_config
    except Exception as e:
        print(f"Error loading config: {e}")
        return default_config


def save_config(config):
    """Save configuration to JSON file"""
    try:
        with open(app.config['CONFIG_FILE'], 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


async def scrape_equipment_async():
    """Scrape equipment data from INET (async)"""
    config = load_config()
    
    if not config.get('inet_username') or not config.get('inet_password'):
        print("INET credentials not configured")
        return None
    
    try:
        from inet_scraper_async_table import scrape_table
        
        equipment_list_url = "https://inet.indsci.com/Dashboard/EquipmentList.aspx"
        results = await scrape_table(
            equipment_list_url,
            username=config.get('inet_username'),
            password=config.get('inet_password')
        )
        
        return results
    except Exception as e:
        print(f"Error scraping equipment: {e}")
        return None


def scrape_equipment():
    """Synchronous wrapper for async scraping"""
    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(scrape_equipment_async())
        loop.close()
        return results
    except Exception as e:
        print(f"Error in scrape_equipment: {e}")
        return None


def parse_equipment_datetime(date_str):
    """Parse INET date/time strings into a datetime object."""
    if not date_str:
        return None

    date_str = date_str.strip()
    formats = [
        '%m/%d/%Y %I:%M %p',  # 10/29/2025 2:00 AM
        '%m/%d/%Y %H:%M',     # 10/29/2025 14:00
        '%m/%d/%Y',           # 10/29/2025
        '%Y-%m-%d %H:%M:%S',  # 2025-10-29 14:00:00
        '%Y-%m-%d %H:%M',     # 2025-10-29 14:00
        '%Y-%m-%d',           # 2025-10-29
        '%d/%m/%Y %I:%M %p',  # 29/10/2025 2:00 AM
        '%d/%m/%Y',           # 29/10/2025
        '%m-%d-%Y',           # 10-29-2025
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def apply_calibration_status(item, due_soon_days, overdue_days):
    """Set calibration status fields based on days since last calibration."""
    item['_days_since_calibration'] = None
    item['_calibration_status'] = 'ok'

    last_cal = parse_equipment_datetime(item.get('Last Calibration Time', ''))
    if not last_cal:
        return

    days_since = (datetime.now() - last_cal).days
    item['_days_since_calibration'] = days_since

    if days_since >= overdue_days:
        item['_calibration_status'] = 'danger'
    elif days_since >= due_soon_days:
        item['_calibration_status'] = 'warning'


def categorize_equipment(equipment_list):
    """Categorize equipment into instruments and docking stations"""
    instruments = []
    docking_stations = []
    config = load_config()
    due_soon_days = config.get('calibration_due_soon_days', 170)
    overdue_days = config.get('calibration_overdue_days', 180)
    
    if not equipment_list:
        return instruments, docking_stations
    
    for item in equipment_list:
        category = item.get('Category', '').strip()
        apply_calibration_status(item, due_soon_days, overdue_days)
        if category.lower() == 'instrument':
            instruments.append(item)
        elif category.lower() == 'docking station':
            docking_stations.append(item)
    
    # Sort instruments by Equipment Group (Unit), then by Type (Model)
    instruments.sort(key=lambda x: (x.get('Equipment Group', ''), x.get('Type', '')))
    
    # Cross-reference docked instruments with their units
    # Create a lookup dictionary for instruments by serial number
    instrument_lookup = {instr.get('Serial Number', ''): instr for instr in instruments if instr.get('Serial Number')}
    
    for station in docking_stations:
        docked_serial = station.get('Instrument Currently Docked', '').strip()
        if docked_serial and docked_serial in instrument_lookup:
            docked_instrument = instrument_lookup[docked_serial]
            station['_docked_unit'] = docked_instrument.get('Equipment Group', 'N/A')
        else:
            station['_docked_unit'] = None
    
    return instruments, docking_stations


def recategorize_equipment_data():
    """Reapply calibration thresholds to the current in-memory equipment data."""
    global equipment_data

    with data_lock:
        all_items = equipment_data['instruments'] + equipment_data['docking_stations']
        if not all_items:
            return False

        instruments, docking_stations = categorize_equipment(all_items)
        equipment_data['instruments'] = instruments
        equipment_data['docking_stations'] = docking_stations
        payload = equipment_data.copy()

    socketio.emit('equipment_update', {
        'instruments': payload['instruments'],
        'docking_stations': payload['docking_stations'],
        'last_update': payload['last_update']
    }, namespace='/')
    return True


def update_equipment_data():
    """Update equipment data and notify clients via SocketIO"""
    global equipment_data
    
    print(f"[{datetime.now()}] Starting equipment data update...")
    
    equipment_list = scrape_equipment()
    
    if equipment_list is not None:
        instruments, docking_stations = categorize_equipment(equipment_list)
        
        with data_lock:
            equipment_data = {
                'instruments': instruments,
                'docking_stations': docking_stations,
                'last_update': datetime.now().isoformat()
            }
        
        print(f"Updated: {len(instruments)} instruments, {len(docking_stations)} docking stations")
        
        # Emit update to all connected clients
        socketio.emit('equipment_update', {
            'instruments': instruments,
            'docking_stations': docking_stations,
            'last_update': equipment_data['last_update']
        }, namespace='/')
    else:
        print("Failed to update equipment data")


def schedule_updates():
    """Schedule periodic equipment updates"""
    config = load_config()
    frequency_minutes = config.get('update_frequency', 60)
    
    # Clear existing jobs
    scheduler.remove_all_jobs()
    
    # Add new job
    scheduler.add_job(
        func=update_equipment_data,
        trigger="interval",
        minutes=frequency_minutes,
        id='update_equipment',
        name='Update equipment data',
        replace_existing=True
    )
    
    print(f"Scheduled updates every {frequency_minutes} minutes")


# Routes

@app.route('/')
def index():
    """Main dashboard page"""
    with data_lock:
        data = equipment_data.copy()
    
    return render_template('index.html', 
                         instruments=data['instruments'],
                         docking_stations=data['docking_stations'],
                         last_update=data['last_update'])


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        config = load_config()
        
        if (username == config['admin_username'] and 
            check_password_hash(config['admin_password_hash'], password)):
            user = User('1')
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Logout"""
    logout_user()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))


@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    """Admin configuration page"""
    config = load_config()
    
    if request.method == 'POST':
        # Update admin password if provided
        new_admin_password = request.form.get('admin_password')
        if new_admin_password:
            config['admin_password_hash'] = generate_password_hash(new_admin_password)
        
        # Update INET credentials
        config['inet_username'] = request.form.get('inet_username', '')
        config['inet_password'] = request.form.get('inet_password', '')
        
        # Update frequency
        try:
            frequency = int(request.form.get('update_frequency', 60))
            if frequency < 1:
                frequency = 1
            config['update_frequency'] = frequency
        except ValueError:
            flash('Invalid update frequency', 'danger')
            return redirect(url_for('admin'))

        try:
            due_soon_days = int(request.form.get('calibration_due_soon_days', 170))
            overdue_days = int(request.form.get('calibration_overdue_days', 180))
            if due_soon_days < 1 or overdue_days < 1:
                raise ValueError
            if overdue_days < due_soon_days:
                flash('Overdue days must be greater than or equal to due soon days', 'danger')
                return redirect(url_for('admin'))
            config['calibration_due_soon_days'] = due_soon_days
            config['calibration_overdue_days'] = overdue_days
        except ValueError:
            flash('Invalid calibration alert settings', 'danger')
            return redirect(url_for('admin'))
        
        if save_config(config):
            flash('Configuration saved successfully!', 'success')
            
            # Reschedule updates with new frequency
            schedule_updates()

            recategorize_equipment_data()
            
            # Trigger immediate update if credentials changed
            if request.form.get('inet_username') or request.form.get('inet_password'):
                socketio.start_background_task(update_equipment_data)
        else:
            flash('Error saving configuration', 'danger')
        
        return redirect(url_for('admin'))
    
    # Don't send password to template, just indicate if it's set
    template_config = config.copy()
    template_config['inet_password'] = '********' if config.get('inet_password') else ''
    
    return render_template('admin.html', config=template_config)


@app.route('/api/refresh', methods=['POST'])
@login_required
def refresh_data():
    """Manually trigger data refresh"""
    socketio.start_background_task(update_equipment_data)
    return jsonify({'status': 'refresh_started'})


@app.route('/health')
def health_check():
    """Health check endpoint for Docker/monitoring"""
    with data_lock:
        has_data = len(equipment_data['instruments']) > 0 or len(equipment_data['docking_stations']) > 0
    
    return jsonify({
        'status': 'healthy',
        'scheduler_running': scheduler.running,
        'has_equipment_data': has_data,
        'last_update': equipment_data.get('last_update')
    }), 200


# SocketIO events

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    with data_lock:
        emit('equipment_update', {
            'instruments': equipment_data['instruments'],
            'docking_stations': equipment_data['docking_stations'],
            'last_update': equipment_data['last_update']
        })


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')


@socketio.on('request_update')
def handle_request_update():
    """Handle manual update request from client"""
    with data_lock:
        emit('equipment_update', {
            'instruments': equipment_data['instruments'],
            'docking_stations': equipment_data['docking_stations'],
            'last_update': equipment_data['last_update']
        })


if __name__ == '__main__':
    # Ensure config exists
    load_config()
    
    # Start scheduler
    if not scheduler.running:
        scheduler.start()
        schedule_updates()
        
        # Do initial update
        print("Performing initial equipment update...")
        update_equipment_data()
    
    # Get configuration from environment variables
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', '5000'))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    
    # Run the app
    print(f"Starting INET Dashboard on http://{host}:{port}")
    print("Admin login: admin/admin (change this in admin panel!)")
    
    try:
        socketio.run(app, debug=debug, host=host, port=port, allow_unsafe_werkzeug=True)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

