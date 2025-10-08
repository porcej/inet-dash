# Docker Deployment Guide

This guide covers deploying the INET Equipment Dashboard using Docker.

## Quick Start

```bash
# Start the dashboard
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the dashboard
docker-compose down
```

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+

## Configuration

### Environment Variables

Create a `.env` file in the `inet-dash` directory:

```bash
SECRET_KEY=your-secure-random-key-here
FLASK_ENV=production
FLASK_PORT=5000
```

Generate a secure secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### First Time Setup

1. **Start the container**:
   ```bash
   docker-compose up -d
   ```

2. **Access the dashboard**:
   Open `http://localhost:5000` in your browser

3. **Login to admin panel**:
   - Navigate to `http://localhost:5000/login`
   - Default credentials: `admin` / `admin`
   - **IMPORTANT**: Change the password immediately!

4. **Configure INET credentials**:
   - Click "Admin" button
   - Enter your INET username and password
   - Set update frequency
   - Click "Save Configuration"

## Health Monitoring

### Health Check Endpoint

The dashboard includes a `/health` endpoint for monitoring:

```bash
curl http://localhost:5000/health
```

Response:
```json
{
  "status": "healthy",
  "scheduler_running": true,
  "has_equipment_data": true,
  "last_update": "2025-10-08T10:30:00"
}
```

### Docker Health Status

Check container health:
```bash
docker ps
```

Look for `healthy` status in the `STATUS` column.

## Data Persistence

The following files are persisted using Docker volumes:

- `config.json` - Stores admin credentials and INET settings
- `inet_cookies.pkl` - Stores session cookies for INET

These files are automatically created if they don't exist.

## Common Operations

### View Logs

```bash
# Follow logs
docker-compose logs -f

# View last 100 lines
docker-compose logs --tail=100

# View logs for specific service
docker-compose logs inet-dashboard
```

### Restart the Container

```bash
docker-compose restart
```

### Update the Application

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose up -d --build
```

### Access Container Shell

```bash
docker-compose exec inet-dashboard /bin/bash
```

### Stop and Remove

```bash
# Stop containers
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Using Make Commands

If you have `make` installed, use these shortcuts:

```bash
make build    # Build the Docker image
make up       # Start the containers
make down     # Stop the containers
make restart  # Restart the containers
make logs     # View logs
make shell    # Open shell in container
make health   # Check health status
make clean    # Remove everything
```

## Production Deployment

### Security Best Practices

1. **Use a strong SECRET_KEY**:
   ```bash
   SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
   ```

2. **Change default admin password** immediately after first login

3. **Use environment variables** for secrets (not in docker-compose.yml)

4. **Enable HTTPS** with a reverse proxy (nginx, traefik, etc.)

5. **Restrict network access** to trusted IPs

### Reverse Proxy Example (nginx)

```nginx
server {
    listen 443 ssl;
    server_name dashboard.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Using with systemd

Create `/etc/systemd/system/inet-dashboard.service`:

```ini
[Unit]
Description=INET Equipment Dashboard
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/inet-dash
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable inet-dashboard
sudo systemctl start inet-dashboard
```

## Troubleshooting

### Container won't start

Check logs:
```bash
docker-compose logs
```

### Health check failing

1. Check if the app is running:
   ```bash
   docker-compose ps
   ```

2. Check health endpoint manually:
   ```bash
   curl http://localhost:5000/health
   ```

3. Inspect container:
   ```bash
   docker-compose exec inet-dashboard /bin/bash
   python -c "import requests; print(requests.get('http://localhost:5000/health').json())"
   ```

### Permission issues

Ensure config files have proper permissions:
```bash
chmod 644 config.json
chmod 644 inet_cookies.pkl
```

### Port already in use

Change the port in docker-compose.yml or .env:
```yaml
ports:
  - "8080:5000"  # Use port 8080 instead
```

## Monitoring

### Log Aggregation

Use Docker's logging drivers:

```yaml
services:
  inet-dashboard:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### External Monitoring

Health check URL for monitoring tools:
```
http://your-server:5000/health
```

Expected response: HTTP 200 with JSON payload

## Backup

Backup important files:

```bash
# Backup configuration
cp config.json config.json.backup

# Backup cookies
cp inet_cookies.pkl inet_cookies.pkl.backup

# Or backup everything
tar -czf inet-dashboard-backup.tar.gz config.json inet_cookies.pkl
```

## Support

For issues or questions:
1. Check logs: `docker-compose logs`
2. Verify health: `curl http://localhost:5000/health`
3. Review main README.md
4. Check container status: `docker ps`

