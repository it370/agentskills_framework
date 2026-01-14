# HTTPS Configuration Guide

## Quick Setup for Development

### Generate Self-Signed SSL Certificates

**Windows (PowerShell):**
```powershell
# Generate certificate
$cert = New-SelfSignedCertificate -DnsName localhost -CertStoreLocation Cert:\LocalMachine\My

# Export to PEM format (requires manual conversion)
# Or use OpenSSL for Windows: https://slproweb.com/products/Win32OpenSSL.html
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365 -subj "/CN=localhost"
```

**Linux/Mac:**
```bash
openssl req -x509 -newkey rsa:4096 -nodes \
  -out cert.pem -keyout key.pem -days 365 \
  -subj "/CN=localhost"
```

### Configure Environment Variables

Add to your `.env` file:

```bash
# SSL Configuration
SSL_KEYFILE=./cert/key.pem
SSL_CERTFILE=./cert/cert.pem

# Server Configuration  
REST_API_HOST=0.0.0.0
REST_API_PORT=8000
SOCKETIO_HOST=0.0.0.0
SOCKETIO_PORT=7000
```

### Update Frontend Configuration

Update `admin-ui/.env.local`:

```bash
NEXT_PUBLIC_API_BASE=https://localhost:8000
NEXT_PUBLIC_SOCKETIO_BASE=https://localhost:7000
```

### Start Servers

```bash
python main.py
```

Both servers will now run with HTTPS on:
- REST API: https://localhost:8000
- Socket.IO: https://localhost:7000

## Production Setup

For production, use certificates from a trusted CA (Let's Encrypt, etc.):

1. **Get certificates:**
   ```bash
   # Using certbot for Let's Encrypt
   sudo certbot certonly --standalone -d yourdomain.com
   ```

2. **Configure `.env`:**
   ```bash
   SSL_KEYFILE=/etc/letsencrypt/live/yourdomain.com/privkey.pem
   SSL_CERTFILE=/etc/letsencrypt/live/yourdomain.com/fullchain.pem
   ```

3. **Update frontend:**
   ```bash
   NEXT_PUBLIC_API_BASE=https://yourdomain.com:8000
   NEXT_PUBLIC_SOCKETIO_BASE=https://yourdomain.com:7000
   ```

## IIS Reverse Proxy Setup

If you're using IIS as a reverse proxy (recommended for Windows production):

1. **Install URL Rewrite and ARR modules**
2. **Configure reverse proxy rules in `web.config`:**

```xml
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <rule name="Reverse Proxy to API" stopProcessing="true">
          <match url="^api/(.*)" />
          <action type="Rewrite" url="https://localhost:8000/{R:1}" />
        </rule>
        <rule name="Reverse Proxy to Socket.IO" stopProcessing="true">
          <match url="^socket.io/(.*)" />
          <action type="Rewrite" url="https://localhost:7000/socket.io/{R:1}" />
        </rule>
      </rules>
    </rewrite>
  </system.webServer>
</configuration>
```

3. **Update frontend to use proxy paths:**
   ```bash
   NEXT_PUBLIC_API_BASE=https://yourdomain.com/api
   NEXT_PUBLIC_SOCKETIO_BASE=https://yourdomain.com
   ```

## Troubleshooting

### Self-Signed Certificate Warnings

Browsers will show security warnings for self-signed certificates. You can:

1. **Accept the risk** (development only)
2. **Add certificate to trusted store**:
   - Windows: Import cert.pem to Trusted Root Certification Authorities
   - Mac: Add to Keychain and mark as trusted
   - Linux: Copy to `/usr/local/share/ca-certificates/` and run `sudo update-ca-certificates`

### WebSocket Connection Issues

If WebSocket connections fail over HTTPS:

1. Ensure Socket.IO client uses `wss://` (handled automatically)
2. Check firewall rules allow ports 7000 and 8000
3. Verify SSL certificates are valid for the domain

### Mixed Content Errors

If your frontend (HTTPS) can't connect to backend (HTTP):

- Modern browsers block mixed content (HTTPS→HTTP)
- **Solution**: Enable HTTPS on both frontend AND backend
