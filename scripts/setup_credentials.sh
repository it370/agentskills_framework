#!/bin/bash
# Quick Setup Script for Secure Credentials
# Run this to set up credentials quickly

echo "=========================================="
echo "Secure Credentials - Quick Setup"
echo "=========================================="
echo ""

# Step 1: Generate master key
echo "[Step 1/5] Generating master encryption key..."
MASTER_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
echo "✓ Generated: $MASTER_KEY"
echo ""

# Step 2: Add to .env
echo "[Step 2/5] Adding to .env file..."
if grep -q "CREDENTIAL_MASTER_KEY" .env 2>/dev/null; then
    echo "⚠️  CREDENTIAL_MASTER_KEY already exists in .env"
    echo "   Skipping to avoid overwriting..."
else
    echo "CREDENTIAL_MASTER_KEY=$MASTER_KEY" >> .env
    echo "✓ Added to .env"
fi
echo ""

# Step 3: Add to .gitignore
echo "[Step 3/5] Updating .gitignore..."
if ! grep -q ".credentials/" .gitignore 2>/dev/null; then
    echo ".credentials/" >> .gitignore
    echo "✓ Added .credentials/ to .gitignore"
else
    echo "✓ .credentials/ already in .gitignore"
fi
echo ""

# Step 4: Instructions
echo "[Step 4/5] Now add your database credentials..."
echo ""
echo "Run this command:"
echo "  python -m scripts.credential_manager add --user system --name production_db"
echo ""
read -p "Press Enter when you've added your credentials..."

# Step 5: Test
echo ""
echo "[Step 5/5] Testing setup..."
python -m scripts.credential_manager list --user system
echo ""

echo "=========================================="
echo "Setup Complete! ✅"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Reference credential in your skill:"
echo "   credential_ref: \"production_db\""
echo ""
echo "2. Start your application:"
echo "   python main.py"
echo ""
echo "See documentations/COMPLETE_SETUP_GUIDE.md for details"
