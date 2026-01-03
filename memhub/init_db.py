#!/usr/bin/env python
"""Initialize database script."""

from memhub.database import init_db

if __name__ == "__main__":
    print("Initializing Memory Hub database...")
    init_db()
    print("Done!")
