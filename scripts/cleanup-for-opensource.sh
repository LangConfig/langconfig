#!/bin/bash

# Script to clean up repo before making it public
# Run this from the project root

echo "🧹 Cleaning up repository for opensource release..."

# Remove accidentally tracked personal files
echo ""
echo "Removing personal AI assistant files from git tracking..."
git rm -r --cached .agent .ai-plans .claude 2>/dev/null || echo "  (Already removed or not tracked)"

# Remove temp build files
echo ""
echo "Removing temporary build files..."
git rm --cached build_errors*.txt tsc_output*.txt 2>/dev/null || echo "  (Already removed or not tracked)"

# Check for secrets
echo ""
echo "🔐 Checking for secrets..."
if git ls-files | grep -E "^\\.env$"; then
    echo "  ❌ ERROR: .env file is tracked! Remove it:"
    echo "     git rm --cached .env"
    exit 1
else
    echo "  ✅ .env is not tracked"
fi

# Check for certificates
echo ""
echo "🔑 Checking for certificates..."
if git ls-files | grep -E "\\.(p12|pfx|key|pem|crt)$"; then
    echo "  ❌ ERROR: Certificate files are tracked! This is a security risk!"
    echo "     Review and remove with: git rm --cached <filename>"
    exit 1
else
    echo "  ✅ No certificates tracked"
fi

# Verify .env.example exists
echo ""
echo "📄 Checking .env.example..."
if [ ! -f .env.example ]; then
    echo "  ⚠️  WARNING: .env.example does not exist!"
    echo "     Create it from .env with placeholder values"
else
    echo "  ✅ .env.example exists"
fi

# Show current status
echo ""
echo "📊 Current git status:"
git status --short

echo ""
echo "✅ Cleanup complete! Next steps:"
echo ""
echo "1. Review the git status above"
echo "2. Commit the .gitignore changes:"
echo "   git add .gitignore"
echo "   git commit -m 'Update .gitignore for opensource release'"
echo ""
echo "3. Verify nothing sensitive is tracked:"
echo "   git log --all --full-history -- .env"
echo "   (should be empty)"
echo ""
echo "4. If .env was ever committed, you MUST rotate all secrets!"
echo ""
