#!/bin/bash
# Memory Hub MCP Server Setup Script

set -e

echo "🚀 Memory Hub MCP Server Setup"
echo "================================"

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv .venv
echo "✓ Virtual environment created"

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Create .env file
echo ""
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "✓ .env file created (默认配置即可使用)"
else
    echo "✓ .env file already exists"
fi

# Check if PostgreSQL is running
echo ""
echo "Checking PostgreSQL..."
if nc -z localhost 5632 2>/dev/null; then
    echo "✓ PostgreSQL is running on port 5632"
else
    echo "⚠️  PostgreSQL is not running on port 5632"
    echo "   Please start it with: docker-compose up -d"
fi

# Initialize database
echo ""
read -p "Do you want to initialize the database now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Initializing database..."
    python init_db.py
    echo "✓ Database initialized"
fi

echo ""
echo "================================"
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Ensure PostgreSQL is running: docker-compose up -d"
echo "2. Run tests: python test_server.py"
echo "3. Start server: python server.py"
echo ""
echo "Note: 首次运行会自动下载 embedding 模型（约 120MB）"
echo "      使用本地 sentence-transformers，无需 API Key！"
echo ""
echo "For more information, see README.md and USAGE.md"
