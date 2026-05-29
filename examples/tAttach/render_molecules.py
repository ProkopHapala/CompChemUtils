#!/usr/bin/python3

import sys
import os
import traceback
import glob
import numpy as np
sys.path.append('../../')
#from pyBall.atomicUtils import AtomicSystem
#from pyBall.plotUtils import render_POVray
from pyBall.moleculeManagement import render_molecule_files

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: render_molecules.py <directory> [extension] [output_dir]")
        print("  directory: Path to directory containing molecule files")
        print("  extension: File extension to process (default: .mol2)")
        print("  output_dir: Directory for output POV files (default: same as input)")
        sys.exit(1)
    directory  = sys.argv[1]
    extension  = sys.argv[2] if len(sys.argv) > 2 else '.mol2'
    output_dir = sys.argv[3] if len(sys.argv) > 3 else None
    render_molecule_files(directory, extension, output_dir)
