"""Allow running as python -m dictacode_stt"""

from dictacode_stt.main import main


if __name__ == "__main__":
    import sys

    sys.exit(main())
