#!/usr/bin/python

import sys
import numpy as np
import matplotlib.pyplot as plt
#from scipy.interpolate import splrep, splev,BSpline
from scipy.interpolate import make_interp_spline

Hartree2kcal = 627.503
eV2kcal      = 23.0609
rad2deg      = 180.0/np.pi 

# ========= Functions

def load_dat( fname, nx=6 ):
    data = np.genfromtxt(fname, comments='?')
    #data = np.loadtxt('Emap.dat', comments='?')
    #print(data)
    print(data.shape)
    rs=data[:,2]    #;print("rs   ", rs  )
    angs=data[:,4]  #;print("angs ", angs)
    Es=data[:,6]    #;print("Es   ", Es  )
    angs = np.reshape( angs, (-1,nx) )
    rs   = np.reshape( rs, (-1,nx) )
    Es   = np.reshape( Es, (-1,nx) )
    return Es,rs,angs

def plot(Es, cmap='plasma',vmin=0,vmax=5.0, extent=None):
    plt.imshow( Es, cmap=cmap, vmax=vmax, vmin=vmin, origin='lower', extent=extent ); 
    plt.colorbar(); 
    #plt.title('B3LYP'); 
    plt.xlabel('Distance [A]')
    plt.ylabel('Angle [deg.]')
    plt.axis('tight')



# =============== Main

fname='Emap'
if len(sys.argv)>1: fname=sys.argv[1]

E_b3lyp, rs,angs  = load_dat(fname+".dat",     )
E_dftb,  rs,angs  = load_dat(fname+"_dftb.dat" )

#print( "E_b3lyp.min(), E_b3lyp.max()  ",  E_b3lyp.min(), E_b3lyp.max() )
E_b3lyp*=Hartree2kcal;     E_b3lyp-=E_b3lyp.min()
E_dftb*=eV2kcal;           E_dftb-=E_dftb.min()

cmap='plasma'

vmax=1.0
vmaxdif=1.0

r0=2.0

rs_      = rs[:,0]+r0
angs_deg = angs[0,:]*rad2deg
extent=[rs_.min(),rs_.max(), angs_deg.min(),angs_deg.max() ]

print(extent)

# ------- Fig 2 - 2D E imshow

plt.figure(figsize=(15,5))

plt.subplot(1,3,1); plot(E_b3lyp.T, cmap=cmap,vmin=0,vmax=vmax, extent=extent); plt.title('B3LYP');
plt.subplot(1,3,2); plot(E_dftb.T,  cmap=cmap,vmin=0,vmax=vmax, extent=extent); plt.title('DFTB+');
plt.subplot(1,3,3); plot((E_b3lyp-E_dftb).T,  cmap='seismic',vmin=-vmaxdif,vmax=vmaxdif, extent=extent); plt.title('diff');

plt.savefig( 'Emap.png', bbox_inches='tight' )

# ------- Fig 2 - 1D Emin

Emin_b3lyp = np.min( E_b3lyp, axis=0 )
Emin_dftb  = np.min( E_dftb,  axis=0 )

xnew = np.linspace( extent[2], extent[3], 100 )

plt.figure(figsize=(3,3))
plt.plot( angs_deg, Emin_b3lyp, 'ok', label='B3LYP' )
plt.plot( angs_deg, Emin_dftb , 'or', label='DFTB+' )

Emin_b3lyp_sp = make_interp_spline(angs_deg, Emin_b3lyp)
Emin_dftb_sp  = make_interp_spline(angs_deg, Emin_dftb)
plt.plot(xnew,Emin_b3lyp_sp(xnew),'-k')
plt.plot(xnew,Emin_dftb_sp (xnew),'-r')

# --- approx 1
#Emin_b3lyp_sp = splrep(angs_deg,Emin_b3lyp,s=len(angs_deg))
#Emin_dftb_sp  = splrep(angs_deg,Emin_dftb ,s=len(angs_deg))
#plt.plot(xnew,splev(xnew,Emin_b3lyp_sp),'-r')
#plt.plot(xnew,splev(xnew,Emin_dftb_sp),'-b')
# --- approx 2
#plt.plot(xnew,BSpline(*Emin_b3lyp_sp)(xnew),'-r')
#plt.plot(xnew,BSpline(*Emin_dftb_sp)(xnew),'-b')

plt.legend()
plt.ylabel('E(r_min) [kcal/mol]')
plt.xlabel('Angle [deg.]')
plt.grid()

plt.tight_layout()
plt.savefig( 'E_ang_rmin.png', bbox_inches='tight' )


# ------- Fig 2 - 1D E(r) ang=60deg
plt.figure(figsize=(3,3))
plt.plot( rs_, E_b3lyp[:,-2], '-k', label='B3LYP' )
plt.plot( rs_, E_dftb [:,-2], '-r', label='DFTB+' )

plt.legend()
plt.ylabel('E(r,60deg) [kcal/mol]')
plt.xlabel('r [A]')
plt.grid()
plt.tight_layout()
plt.savefig( 'E_r_a60.png', bbox_inches='tight' )

plt.show()
