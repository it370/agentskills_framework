# Production Deployment Guide

Complete guide for deploying AgentSkills Framework in production.

---

## 🚀 Quick Start

### Prerequisites

```bash
# Ensure production server is installed in your conda environment
conda activate clearstar
pip install gunicorn uvicorn[standard] hypercorn  # All platforms
```

### Start Production Server

**Windows:**
```bash
start-production.bat
```

**Linux/Mac:**
```bash
chmod +x start-production.sh
./start-production.sh
```

**Manual:**
```bash
# Windows
conda activate clearstar
python production_server.py

# Linux/Mac
conda activate clearstar
gunicorn --config gunicorn.conf.py api:api
```

### Health Check

```bash
# Test if server is running
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "checks": {"postgres": true, "mongodb": true, "broadcaster": true}}
```

### Current Status

**Platform Detection:**
- **Windows**: Uses Hypercorn (ASGI, 4 workers by default)
- **Linux/Mac**: Uses Gunicorn + Uvicorn workers (auto-calculated workers)

**Key Files:**
- `production_server.py` - Windows entry point (Hypercorn)
- `start-production.bat` - Windows startup script
- `start-production.sh` - Linux/Mac startup script
- `gunicorn.conf.py` - Gunicorn configuration (Linux/Mac)
- `agentskills.service` - Systemd service file (Linux)

---

## Table of Contents

1. [Configuration](#configuration)
2. [Platform-Specific Deployment](#platform-specific-deployment)
   - [Windows Deployment](#windows-deployment)
   - [Linux/Ubuntu Deployment](#linuxubuntu-deployment)
3. [Performance Tuning](#performance-tuning)
4. [Monitoring](#monitoring)
5. [Troubleshooting](#troubleshooting)

---

---

## Configuration

### Environment Variables

Production-specific settings in `.env`:

```bash
# Server Configuration
REST_API_HOST=0.0.0.0
REST_API_PORT=8000

# Workers (Platform-specific)
HYPERCORN_WORKERS=4  # Windows (Hypercorn)
GUNICORN_WORKERS=9  # Linux/Mac (Gunicorn) - Default: (CPU cores * 2) + 1
GUNICORN_TIMEOUT=120  # Request timeout in seconds
GUNICORN_MAX_REQUESTS=10000  # Restart workers after N requests
GUNICORN_LOG_LEVEL=info  # debug, info, warning, error, critical

# Logging
GUNICORN_ACCESS_LOG=-  # - for stdout, or path to file
GUNICORN_ERROR_LOG=-   # - for stderr, or path to file

# SSL/TLS (Optional)
SSL_KEYFILE=./cert/key.pem
SSL_CERTFILE=./cert/cert.pem

# Callback URL (Important for REST executor skills)
CALLBACK_BASE_URL=https://your-domain.com  # Or http://your-ip:8000
```

### Platform Differences

| Feature | Windows | Linux/Mac |
|---------|---------|-----------|
| **Server** | Hypercorn (ASGI) | Gunicorn + Uvicorn |
| **Workers** | `HYPERCORN_WORKERS` (default: 4) | `GUNICORN_WORKERS` (auto-calc) |
| **Entry Point** | `production_server.py` | `gunicorn` command |
| **Startup** | `start-production.bat` | `start-production.sh` |
| **System Service** | NSSM / Task Scheduler | Systemd |

### Worker Count Guidelines

**CPU-bound workloads:**
```bash
GUNICORN_WORKERS=$((CPU_CORES * 2 + 1))
```

**I/O-bound workloads (recommended for this application):**
```bash
GUNICORN_WORKERS=$((CPU_CORES * 4))
```

**Example calculations:**
- 2 CPU cores → 5 workers (CPU-bound) or 8 workers (I/O-bound)
- 4 CPU cores → 9 workers (CPU-bound) or 16 workers (I/O-bound)
- 8 CPU cores → 17 workers (CPU-bound) or 32 workers (I/O-bound)

---

## Platform-Specific Deployment

## Windows Deployment

### 1. Manual Start

```bash
# Open PowerShell/CMD in project directory
conda activate clearstar
start-production.bat
```

**Or manually:**
```bash
conda activate clearstar
python production_server.py
```

### 2. Windows Service with NSSM

Download NSSM: https://nssm.cc/download

```powershell
# Install as service
nssm install AgentSkills "C:\path\to\conda\envs\clearstar\python.exe"
nssm set AgentSkills AppParameters "production_server.py"
nssm set AgentSkills AppDirectory "C:\path\to\agentskills_framework"
nssm set AgentSkills DisplayName "AgentSkills Framework"
nssm set AgentSkills Description "AI Workflow Engine"
nssm set AgentSkills Start SERVICE_AUTO_START

# Start service
nssm start AgentSkills

# Check status
nssm status AgentSkills

# View logs
nssm set AgentSkills AppStdout "C:\path\to\logs\agentskills.log"
nssm set AgentSkills AppStderr "C:\path\to\logs\agentskills-error.log"
```

### 3. IIS Reverse Proxy (Optional)

Install URL Rewrite and Application Request Routing modules, then add to `web.config`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <system.webServer>
        <rewrite>
            <rules>
                <rule name="AgentSkills Proxy">
                    <match url="(.*)" />
                    <action type="Rewrite" url="http://localhost:8000/{R:1}" />
                </rule>
            </rules>
        </rewrite>
    </system.webServer>
</configuration>
```

---

## Linux/Ubuntu Deployment

### 1. Install as Systemd Service

```bash
# Copy service file
sudo cp agentskills.service /etc/systemd/system/

# Edit paths in service file if needed
sudo nano /etc/systemd/system/agentskills.service

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable agentskills

# Start service
sudo systemctl start agentskills

# Check status
sudo systemctl status agentskills
```

### 2. Service Management Commands

```bash
# Start
sudo systemctl start agentskills

# Stop
sudo systemctl stop agentskills

# Restart
sudo systemctl restart agentskills

# Reload (graceful restart)
sudo systemctl reload agentskills

# View logs
sudo journalctl -u agentskills -f

# View recent logs
sudo journalctl -u agentskills -n 100
```

### 3. Nginx Reverse Proxy (Recommended)

Install Nginx:
```bash
sudo apt update
sudo apt install nginx
```

Create Nginx configuration (`/etc/nginx/sites-available/agentskills`):

```nginx
upstream agentskills_backend {
    server 127.0.0.1:8000 fail_timeout=0;
}

server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL Configuration (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Request size limits
    client_max_body_size 100M;
    
    # Timeouts
    proxy_connect_timeout 120s;
    proxy_send_timeout 120s;
    proxy_read_timeout 120s;
    
    location / {
        proxy_pass http://agentskills_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (for future use)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable and test:
```bash
sudo ln -s /etc/nginx/sites-available/agentskills /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 4. SSL with Let's Encrypt

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Test auto-renewal
sudo certbot renew --dry-run
```


## Performance Tuning

### 1. Database Connection Pooling

In `.env`:
```bash
# PostgreSQL
POSTGRES_MIN_POOL_SIZE=5
POSTGRES_MAX_POOL_SIZE=20

# MongoDB
MONGO_MIN_POOL_SIZE=5
MONGO_MAX_POOL_SIZE=20
```

### 2. Worker Configuration

**For 4 CPU cores:**
```bash
GUNICORN_WORKERS=16  # I/O bound
GUNICORN_TIMEOUT=120
GUNICORN_MAX_REQUESTS=10000
```

**For 8 CPU cores:**
```bash
GUNICORN_WORKERS=32
GUNICORN_TIMEOUT=120
GUNICORN_MAX_REQUESTS=10000
```

### 3. Kernel Parameters (Linux)

Edit `/etc/sysctl.conf`:
```bash
# Increase file descriptor limits
fs.file-max = 65536

# Network tuning
net.core.somaxconn = 4096
net.ipv4.tcp_max_syn_backlog = 4096
```

Apply:
```bash
sudo sysctl -p
```

### 4. Resource Monitoring

```bash
# CPU and Memory usage
htop

# Gunicorn workers
ps aux | grep gunicorn

# Open connections
netstat -an | grep :8000 | wc -l

# System resource limits
ulimit -a
```

---

## Monitoring

### 1. Health Check Endpoint

```bash
# Test health endpoint
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "checks": {
    "postgres": true,
    "mongodb": true,
    "broadcaster": true
  }
}
```

### 2. Log Monitoring

**Linux (systemd):**
```bash
# Follow logs
sudo journalctl -u agentskills -f

# Filter by priority
sudo journalctl -u agentskills -p err

# Export logs
sudo journalctl -u agentskills --since "1 hour ago" > logs.txt
```

**Application logs:**
```bash
# If using file logging
tail -f /var/log/agentskills/access.log
tail -f /var/log/agentskills/error.log
```

### 3. Performance Metrics

Monitor these metrics:
- **Request latency** - Should be < 1s for most requests
- **Worker count** - All workers should be busy during load
- **Database connections** - Should not hit pool max
- **Memory usage** - Should be stable (no leaks)
- **Error rate** - Should be < 1%

---

## Troubleshooting

### Issue: Workers Timing Out

**Symptoms:** 502 errors, worker killed messages

**Solutions:**
```bash
# Increase timeout
GUNICORN_TIMEOUT=300

# Increase max requests
GUNICORN_MAX_REQUESTS=5000
```

### Issue: High Memory Usage

**Symptoms:** Workers consuming excessive RAM

**Solutions:**
```bash
# Reduce worker count
GUNICORN_WORKERS=4

# Restart workers more frequently
GUNICORN_MAX_REQUESTS=1000
```

### Issue: Connection Pool Exhausted

**Symptoms:** "Connection pool exhausted" errors

**Solutions:**
```bash
# Increase pool size
POSTGRES_MAX_POOL_SIZE=50
MONGO_MAX_POOL_SIZE=50

# Or reduce workers
GUNICORN_WORKERS=8
```

### Issue: SSL Certificate Errors

**Symptoms:** REST executor callbacks failing

**Solutions:**

1. **Use HTTP for development:**
   ```bash
   # Comment out in .env
   # SSL_KEYFILE=...
   # SSL_CERTFILE=...
   CALLBACK_BASE_URL=http://your-ip:8000
   ```

2. **Use proper SSL in production:**
   ```bash
   # Use Let's Encrypt
   sudo certbot --nginx -d your-domain.com
   
   # Update .env
   CALLBACK_BASE_URL=https://your-domain.com
   ```

### Issue: Port Already in Use

**Symptoms:** "Address already in use" error

**Solutions:**
```bash
# Find process using port 8000
sudo lsof -i :8000

# Kill process
sudo kill -9 <PID>

# Or change port in .env
REST_API_PORT=8001
```

### Graceful Restart

```bash
# Linux (systemd)
sudo systemctl reload agentskills

# Or send HUP signal
kill -HUP <gunicorn_master_pid>

# Windows
nssm restart AgentSkills
```

---

## Production Checklist

Before going live:

- [ ] Environment variables configured (`.env`)
- [ ] SSL certificates installed (if using HTTPS)
- [ ] Database connection pools configured
- [ ] Worker count optimized for your CPU
- [ ] Reverse proxy configured (Nginx/IIS)
- [ ] Firewall rules configured
- [ ] Health check endpoint responding
- [ ] Logging configured and tested
- [ ] Backup strategy in place
- [ ] Monitoring alerts configured
- [ ] Load testing completed
- [ ] Documentation updated

---

## Additional Resources

- **Gunicorn Documentation:** https://docs.gunicorn.org/
- **Uvicorn Documentation:** https://www.uvicorn.org/
- **FastAPI Deployment:** https://fastapi.tiangolo.com/deployment/
- **Let's Encrypt:** https://letsencrypt.org/

---

## Support

For issues or questions:
1. Check application logs
2. Review this documentation
3. Check the main README.md
4. Contact your system administrator
