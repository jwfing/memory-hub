#!/bin/bash
# Generate Claude Desktop configuration for Memory Hub MCP Server

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Memory Hub - Claude Desktop Config Generator${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH="$SCRIPT_DIR/.venv/bin/python"
SERVER_PATH="$SCRIPT_DIR/server.py"

# Check if venv exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo -e "${YELLOW}Warning: Virtual environment not found at $PYTHON_PATH${NC}"
    echo -e "${YELLOW}Using system Python instead${NC}"
    PYTHON_PATH=$(which python3)
fi

# Load .env file
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
else
    echo -e "${YELLOW}Warning: .env file not found, using defaults${NC}"
    POSTGRES_HOST="localhost"
    POSTGRES_PORT="5632"
    POSTGRES_DB="memhub"
    POSTGRES_USER="postgres"
    POSTGRES_PASSWORD="itsnothing"
    JWT_SECRET="change-this-secret-key-in-production"
    EMBEDDING_MODEL="paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIMENSIONS="768"
fi

# Generate config
cat > claude_desktop_config.json <<EOF
{
  "mcpServers": {
    "memory-hub": {
      "command": "$PYTHON_PATH",
      "args": [
        "$SERVER_PATH"
      ],
      "env": {
        "POSTGRES_HOST": "$POSTGRES_HOST",
        "POSTGRES_PORT": "$POSTGRES_PORT",
        "POSTGRES_DB": "$POSTGRES_DB",
        "POSTGRES_USER": "$POSTGRES_USER",
        "POSTGRES_PASSWORD": "$POSTGRES_PASSWORD",
        "JWT_SECRET": "$JWT_SECRET",
        "EMBEDDING_MODEL": "$EMBEDDING_MODEL",
        "EMBEDDING_DIMENSIONS": "$EMBEDDING_DIMENSIONS"
      }
    }
  }
}
EOF

echo -e "${GREEN}✓ Configuration generated successfully!${NC}"
echo ""
echo -e "${YELLOW}Configuration details:${NC}"
echo -e "  Python: ${BLUE}$PYTHON_PATH${NC}"
echo -e "  Server: ${BLUE}$SERVER_PATH${NC}"
echo -e "  Database: ${BLUE}$POSTGRES_USER@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB${NC}"
echo ""
echo -e "${YELLOW}Generated file: ${BLUE}claude_desktop_config.json${NC}"
echo ""

# Determine OS and config location
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/Claude"
    CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CONFIG_DIR="$HOME/.config/Claude"
    CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    CONFIG_DIR="$APPDATA/Claude"
    CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
else
    echo -e "${YELLOW}Unknown OS. Please manually copy the config.${NC}"
    exit 0
fi

echo -e "${YELLOW}Claude Desktop config location:${NC}"
echo -e "  ${BLUE}$CONFIG_FILE${NC}"
echo ""

# Ask if user wants to install
read -p "Do you want to install this config to Claude Desktop? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Create directory if it doesn't exist
    mkdir -p "$CONFIG_DIR"

    # Backup existing config
    if [ -f "$CONFIG_FILE" ]; then
        BACKUP_FILE="$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
        echo -e "${YELLOW}Backing up existing config to:${NC}"
        echo -e "  ${BLUE}$BACKUP_FILE${NC}"
        cp "$CONFIG_FILE" "$BACKUP_FILE"

        # Merge with existing config
        echo -e "${YELLOW}Merging with existing configuration...${NC}"

        # Use Python to merge JSON (if Python is available)
        if command -v python3 &> /dev/null; then
            python3 - <<PYTHON_SCRIPT
import json
import sys

# Read existing config
with open('$CONFIG_FILE', 'r') as f:
    existing = json.load(f)

# Read new config
with open('claude_desktop_config.json', 'r') as f:
    new = json.load(f)

# Merge mcpServers
if 'mcpServers' not in existing:
    existing['mcpServers'] = {}

existing['mcpServers'].update(new['mcpServers'])

# Write merged config
with open('$CONFIG_FILE', 'w') as f:
    json.dump(existing, f, indent=2)

print("✓ Configuration merged successfully!")
PYTHON_SCRIPT
        else
            # Simple overwrite if Python not available
            cp claude_desktop_config.json "$CONFIG_FILE"
        fi
    else
        # No existing config, just copy
        cp claude_desktop_config.json "$CONFIG_FILE"
    fi

    echo ""
    echo -e "${GREEN}✓ Configuration installed!${NC}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo -e "  1. Make sure PostgreSQL is running:"
    echo -e "     ${BLUE}docker-compose up -d postgres${NC}"
    echo ""
    echo -e "  2. Completely quit and restart Claude Desktop"
    echo ""
    echo -e "  3. You should see Memory Hub tools available in Claude Desktop"
    echo ""
else
    echo ""
    echo -e "${YELLOW}Configuration not installed.${NC}"
    echo -e "You can manually copy ${BLUE}claude_desktop_config.json${NC} to:"
    echo -e "  ${BLUE}$CONFIG_FILE${NC}"
    echo ""
fi

echo -e "${GREEN}Done!${NC}"