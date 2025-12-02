"""Allow running as python -m dictacode_hid"""

from dictacode_hid.main import main


if __name__ == "__main__":
    import sys

    sys.exit(main())
