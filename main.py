"""Root entrypoint for hosting environments running `python main.py`."""

import sys
from pathlib import Path

# Ensure src/ is on sys.path
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from pai.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
