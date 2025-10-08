#!/bin/bash
set -e

# Wait for any initialization if needed
echo "Starting INET Dashboard..."

# Check if config.json exists, if not create a default one
if [ ! -f "/app/config.json" ]; then
    echo "Creating default config.json..."
    cat > /app/config.json <<EOF
{
  "admin_username": "admin",
  "admin_password_hash": "scrypt:32768:8:1\$vZ8J1xZQhK7jX9Uo\$8a7c1a5f0c3d2e4b6f8a9c1b2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e",
  "inet_username": "",
  "inet_password": "",
  "update_frequency": 60
}
EOF
fi

# Execute the main command
exec "$@"

