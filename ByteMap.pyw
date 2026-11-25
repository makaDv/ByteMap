"""Double-click this file to open ByteMap (runs with pythonw, no console window)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bytemap.gui import main  # noqa: E402

main()
