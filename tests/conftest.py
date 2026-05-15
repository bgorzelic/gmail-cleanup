"""Shared pytest fixtures and path setup.

Adds the repo root to sys.path so `import gmail_cli` works without packaging.
Packaging task will replace this once `pip install -e .` lands.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
