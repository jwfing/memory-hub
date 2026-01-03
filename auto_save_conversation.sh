#!/bin/bash
# Quick script to save current conversation context to memory-hub

# This script can be run manually or scheduled
# Usage: ./auto_save_conversation.sh "user message" "assistant response"

USER_MESSAGE="$1"
ASSISTANT_MESSAGE="$2"
SESSION_ID="${3:-claude_code_$(date +%Y%m%d)}"

MEMHUB_URL="${MEMHUB_HTTP_URL:-http://localhost:8000}"
TOKEN="${MEMHUB_AUTH_TOKEN}"

if [ -z "$TOKEN" ]; then
    echo "Error: MEMHUB_AUTH_TOKEN not set"
    exit 1
fi

# Save user message
if [ -n "$USER_MESSAGE" ]; then
    echo "Saving user message..."
    curl -X POST "$MEMHUB_URL/messages" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d @- << EOF
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "save_conversation",
        "arguments": {
            "session_id": "$SESSION_ID",
            "role": "user",
            "content": "$USER_MESSAGE",
            "platform": "claude_code"
        }
    }
}
EOF
    echo ""
fi

# Save assistant message
if [ -n "$ASSISTANT_MESSAGE" ]; then
    echo "Saving assistant message..."
    curl -X POST "$MEMHUB_URL/messages" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d @- << EOF
{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "save_conversation",
        "arguments": {
            "session_id": "$SESSION_ID",
            "role": "assistant",
            "content": "$ASSISTANT_MESSAGE",
            "platform": "claude_code"
        }
    }
}
EOF
    echo ""
fi

echo "✓ Conversation saved to memory-hub"