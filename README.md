# INET Equipment Dashboard

A real-time Flask dashboard for monitoring equipment calibration status from the INET system. Features live updates via WebSocket, dark theme UI, and admin configuration panel.

## Features

- **Real-time Updates**: Equipment data refreshes automatically using Flask-SocketIO
- **Dark Theme**: Modern Bootstrap 5.3 dark theme interface
- **Dual View Layout**:
  - Left sidebar: Docking Stations list
  - Main panel: Instruments table with calibration status
- **Calibration Alerts**:
  - 🔴 Red/Danger: Calibration overdue (past due date)
  - 🟡 Yellow/Warning: Calibration due within 10 days
  - 🟢 Green/OK: Calibration up to date
- **Admin Panel**: Configure INET credentials and update frequency
- **Secure Authentication**: Password-protected admin access
- **Background Scraping**: Automatic periodic data updates from INET

## Prerequisites

- Python 3.8+
- Access to INET system (inet.indsci.com)
- INET account credentials

## Installation

1. **Navigate to the project directory**:
   ```bash
   cd /Users/porcej/dev/inet/inet-dash
   ```

2. **Create and activate a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### Environment Variables

The application supports configuration via environment variables using a `.env` file:

1. **Create your `.env` file**:
   ```bash
   cp env.example .env
   ```

2. **Edit `.env` with your settings**:
   ```bash
   # Flask Secret Key (IMPORTANT: Change in production!)
   SECRET_KEY=your-secret-key-here
   
   # Flask Environment (development or production)
   FLASK_ENV=development
   
   # Server Host (0.0.0.0 for all interfaces, 127.0.0.1 for localhost only)
   FLASK_HOST=0.0.0.0
   
   # Server Port
   FLASK_PORT=5000
   ```

3. **Generate a secure secret key for production**:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

### Initial Setup

1. **Start the application**:
   ```bash
   python app.py
   ```

2. **Access the dashboard**:
   Open your browser to `http://localhost:5000`

3. **Login to admin panel**:
   - Navigate to `http://localhost:5000/login`
   - Default credentials: `admin` / `admin`
   - **⚠️ Important**: Change the default password immediately!

4. **Configure INET credentials**:
   - Go to Admin Panel (gear icon)
   - Enter your INET username and password
   - Set desired update frequency (in minutes)
   - Click "Save Configuration"

### Configuration File

Settings are stored in `config.json` (auto-created on first run):

```json
{
  "admin_username": "admin",
  "admin_password_hash": "<hashed_password>",
  "inet_username": "your_inet_username",
  "inet_password": "your_inet_password",
  "update_frequency": 60
}
```

## Docker Deployment

### Quick Start with Docker

The easiest way to run the INET Dashboard is using Docker:

```bash
# 1. Navigate to the directory
cd /Users/porcej/dev/inet/inet-dash

# 2. Build and start the container
docker-compose up -d

# 3. View logs
docker-compose logs -f

# 4. Stop the container
docker-compose down
```

### Docker Configuration

**Environment Variables** (in `.env` file or docker-compose.yml):
```bash
SECRET_KEY=your-secret-key-here
FLASK_ENV=production
FLASK_PORT=5000
```

**Persistent Data**:
The following files are mounted as volumes to persist data:
- `config.json` - Admin and INET credentials
- `inet_cookies.pkl` - Session cookies

### Docker Commands

**Build the image**:
```bash
docker build -t inet-dashboard .
```

**Run standalone container**:
```bash
docker run -d \
  --name inet-dashboard \
  -p 5000:5000 \
  -v $(pwd)/config.json:/app/config.json \
  -v $(pwd)/inet_cookies.pkl:/app/inet_cookies.pkl \
  -e SECRET_KEY="your-secret-key" \
  inet-dashboard
```

**Check health status**:
```bash
docker ps  # Look for "healthy" status
curl http://localhost:5000/health
```

**View logs**:
```bash
docker logs -f inet-dashboard
```

**Update and restart**:
```bash
docker-compose pull
docker-compose up -d
```

## Usage

### Dashboard View

- **Left Sidebar**: Lists all docking stations with model and serial numbers
- **Main Table**: Displays instruments with the following columns:
  - Equipment Number
  - Model
  - Serial Number
  - Location
  - Next Calibration Date
  - Days Remaining
  - Status (color-coded badge)

### Admin Panel

Access via the "Admin" button in the navigation bar (requires login).

**Available Settings**:
- **Admin Password**: Change the dashboard admin password
- **INET Username**: Your INET account username
- **INET Password**: Your INET account password
- **Update Frequency**: How often to scrape data (1-1440 minutes)

**Actions**:
- **Refresh Now**: Manually trigger an immediate data update
- **Test Connection**: Verify INET connection (coming soon)

### Real-time Updates

The dashboard automatically updates when new data is available:
- Connection status indicator shows WebSocket connection state
- Last update timestamp shows when data was last refreshed
- Tables update seamlessly without page refresh

## Architecture

### Directory Structure

```
inet-dash/
├── app.py                        # Main Flask application
├── inet_scraper_async_table.py  # INET scraper module
├── config.json                   # Configuration file (auto-generated)
├── requirements.txt              # Python dependencies
├── env.example                   # Environment variables template
├── .env                          # Environment variables (create from env.example)
├── Dockerfile                    # Docker image configuration
├── docker-compose.yml            # Docker Compose configuration
├── docker-entrypoint.sh          # Docker initialization script
├── .dockerignore                 # Docker build exclusions
├── Makefile                      # Docker shortcuts
├── DOCKER.md                     # Docker deployment guide
├── templates/
│   ├── index.html               # Main dashboard
│   ├── login.html               # Admin login page
│   └── admin.html               # Admin configuration panel
├── static/
│   ├── css/
│   │   └── style.css            # Dark theme custom styles
│   └── js/
│       └── dashboard.js         # WebSocket client & UI updates
└── README.md
```

### Technology Stack

- **Backend**: Flask, Flask-SocketIO, Flask-Login
- **Frontend**: Bootstrap 5.3 (dark theme), Socket.IO client
- **Scraping**: aiohttp, BeautifulSoup4 (built-in scraper module)
- **Scheduling**: APScheduler
- **Authentication**: Werkzeug password hashing
- **Containerization**: Docker, Docker Compose

### INET Scraper Module

The dashboard includes `inet_scraper_async_table.py` - an async web scraper that:
- Handles login to INET system
- Maintains session cookies
- Scrapes equipment data from tables
- Supports retry logic and error handling

The scraper is integrated directly into the dashboard application:

```python
from inet_scraper_async_table import WebScraperAsync, scrape_table
```

## Troubleshooting

### Connection Issues

**Problem**: "Disconnected" status in dashboard

**Solutions**:
- Ensure Flask app is running (`python app.py`)
- Check browser console for WebSocket errors
- Verify no firewall blocking port 5000

### Scraper Errors

**Problem**: No data appearing in dashboard

**Solutions**:
- Verify INET credentials in admin panel
- Check if INET website is accessible
- Review console logs for scraper errors
- Try "Refresh Now" button in admin panel

### Cookie Issues

**Problem**: Login failures to INET

**Solutions**:
- Delete `inet_cookies.pkl` in inet-scraper directory
- Verify credentials are correct
- Check INET account hasn't been locked

### Module Errors

**Problem**: `ImportError: No module named 'inet_scraper_async_table'`

**Solutions**:
- Ensure `inet_scraper_async_table.py` exists in the `inet-dash/` directory
- Verify the file was copied correctly from `inet-scraper/`
- Check file permissions: `chmod 644 inet_scraper_async_table.py`

## Security Considerations

⚠️ **Important Security Notes**:

1. **Change default admin password** immediately after first login
2. **Use environment variables** for sensitive data in production:
   - Create a `.env` file (copy from `env.example`)
   - Set a secure `SECRET_KEY` using: `python -c "import secrets; print(secrets.token_hex(32))"`
   - Never commit `.env` to version control (already in .gitignore)
3. **Enable HTTPS** in production environments
4. **Restrict network access** to trusted IPs if possible:
   - Use `FLASK_HOST=127.0.0.1` to only allow localhost connections
   - Use `FLASK_HOST=0.0.0.0` to allow all network interfaces
5. **Keep config.json secure** - contains INET credentials
6. **Never commit config.json** to version control (add to .gitignore)

## Development

### Running in Development Mode

```bash
python app.py
```

The app runs with Flask's debug mode enabled by default.

### Running in Production

For production deployment, use a production WSGI server:

```bash
pip install gunicorn eventlet
```

**Option 1: Using `.env` file** (recommended):

```bash
# Create and configure .env file
cp env.example .env
# Edit .env with production values

# Run with gunicorn
gunicorn --worker-class eventlet -w 1 app:app
```

**Option 2: Using environment variables directly**:

```bash
export SECRET_KEY="your-production-secret-key"
export FLASK_ENV="production"
export FLASK_HOST="0.0.0.0"
export FLASK_PORT="5000"

gunicorn --worker-class eventlet -w 1 --bind ${FLASK_HOST}:${FLASK_PORT} app:app
```

**Option 3: Using systemd service** (recommended for Linux servers):

Create `/etc/systemd/system/inet-dashboard.service`:

```ini
[Unit]
Description=INET Equipment Dashboard
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/inet-dash
Environment="PATH=/path/to/inet-dash/venv/bin"
EnvironmentFile=/path/to/inet-dash/.env
ExecStart=/path/to/inet-dash/venv/bin/gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable inet-dashboard
sudo systemctl start inet-dashboard
```

## API Endpoints

### Public Routes
- `GET /` - Main dashboard
- `GET /login` - Admin login page
- `POST /login` - Login submission

### Protected Routes (require authentication)
- `GET /admin` - Admin configuration panel
- `POST /admin` - Save configuration
- `GET /logout` - Logout
- `POST /api/refresh` - Trigger manual data refresh

### WebSocket Events
- `connect` - Client connected
- `disconnect` - Client disconnected
- `equipment_update` - Server pushes new equipment data
- `request_update` - Client requests current data

## Customization

### Update Frequency

Default: 60 minutes. Adjustable via admin panel (1-1440 minutes).

### Calibration Thresholds

To modify warning thresholds, edit `app.py`:

```python
# Current logic (line ~159):
if days_diff < 0:  # Past due
    item['_calibration_status'] = 'danger'
elif days_diff <= 10:  # Within 10 days
    item['_calibration_status'] = 'warning'
```

### Theme Colors

Edit `/static/css/style.css` to customize colors:

```css
:root {
    --bs-body-bg: #121212;
    --bs-body-color: #e0e0e0;
    --bs-dark: #1e1e1e;
    --bs-secondary: #2d2d2d;
}
```

## License

See LICENSE file for details.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review console logs for error messages
3. Verify INET credentials and connectivity
4. Check that inet-scraper is properly configured

## Version History

- **v1.0.0** (2025-10-07)
  - Initial release
  - Real-time dashboard with WebSocket updates
  - Dark theme UI
  - Admin configuration panel
  - Automatic background scraping
  - Calibration status alerts
