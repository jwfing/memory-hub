#!/usr/bin/env python3
"""
Hook script to automatically save Claude Code conversations to memory-hub.
This script calls the HTTP endpoint which includes entity and relationship extraction.
"""

import sys
import json
import os
import requests
from datetime import datetime, timezone

# Configuration
MEMHUB_URL = os.getenv("MEMHUB_HTTP_URL", "http://localhost:8000")
MEMHUB_TOKEN = os.getenv("MEMHUB_AUTH_TOKEN", "")


def save_to_memhub(role: str, content: str, session_id: str = None):
    """Save a conversation message to memory-hub via HTTP API."""

    if not MEMHUB_TOKEN:
        print("Warning: MEMHUB_AUTH_TOKEN not set", file=sys.stderr)
        return False

    # Use current date as session_id if not provided
    if not session_id:
        session_id = f"claude_code_{datetime.now(timezone.utc).strftime('%Y%m%d')}"

    # Prepare the request
    url = f"{MEMHUB_URL}/api/save"
    headers = {
        "Authorization": f"Bearer {MEMHUB_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "platform": "claude_code",
        "metadata": json.dumps({
            "auto_saved": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            entities = result.get("entities_extracted", 0)
            relationships = result.get("relationships_extracted", 0)
            print(f"✓ Saved (entities: {entities}, relationships: {relationships})", file=sys.stderr)
            return True
        else:
            print(f"✗ HTTP {response.status_code}: {response.text}", file=sys.stderr)
            return False

    except Exception as e:
        print(f"✗ Error saving to memory-hub: {e}", file=sys.stderr)
        return False


def main():
    """Main function to handle hook input."""

    # Read input from stdin (hook data)
    try:
        input_data = sys.stdin.read()

        # Try to parse as JSON
        try:
            data = json.loads(input_data)
            role = data.get("role", "user")
            content = data.get("content", input_data)
            session_id = data.get("session_id")
        except json.JSONDecodeError:
            # If not JSON, treat as plain text user message
            role = "user"
            content = input_data
            session_id = None

        # Save to memory-hub
        if content and content.strip():
            save_to_memhub(role, content, session_id)

    except Exception as e:
        print(f"Error in hook: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
