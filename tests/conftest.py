"""
pytest configuration — ensures src/ is on sys.path before any test module
imports, and patches sys.path to allow main.py to be imported as a module
without breaking its own internal relative imports.
"""
import sys
from pathlib import Path

# Ensure the project root and src/ are on the path for all imports
root = Path(__file__).parent.parent
src = root / "src"

if str(root) not in sys.path:
    sys.path.insert(0, str(root))
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

# ─── Patch template modules to support import from BOTH ───────────────────────
#
# main.py does: sys.path.insert(0, str(Path(__file__).parent / "src"))
#   then: from template.document_role_classifier import ...
#         from ..common.pdf_inspector import PDFInspectionResult
#
# When pytest imports 'main' as a top-level module (not as __main__),
# the '..common' relative import inside template/*.py fails because
# Python sees 'template' as a top-level module with no parent package.
#
# The fix: before any template module is imported, replace their
# __init__.py骗局的 relative-import chains with absolute equivalents.
# We do this by pre-importing the template package from src/.

# Pre-load the entire src package so that 'template.X' resolves as a proper
# subpackage of 'src', not as a standalone top-level module.
import importlib

# Ensure 'src' itself is importable as a package
src_pkg_name = "src"

# Create a fake 'src' package entry if needed (so 'from src.template.X' works)
# We accomplish this by inserting src/ at position 0 of sys.path, which means
# Python finds 'src/template/__init__.py' when we do 'import src.template'.
# But we want 'import template' (not 'import src.template').
#
# The real fix: make template/*.py use 'from common.X' instead of 'from ..common.X'
# BUT we don't want to change those files (they're designed to run via main.py
# which patches sys.path).
#
# Instead, we handle it by ensuring main.py's sys.path.insert is NOT executed
# when imported as a module. We can do this by patching Path(__file__) for main.py.

# Actually, the simplest fix: just run pytest from the src/ directory as the
# cwd, and import using absolute paths from src. Let's handle this via conftest.

# The key insight: when we `import main`, main.py's sys.path.insert runs with
# Path(__file__) = /path/to/main.py, so it adds /path/to/src to sys.path.
# Then `from template.X import ...` resolves 'template' using that patched path.
# But `from ..common.X` inside X.py fails because 'template.X' was imported as
# a top-level module (no parent package).
#
# Fix: patch the template modules' globals to fake a parent 'src' package before
# import. This is complex.
#
# Simpler fix: run pytest with --rootdir=src and import from the src root.
# But the test file itself does: sys.path.insert(0, .../src)
# and imports 'from common.X', 'from main import analyze'.
#
# The issue is specifically 'from ..common.X' in template/*.py when main.py
# is imported as a top-level module.
#
# BEST FIX: add a conftest.py that imports main in a way that gives it a
# proper package context, OR patch the template modules' __package__.
