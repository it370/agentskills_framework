<#
.SYNOPSIS
    Export IIS certificate and convert to PEM format for Python backend servers
    
.DESCRIPTION
    This script:
    1. Lists available IIS certificates
    2. Exports selected certificate to PFX
    3. Converts to PEM format (key.pem and cert.pem)
    4. Displays configuration to add manually
    
.PARAMETER CertThumbprint
    The thumbprint of the certificate to export (optional, will prompt if not provided)
    
.PARAMETER OutputDir
    Directory to save certificate files (default: .\cert)
    
.PARAMETER ExportPassword
    Password for PFX export (will prompt if not provided)
    
.EXAMPLE
    .\setup-ssl.ps1
    .\setup-ssl.ps1 -CertThumbprint "ABC123..." -OutputDir "C:\certs"
#>

param(
    [string]$CertThumbprint,
    [string]$OutputDir = ".\cert",
    [string]$ExportPassword
)

# Requires Administrator privileges
#Requires -RunAsAdministrator

Write-Host "=== IIS Certificate to PEM Converter ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if OpenSSL is available
Write-Host "[1/6] Checking for OpenSSL..." -ForegroundColor Yellow
$opensslPath = Get-Command openssl -ErrorAction SilentlyContinue

if (-not $opensslPath) {
    Write-Host "ERROR: OpenSSL not found in PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install OpenSSL:" -ForegroundColor Yellow
    Write-Host "  Option 1: choco install openssl -y" -ForegroundColor Gray
    Write-Host "  Option 2: Download from https://slproweb.com/products/Win32OpenSSL.html" -ForegroundColor Gray
    exit 1
}
Write-Host "OK - OpenSSL found: $($opensslPath.Source)" -ForegroundColor Green
Write-Host ""

# Step 2: List available certificates
Write-Host "[2/6] Available IIS Certificates:" -ForegroundColor Yellow
$certs = Get-ChildItem -Path Cert:\LocalMachine\My | Where-Object {
    $_.HasPrivateKey -eq $true
}

if ($certs.Count -eq 0) {
    Write-Host "ERROR: No certificates with private keys found" -ForegroundColor Red
    exit 1
}

$i = 1
foreach ($cert in $certs) {
    Write-Host "  [$i] Subject: $($cert.Subject)" -ForegroundColor White
    Write-Host "      Thumbprint: $($cert.Thumbprint)" -ForegroundColor Gray
    Write-Host "      Expires: $($cert.NotAfter)" -ForegroundColor Gray
    Write-Host ""
    $i++
}

# Step 3: Select certificate
if (-not $CertThumbprint) {
    $selection = Read-Host "Select certificate number [1-$($certs.Count)]"
    $selectedCert = $certs[$selection - 1]
} else {
    $selectedCert = $certs | Where-Object { $_.Thumbprint -eq $CertThumbprint }
    if (-not $selectedCert) {
        Write-Host "ERROR: Certificate with thumbprint '$CertThumbprint' not found" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Selected: $($selectedCert.Subject)" -ForegroundColor Green
Write-Host ""

# Step 4: Create output directory
Write-Host "[3/6] Creating output directory..." -ForegroundColor Yellow
$OutputDir = $OutputDir.TrimEnd('\')
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}
$OutputDir = (Resolve-Path $OutputDir).Path
Write-Host "OK - Output directory: $OutputDir" -ForegroundColor Green
Write-Host ""

# Step 5: Export to PFX
Write-Host "[4/6] Exporting certificate to PFX..." -ForegroundColor Yellow
$pfxPath = Join-Path $OutputDir "temp-cert.pfx"

if (-not $ExportPassword) {
    $securePassword = Read-Host "Enter export password" -AsSecureString
} else {
    $securePassword = ConvertTo-SecureString -String $ExportPassword -Force -AsPlainText
}

try {
    Export-PfxCertificate -Cert $selectedCert -FilePath $pfxPath -Password $securePassword -Force | Out-Null
    Write-Host "OK - Exported to: $pfxPath" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to export certificate: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 6: Convert to PEM format
Write-Host "[5/6] Converting to PEM format..." -ForegroundColor Yellow

$keyPath = Join-Path $OutputDir "key.pem"
$certPath = Join-Path $OutputDir "cert.pem"

# Convert password to plain text for OpenSSL
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
$plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# Extract private key
Write-Host "  Extracting private key..." -ForegroundColor Gray
$keyArgs = "pkcs12 -in `"$pfxPath`" -nocerts -out `"$keyPath`" -nodes -password pass:$plainPassword"
$process = Start-Process -FilePath "openssl" -ArgumentList $keyArgs -Wait -NoNewWindow -PassThru
if ($process.ExitCode -ne 0) {
    Write-Host "ERROR: Failed to extract private key" -ForegroundColor Red
    Remove-Item $pfxPath -Force
    exit 1
}

# Extract certificate
Write-Host "  Extracting certificate..." -ForegroundColor Gray
$certArgs = "pkcs12 -in `"$pfxPath`" -clcerts -nokeys -out `"$certPath`" -password pass:$plainPassword"
$process = Start-Process -FilePath "openssl" -ArgumentList $certArgs -Wait -NoNewWindow -PassThru
if ($process.ExitCode -ne 0) {
    Write-Host "ERROR: Failed to extract certificate" -ForegroundColor Red
    Remove-Item $pfxPath -Force
    exit 1
}

# Clean up temporary PFX file
Remove-Item $pfxPath -Force

Write-Host "OK - Private key: $keyPath" -ForegroundColor Green
Write-Host "OK - Certificate: $certPath" -ForegroundColor Green
Write-Host ""

# Step 7: Verify certificates
Write-Host "[6/6] Verifying certificates..." -ForegroundColor Yellow

Write-Host "  Checking certificate..." -ForegroundColor Gray
$verifyCert = Start-Process -FilePath "openssl" -ArgumentList "x509 -in `"$certPath`" -text -noout" -Wait -NoNewWindow -PassThru
if ($verifyCert.ExitCode -ne 0) {
    Write-Host "WARNING: Certificate verification failed" -ForegroundColor Yellow
}

Write-Host "  Checking private key..." -ForegroundColor Gray
$verifyKey = Start-Process -FilePath "openssl" -ArgumentList "rsa -in `"$keyPath`" -check -noout" -Wait -NoNewWindow -PassThru
if ($verifyKey.ExitCode -ne 0) {
    Write-Host "WARNING: Private key verification failed" -ForegroundColor Yellow
}

Write-Host "OK - Certificates verified" -ForegroundColor Green
Write-Host ""

# Summary
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "                    SETUP COMPLETE" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Certificate files created:" -ForegroundColor White
Write-Host "  Key:  $keyPath" -ForegroundColor Gray
Write-Host "  Cert: $certPath" -ForegroundColor Gray
Write-Host ""

# Convert to relative paths for .env display
$relativeKeyPath = Resolve-Path -Relative $keyPath
$relativeCertPath = Resolve-Path -Relative $certPath

Write-Host "----------------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "MANUAL CONFIGURATION REQUIRED" -ForegroundColor Yellow
Write-Host "----------------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Add to your .env file:" -ForegroundColor Yellow
Write-Host ""
Write-Host "   SSL_KEYFILE=$relativeKeyPath" -ForegroundColor White
Write-Host "   SSL_CERTFILE=$relativeCertPath" -ForegroundColor White
Write-Host ""
Write-Host "2. Add to admin-ui/.env.local:" -ForegroundColor Yellow
Write-Host ""
Write-Host "   NEXT_PUBLIC_API_BASE=https://localhost:8000" -ForegroundColor White
Write-Host "   NEXT_PUBLIC_SOCKETIO_BASE=https://localhost:7000" -ForegroundColor White
Write-Host ""
Write-Host "3. Start servers:" -ForegroundColor Yellow
Write-Host ""
Write-Host "   python main.py" -ForegroundColor White
Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Done!" -ForegroundColor Green
