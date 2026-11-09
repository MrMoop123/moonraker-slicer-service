# Moonraker Slicing Service

A standalone Python microservice that exposes a Moonraker-compatible JSON-RPC API endpoint for slicing 3D model files (STL/OBJ/AMF) into G-code using a headless slicer CLI (PrusaSlicer), driven by user-uploaded slicer profiles.

## Architecture

```
Mainsail/Fluidd  --HTTP/JSON-RPC-->  moonraker-slicer-svc  --CLI-->  PrusaSlicer (headless)
                                                                                    |
                                                                             /home/pi/gcode_files/
```

**Platform:** Raspberry Pi OS / Debian on BTT Pi V1.2.1 (arm64/aarch64)
**Runtime:** Python 3.11+
**Default Port:** 7125
**Slicer:** PrusaSlicer (arm64)

## Quick Start

### 1. Install PrusaSlicer (arm64)

Two options depending on your Pi setup:

**Option A: Flatpak (recommended on Raspberry Pi OS with desktop)**
```bash
# Install Flatpak if not present
sudo apt install flatpak
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

# Install PrusaSlicer
flatpak install flathub com.prusa3d.PrusaSlicer -y

# Verify
flatpak run com.prusa3d.PrusaSlicer --version
```

**Option B: AppImage (headless/server, no GUI needed)**
```bash
# Download PrusaSlicer 2.6.0 (last version with arm64 AppImage)
chmod +x scripts/install-slicer.sh
./scripts/install-slicer.sh
```

### 2. Install the service

```bash
./scripts/install.sh
```

### 3. Upload a slicer profile

Export `printer_settings.ini` and `filament_settings.ini` from the slicer GUI, then:

```bash
curl -X POST http://localhost:7125/api/profiles/upload \
  -F "profile_name=default" \
  -F "files=@printer_settings.ini" \
  -F "files=@filament_settings.ini"
```

### 4. Slice a model

```bash
curl -X POST http://localhost:7125/api/slice \
  -H 'Content-Type: application/json' \
  -d '{
    "model_file": "cube.stl",
    "profile_name": "default"
  }'
```

### 5. Check job status

```bash
curl http://localhost:7125/api/jobs/slice_abc123
```

## Configuration

Edit `~/.config/moonraker-slicer/config.yaml`:

```yaml
host: "0.0.0.0"
port: 7125
slicer_binary: "/usr/local/bin/prusa-slicer"
slicer_name: "prusa-slicer"
profiles_dir: "~/.config/moonraker-slicer/profiles"
output_dir: "/home/pi/gcode_files"
max_concurrent_jobs: 2
max_model_size_mb: 500
job_retention_days: 30
log_level: "INFO"
```

CLI overrides:

```bash
moonraker-slicer --config /custom/path.yaml --port 8080 --log-level DEBUG
```

## API Reference

### Health Check
```
GET /api/health
```

### Profiles
```
GET    /api/profiles                      # List all profiles
GET    /api/profiles/<name>/metadata      # Get profile details
POST   /api/profiles/upload               # Upload profile files
DELETE /api/profiles/<name>               # Delete profile
GET    /api/profiles/<name>/validate      # Validate profile keys
```

### Slicing
```
POST /api/slice                            # Submit slice job
Body: {"model_file": "model.stl", "profile_name": "my_profile"}
```

### Jobs
```
GET /api/jobs                              # List recent jobs
GET /api/jobs/<job_id>                     # Get job status
GET /api/jobs/status                       # Job count summary
```

### Moonraker JSON-RPC (when plugin installed)
```json
{"method": "slicer.slice", "params": {"model_file": "model.stl", "profile_name": "my_profile"}}
{"method": "slicer.job_status", "params": {"job_id": "slice_abc123"}}
{"method": "slicer.list_profiles"}
{"method": "slicer.list_jobs"}
```

## Profiles

Slicer profiles are INI-style files exported from the slicer GUI. Store them at:
```
~/.config/moonraker-slicer/profiles/<profile_name>/
├── printer_settings.ini
├── filament_settings.ini
└── metadata.json    # auto-generated
```

Required keys in `printer_settings.ini`: `nozzle_diameter`, `vertical_limit`, `travel_speed`.

## Deployment

### systemd Service

```ini
# /etc/systemd/system/moonraker-slicer.service
[Unit]
Description=Moonraker Slicing Service
After=network-online.target moonraker.service
Wants=network-online.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=%h/src/moonraker-slicer-service
ExecStart=%h/.venvs/moonraker-slicer-service/bin/python -m moonraker_slicer
Restart=on-failure
RestartSec=5
Environment=HOME=%h
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

### Nginx Reverse Proxy (with auth)

```nginx
server {
    listen 80;
    server_name slicer.example.com;

    auth_basic "Slicer Access";
    auth_basic_user_file /etc/nginx/.slicer_passwd;

    location / {
        proxy_pass http://127.0.0.1:7125;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Manual smoke test:
```bash
curl -X POST http://localhost:7125/api/slice \
  -H 'Content-Type: application/json' \
  -d '{"model_file":"cube.stl","profile_name":"test_profile"}'

curl http://localhost:7125/api/jobs/<job_id>
```

## Security

- Bind to `127.0.0.1` for local-only access, or use Nginx reverse proxy with auth
- Path validation blocks directory traversal attempts
- File size limit: 500 MB (configurable)
- Job results auto-cleanup after 30 days
