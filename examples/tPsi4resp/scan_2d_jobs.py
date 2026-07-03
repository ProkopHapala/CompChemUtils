

import sys
import os


sys.path.insert(0, '../../')
from py import atomicUtils as au
from py import FFFit as fff
from py.interfaces import psi4 as psi4u

from pyBall import dftb_utils as dftbu

import numpy as np
import matplotlib.pyplot as plt
#from functools import partial
from functools import partial

#import psi4;   psi4u.psi4=psi4


# https://psicode.org/psi4manual/master/api/psi4.core.Molecule.html
# https://github.com/psi4/psi4numpy/blob/master/Tutorials/01_Psi4NumPy-Basics/1b_molecule.ipynb    
#    * Example: Fitting Lennard-Jones Parameters from Potential Energy Scan


# ============= SETUP 

params = {  # These are the default settings

#'method' : 'scf',
#'method' : 'pbe',
#'method' : 'b3lyp',
#'method' : 'b3lyp-d3',
#'method' : 'mp2',

# 'basis'  : 'sto-3g',
# 'basis'  : '6-31+G',
# 'basis'  : '6-311+G*',
# 'basis'  : '6-311++G**',
# 'basis'  : '6-311++G(3df,3pd)',
# 'basis'    : 'cc-pvdz',
# 'basis'  : 'aug-cc-pvtz',
# 'basis'  : 'def2-QZVPPD',
# 'bsse'     : 'cp',


'nhyphe'       : None, 
'mem'          : '500MB', 
'method'       : 'b3lyp-d3', 
'basis'        : 'CC-pVDZ', 
'bsse'         : "['cp','nocp']", 
'params_block' : None, 
'fname'        : 'psi.in', 
'q'            : 0, 
'multiplicity' : 1, 
'opt'          : True
}



def write_psi4_in( mol,  pars ):
    #if 'ifrag_line' in pars: nhyphen=pars['ifrag_line'] 
    apos,es = mol
    lines = [ "%i %12.8f %12.8f %12.8f" %(es[i],apos[i,0],apos[i,1],apos[i,2]) for i in range(len(es)) ]
    psi4u.write_psi4_in( lines, nhyphen=pars['ifrag_line'], mem=pars['mem'], method=pars['method'], basis=pars['basis'], bsse=pars['bsse'], params_block=pars['params_block'], fname='psi.in', q=pars[''], multiplicity=pars['multiplicity'], opt=pars['opt'] ):
    return 0

# ============ MAIN

mol = au.AtomicSystem( fname='HBond_OCH2_vs_H2O-x-2.xyz' )

rs   = np.arange(-0.6,2.0,0.1)             ;print("rs   ", rs   )
angs  = np.arange(0.0,0.5+1e-8,0.1) * np.pi #+ ang0 

fff.angularScan_1mol(  (mol.apos,mol.enames), [4,5,6], rs, angs, ax1=0,ax2=1, dir=(-1.0,0.0,0.0), xyz_file="scan_in.xyz" )

os.system("jmol_ scan_in.xyz")

#Es, xs = fff.scan_xyz( "scan_in.xyz", fxyzout="scan_out_dftb.xyz", Eout=None, params=params, callback=write_psi4_in )


exit()

