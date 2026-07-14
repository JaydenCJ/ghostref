"""Allow ``python -m ghostref`` to behave exactly like the ``ghostref`` script."""

import sys

from ghostref.cli import main

if __name__ == "__main__":
    sys.exit(main())
