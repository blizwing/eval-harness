import sys
from pathlib import Path

# Repo root isn't a package (Day-prefixed modules import each other as bare
# top-level names), so tests need it on sys.path regardless of where pytest
# is invoked from.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
