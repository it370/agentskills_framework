# Quick Setup Script for Secure Credentials (PowerShell)
# Run this to set up credentials quickly

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Secure Credentials - Quick Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Generate master key
Write-Host "[Step 1/5] Generating master encryption key..." -ForegroundColor Yellow
$masterKey = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
Write-Host "✓ Generated: $masterKey" -ForegroundColor Green
Write-Host ""

# Step 2: Add to .env
Write-Host "[Step 2/5] Adding to .env file..." -ForegroundColor Yellow
if (Test-Path .env) {
    $envContent = Get-Content .env -Raw
    if ($envContent -match "CREDENTIAL_MASTER_KEY") {
        Write-Host "⚠️  CREDENTIAL_MASTER_KEY already exists in .env" -ForegroundColor Yellow
        Write-Host "   Skipping to avoid overwriting..." -ForegroundColor Yellow
    } else {
        Add-Content .env "`nCREDENTIAL_MASTER_KEY=$masterKey"
        Write-Host "✓ Added to .env" -ForegroundColor Green
    }
} else {
    "CREDENTIAL_MASTER_KEY=$masterKey" | Out-File .env -Encoding UTF8
    Write-Host "✓ Created .env with master key" -ForegroundColor Green
}
Write-Host ""

# Step 3: Add to .gitignore
Write-Host "[Step 3/5] Updating .gitignore..." -ForegroundColor Yellow
if (Test-Path .gitignore) {
    $gitignoreContent = Get-Content .gitignore -Raw
    if ($gitignoreContent -notmatch ".credentials/") {
        Add-Content .gitignore "`n.credentials/"
        Write-Host "✓ Added .credentials/ to .gitignore" -ForegroundColor Green
    } else {
        Write-Host "✓ .credentials/ already in .gitignore" -ForegroundColor Green
    }
} else {
    ".credentials/" | Out-File .gitignore -Encoding UTF8
    Write-Host "✓ Created .gitignore with .credentials/" -ForegroundColor Green
}
Write-Host ""

# Step 4: Instructions
Write-Host "[Step 4/5] Now add your database credentials..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Run this command:" -ForegroundColor Cyan
Write-Host "  python -m scripts.credential_manager add --user system --name production_db" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter when you've added your credentials"

# Step 5: Test
Write-Host ""
Write-Host "[Step 5/5] Testing setup..." -ForegroundColor Yellow
python -m scripts.credential_manager list --user system
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Setup Complete! ✅" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Reference credential in your skill:" -ForegroundColor White
Write-Host "   credential_ref: `"production_db`"" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Start your application:" -ForegroundColor White
Write-Host "   python main.py" -ForegroundColor Gray
Write-Host ""
Write-Host "See documentations/COMPLETE_SETUP_GUIDE.md for details" -ForegroundColor Cyan
