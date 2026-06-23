"""Root conftest.py for apps/api.

Ensures the project root (apps/api) is on sys.path so that
`from app import ...` works regardless of how pytest is invoked.
"""

import sys
from pathlib import Path

# Add apps/api to sys.path so `from app import ...` works.
sys.path.insert(0, str(Path(__file__).parent))
