#!/usr/bin/env python3
"""Deprecated wrapper — use: python vib_spectra.py plot <molecule> ..."""
import sys
from vib_spectra import main

if __name__ == '__main__':
    sys.argv = [sys.argv[0], 'plot'] + sys.argv[1:]
    main()
