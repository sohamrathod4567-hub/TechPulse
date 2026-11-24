"""
TechPulse - Technology Job Market Intelligence Platform.
"""

import sys
from pathlib import Path

# Ensure 'src' directory is in sys.path so 'techpulse' can be imported
# whether invoked as 'python -m src.techpulse...' or 'python -m techpulse...'
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
