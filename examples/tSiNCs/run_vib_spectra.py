#!/usr/bin/env python3
"""Deprecated wrapper — use: python vib_spectra.py run <molecule> ..."""
import sys
from vib_spectra import main

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] not in ('run', 'plot', 'match', 'export', 'migrate', 'list'):
        sys.argv.insert(1, 'run')
    main()
