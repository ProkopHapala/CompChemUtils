"""
py/interfaces/gpaw.py — GPAW backend for periodic / aperiodic DFT with PAW.

Wraps ASE + GPAW for local execution and exports self-contained Python
runner scripts for cluster execution.
"""

import os
import numpy as np
from typing import Optional, List
from ._base import CalculationBackend
from .. import atomicUtils as au
from ..system_specific import MetalTips as mt
from .. import geom_engine as ge


def _ensure_dir(d):
    os.makedirs(d, exist_ok=True)


def build_surface_frame(metal='Ag', size=(2, 2, 2), a=None, vacuum=10.0, height=2.0, position='fcc'):
    a = a if a is not None else mt.lattice_constant(metal)
    slab, i_ad = mt.build_fcc111_adatom(metal=metal, size=size, a=a, vacuum=vacuum, height=height, position=position, periodic=True)
    base3 = mt.pick_fcc_hollow_base3(slab, i_ad)
    return slab, i_ad, base3


def ag111_directions_from_base3(slab, i_adatom, base3, tilt_degs=(20.0, 45.0)):
    ps = slab.get_positions()
    pA = ps[i_adatom]
    bps = np.array([ps[i] for i in base3], dtype=float)
    v_corner = bps[0] - pA
    v_corner[2] = 0.0
    u_corner = ge._normalize(v_corner)
    v_face = 0.5 * (bps[1] + bps[2]) - pA
    v_face[2] = 0.0
    u_face = ge._normalize(v_face)
    z = np.array((0.0, 0.0, 1.0))
    out = [{'name': 'up', 'theta_deg': 0.0, 'azim_kind': 'none', 'fwd': z.copy(), 'ref_lat': u_corner.copy()}]
    for th in tilt_degs:
        sth = np.sin(np.deg2rad(th))
        cth = np.cos(np.deg2rad(th))
        for kind, u in (('corner', u_corner), ('face', u_face)):
            fwd = ge._normalize(u * sth + z * cth)
            out.append({'name': f"tilt{int(round(th))}_{kind}", 'theta_deg': float(th), 'azim_kind': kind, 'fwd': fwd, 'ref_lat': u.copy()})
    return out


def export_surface_movie_from_molecule_frames(
    mol_xyz,
    out_xyz,
    metal='Ag',
    surface_size=(2, 2, 2),
    a=None,
    vacuum=10.0,
    adatom_height=2.0,
    dist=2.0,
    tilt_degs=(20.0, 45.0),
    roll_degs=(0.0, 90.0),
    remove_epairs=True,
    export_formats=('extxyz', 'cif', 'vasp'),
    outdir_struct=None,
    plot_dirs_png=None,
):
    slab, i_ad, base3 = build_surface_frame(metal=metal, size=surface_size, a=a, vacuum=vacuum, height=adatom_height)
    dirs = ag111_directions_from_base3(slab, i_ad, base3, tilt_degs=tilt_degs)
    if plot_dirs_png is not None:
        ge.plot_directions_3d(dirs, plot_dirs_png)
    mol = ge.AtomicSystem(fname=mol_xyz)
    mol.neighs(bBond=True)
    i_host, host_element = ge._find_host_atom(mol)
    origin_m, fw_m, up_m, mask_keep = ge._mol_frame_from_epairs(mol, i_host, host_element=host_element)
    M_rows = au.makeRotMat(fw_m, up_m)
    if remove_epairs:
        mol_es = [e for e, m in zip(mol.enames, mask_keep) if m]
        mol_qs = mol.qs[mask_keep] if mol.qs is not None else None
        mol_ps = mol.apos[mask_keep]
    else:
        mol_es = list(mol.enames)
        mol_qs = mol.qs
        mol_ps = mol.apos
    surf_es, surf_ps, lvec, pbc = mt.slab_to_arrays(slab)
    n_s = len(surf_es)
    n_m = len(mol_es)
    q_s = np.zeros(n_s)
    q_m = mol_qs if mol_qs is not None else np.zeros(n_m)
    qs = np.concatenate([q_s, q_m])
    with open(out_xyz, 'w') as fout:
        for idir, ddir in enumerate(dirs):
            fwd_t = ddir['fwd']
            for iroll, rdeg in enumerate(roll_degs):
                idof = idir * len(roll_degs) + iroll
                up0_t = ge._safe_up_from_ref(fwd_t, ddir['ref_lat'])
                up_t = ge._roll_up(fwd_t, up0_t, rdeg)
                T_rows = au.makeRotMat(fwd_t, up_t)
                target_origin = surf_ps[i_ad] + fwd_t * dist
                mol_ps2 = ge._transform_positions(mol_ps, origin_m, M_rows, T_rows, target_origin)
                es = surf_es + mol_es
                ps = np.vstack([surf_ps, mol_ps2])
                comment = f"dof={idof} idir={idir} iroll={iroll} dir={ddir['name']} theta={ddir['theta_deg']:.1f} roll={rdeg:.1f} host={host_element}[{i_host}] dist={dist:.3f} surf=Ag111_{surface_size[0]}x{surface_size[1]}x{surface_size[2]} adH={adatom_height:.3f}"
                flat = ' '.join(f'{v:.6f}' for v in lvec.flatten())
                extxyz_comment = f'Lattice="{flat}" Properties=species:S:1:pos:R:3 {comment}'
                au.writeToXYZ(fout, es, ps, qs=qs, comment=extxyz_comment, bHeader=True)
    if outdir_struct is not None:
        _ensure_dir(outdir_struct)
        try:
            from ase import Atoms
        except Exception as e:
            raise ImportError("ASE is required to write VESTA/ase-gui formats") from e
        for idir, ddir in enumerate(dirs):
            fwd_t = ddir['fwd']
            for iroll, rdeg in enumerate(roll_degs):
                up0_t = ge._safe_up_from_ref(fwd_t, ddir['ref_lat'])
                up_t = ge._roll_up(fwd_t, up0_t, rdeg)
                T_rows = au.makeRotMat(fwd_t, up_t)
                target_origin = surf_ps[i_ad] + fwd_t * dist
                mol_ps2 = ge._transform_positions(mol_ps, origin_m, M_rows, T_rows, target_origin)
                es = surf_es + mol_es
                ps = np.vstack([surf_ps, mol_ps2])
                atoms = Atoms(symbols=es, positions=ps, cell=lvec, pbc=pbc)
                tag = f"{ddir['name']}_roll{int(round(rdeg))}"
                if 'extxyz' in export_formats:
                    atoms.write(os.path.join(outdir_struct, f"{tag}.xyz"), format='extxyz')
                if 'cif' in export_formats:
                    atoms.write(os.path.join(outdir_struct, f"{tag}.cif"), format='cif')
                if 'vasp' in export_formats:
                    atoms.write(os.path.join(outdir_struct, f"{tag}.POSCAR"), format='vasp')
    return {'out_xyz': out_xyz, 'n_frames': len(dirs) * len(roll_degs), 'surface_adatom_index': int(i_ad), 'base3': tuple(int(i) for i in base3)}


def build_surface_edgepair_frame(metal='Ag', size=(2, 2, 2), a=None, vacuum=10.0, height=2.0, position0='fcc', shift_frac=(0.5, 0.0)):
    a = a if a is not None else mt.lattice_constant(metal)
    slab, i_ad0, i_ad1 = mt.build_fcc111_adatom_pair(metal=metal, size=size, a=a, vacuum=vacuum, height=height, position0=position0, shift_frac=shift_frac, periodic=True)
    return slab, int(i_ad0), int(i_ad1)


def export_surface_edgepair_movie_from_molecule(
    mol_xyz,
    out_xyz,
    surface_size=(2, 2, 2),
    a=4.086,
    vacuum=10.0,
    adatom_height=2.0,
    position0='fcc',
    shift_frac=(0.5, 0.0),
    lift=2.0,
    tilts_deg=(0.0, 15.0, 30.0),
    anchor_element=None,
    origin_mode='axis_mid',
    target_up_mode='standing',
    clash_factor=0.7,
    clash_max_report=12,
    auto_fix=True,
    lift_step=0.25,
    lift_max=8.0,
    export_formats=('extxyz', 'cif', 'vasp'),
    outdir_struct=None,
):
    slab, i_ad0, i_ad1 = build_surface_edgepair_frame(size=surface_size, a=a, vacuum=vacuum, height=adatom_height, position0=position0, shift_frac=shift_frac)
    surf_es, surf_ps, lvec, pbc = mt.slab_to_arrays(slab)
    mol = ge.AtomicSystem(fname=mol_xyz)
    mol.neighs(bBond=True)
    i_anchor, (i0_axis, i1_axis) = ge._infer_edge_anchors(mol, anchor_element=anchor_element)
    mol_es = list(mol.enames)
    mol_ps = np.array(mol.apos, dtype=np.float64)
    p0 = surf_ps[i_ad0]
    p1 = surf_ps[i_ad1]
    edge_mid = 0.5 * (p0 + p1)
    edge_axis = ge._normalize(p1 - p0)
    z_axis = np.array((0.0, 0.0, 1.0))
    if abs(np.dot(z_axis, edge_axis)) > 0.95:
        z_axis = np.array((0.0, 1.0, 0.0))
    swap_edge = False
    up_sign = 1.0
    if auto_fix:
        best = ge.auto_edge_placement(
            sub_es=surf_es,
            sub_ps=surf_ps,
            mol_es=mol_es,
            mol_ps=mol_ps,
            edge_p0=p0,
            edge_p1=p1,
            i_anchor=int(i_anchor),
            i_axis0=int(i0_axis),
            i_axis1=int(i1_axis),
            tilts_deg=tuple(tilts_deg),
            lift0=float(lift),
            origin_mode=origin_mode,
            target_up_mode=target_up_mode,
            clash_factor=float(clash_factor),
            lift_step=float(lift_step),
            lift_max=float(lift_max),
        )
        swap_edge = bool(best['swap_edge'])
        up_sign = float(best['target_up_sign'])
        lift = float(best['lift'])
        if best.get('nshort', 0) > 0:
            print(f"WARNING auto_edge_placement unresolved nshort={best['nshort']} worst_ratio={best.get('worst_ratio', -1.0):.3f} out={out_xyz}")
        if best.get('oxygen_dz', 0.0) > 0.0:
            print(f"WARNING oxygen_up oxygen_dz={best['oxygen_dz']:.3f} out={out_xyz}")
    if swap_edge:
        p0, p1 = p1, p0
    n_s = len(surf_es)
    n_m = len(mol_es)
    q_s = np.zeros(n_s)
    q_m = mol.qs if mol.qs is not None else np.zeros(n_m)
    qs = np.concatenate([q_s, q_m])
    with open(out_xyz, 'w') as fout:
        for it, tilt in enumerate(tilts_deg):
            mol_ps2 = ge.place_molecule_on_edge(
                mol_es=mol_es,
                mol_ps=mol_ps,
                edge_p0=p0,
                edge_p1=p1,
                i_anchor=int(i_anchor),
                i_axis0=int(i0_axis),
                i_axis1=int(i1_axis),
                lift=float(lift),
                tilt_deg=float(tilt),
                z_axis=z_axis,
                origin_mode=origin_mode,
                target_up_mode=target_up_mode,
                target_up_sign=up_sign,
            )
            es = surf_es + mol_es
            ps = np.vstack([surf_ps, mol_ps2])
            shorts = au.findShortContactsNP(ps, es, factor=float(clash_factor))
            if shorts:
                shorts.sort(key=lambda x: x[2])
                print(f"WARNING short_contacts n={len(shorts)} dof={it} tilt={float(tilt):.2f} out={out_xyz}")
                for k, (i, j, r, rmin) in enumerate(shorts[:int(clash_max_report)]):
                    ei, ej = es[int(i)], es[int(j)]
                    print(f"  {k:02d} {int(i):4d}({ei}) {int(j):4d}({ej}) r={float(r):.3f}  rmin={float(rmin):.3f}")
            comment = f"dof={it} tilt={float(tilt):.2f} lift={float(lift):.3f} edge=({i_ad0},{i_ad1}) anchor={int(i_anchor)} axis=({int(i0_axis)},{int(i1_axis)}) surf=Ag111_{surface_size[0]}x{surface_size[1]}x{surface_size[2]} adH={adatom_height:.3f} shift={float(shift_frac[0]):.3f},{float(shift_frac[1]):.3f}"
            flat = ' '.join(f'{v:.6f}' for v in lvec.flatten())
            extxyz_comment = f'Lattice="{flat}" Properties=species:S:1:pos:R:3 {comment}'
            au.writeToXYZ(fout, es, ps, qs=qs, comment=extxyz_comment, bHeader=True)
    if outdir_struct is not None:
        _ensure_dir(outdir_struct)
        try:
            from ase import Atoms
        except Exception as e:
            raise ImportError("ASE is required to write VESTA/ase-gui formats") from e
        for tilt in tilts_deg:
            mol_ps2 = ge.place_molecule_on_edge(
                mol_es=mol_es,
                mol_ps=mol_ps,
                edge_p0=p0,
                edge_p1=p1,
                i_anchor=int(i_anchor),
                i_axis0=int(i0_axis),
                i_axis1=int(i1_axis),
                lift=float(lift),
                tilt_deg=float(tilt),
                z_axis=z_axis,
                origin_mode=origin_mode,
                target_up_mode=target_up_mode,
                target_up_sign=up_sign,
            )
            es = surf_es + mol_es
            ps = np.vstack([surf_ps, mol_ps2])
            atoms = Atoms(symbols=es, positions=ps, cell=lvec, pbc=pbc)
            tag = f"tilt{int(round(float(tilt))):03d}"
            if 'extxyz' in export_formats:
                atoms.write(os.path.join(outdir_struct, f"{tag}.xyz"), format='extxyz')
            if 'cif' in export_formats:
                atoms.write(os.path.join(outdir_struct, f"{tag}.cif"), format='cif')
            if 'vasp' in export_formats:
                atoms.write(os.path.join(outdir_struct, f"{tag}.POSCAR"), format='vasp')
    return {'out_xyz': out_xyz, 'n_frames': len(tuple(tilts_deg)), 'adatom_pair': (int(i_ad0), int(i_ad1)), 'edge_mid': edge_mid, 'anchor_index': int(i_anchor), 'axis_pair': (int(i0_axis), int(i1_axis))}


def write_gpaw_runner(fname, structure_file, txt='gpaw.txt', xc='PBE', pw=400, kpts=(4, 4, 1), fix_indices=None):
    with open(fname, 'w') as f:
        f.write("import numpy as np\n")
        f.write("from ase.io import read\n")
        f.write("from ase.constraints import FixAtoms\n")
        f.write("from gpaw import GPAW, PW, FermiDirac\n")
        f.write("\n")
        f.write(f"atoms = read('{structure_file}')\n")
        if fix_indices is not None:
            inds = ",".join(str(int(i)) for i in fix_indices)
            f.write(f"atoms.set_constraint(FixAtoms(indices=[{inds}]))\n")
        f.write("\n")
        f.write(f"calc = GPAW(mode=PW({float(pw)}), xc='{xc}', occupations=FermiDirac(0.1), kpts={{'size': {tuple(kpts)}}}, txt='{txt}')\n")
        f.write("atoms.calc = calc\n")
        f.write("E = atoms.get_potential_energy()\n")
        f.write("print('E[eV]=', E)\n")
        f.write("atoms.write('final.traj')\n")


class GPAWBackend(CalculationBackend):
    """GPAW backend via ASE.

    Parameters
    ----------
    kpts        : k-point mesh (e.g. (1,1,1) for gamma, (4,4,4) for bulk)
    mode        : 'lcao' or 'pw'; if 'pw', ecut (eV) used
    ecut        : plane-wave cutoff in eV (default 300)
    xc          : exchange-correlation functional (default 'PBE')
    spinpol     : spin-polarized calculation
    charge      : total charge
    symmetry    : symmetry exploitation {'off','on','auto'}
    h           : grid spacing for real-space mode (Å); if set, overrides mode='pw'
    maxiter     : SCF max iterations
    mixer       : SCF mixer (default None = GPAW default)
    """
    name = "gpaw"
    capabilities = {'energy', 'relax', 'vibrations', 'phonons', 'density', 'esp'}

    def __init__(self, kpts=(1, 1, 1), mode='pw', ecut=300.0, xc='PBE',
                 spinpol=False, charge=0, symmetry='off', h=None,
                 maxiter=333, mixer=None):
        self.kpts = kpts
        self.mode = mode
        self.ecut = float(ecut)
        self.xc = xc
        self.spinpol = spinpol
        self.charge = charge
        self.symmetry = symmetry
        self.h = h
        self.maxiter = maxiter
        self.mixer = mixer

    # ---- helpers
    def _to_ase(self, geom):
        """Convert AtomicSystem or (apos, es) to ASE Atoms."""
        from ase import Atoms
        from ase.units import Bohr
        if hasattr(geom, 'apos') and hasattr(geom, 'enames'):
            apos, es = geom.apos, geom.enames
            cell = getattr(geom, 'lvec', None)
        else:
            apos, es = geom
            cell = None
        atoms = Atoms(symbols=es, positions=apos, cell=cell, pbc=(cell is not None))
        return atoms

    def _from_ase(self, atoms):
        """Convert ASE Atoms back to (apos, es)."""
        import numpy as np
        return np.array(atoms.positions), list(atoms.get_chemical_symbols())

    def _make_calc(self):
        """Build a GPAW calculator."""
        from gpaw import GPAW, PW, LCAO
        kwargs = {
            'xc': self.xc,
            'kpts': self.kpts,
            'spinpol': self.spinpol,
            'charge': self.charge,
            'symmetry': self.symmetry,
            'maxiter': self.maxiter,
        }
        if self.mixer is not None:
            kwargs['mixer'] = self.mixer
        if self.h is not None:
            kwargs['h'] = self.h
        else:
            if self.mode == 'pw':
                kwargs['mode'] = PW(self.ecut)
            elif self.mode == 'lcao':
                kwargs['mode'] = LCAO()
            else:
                raise ValueError(f"GPAWBackend: unknown mode {self.mode!r}")
        return GPAW(**kwargs)

    # ---- local execution
    def run_energy(self, geom, method=None, basis=None, **kw) -> float:
        self.check('energy')
        atoms = self._to_ase(geom)
        calc = self._make_calc()
        atoms.calc = calc
        if method is not None:
            calc.set(xc=method)
        return float(atoms.get_potential_energy())

    def run_relax(self, geom, method=None, basis=None, constraints=None,
                  fmax=0.05, maxsteps=200, **kw):
        self.check('relax')
        from ase.optimize import BFGS
        atoms = self._to_ase(geom)
        calc = self._make_calc()
        atoms.calc = calc
        if method is not None:
            calc.set(xc=method)
        if constraints:
            for c in constraints:
                if c.type == 'freeze_atoms':
                    from ase.constraints import FixAtoms
                    atoms.set_constraint(FixAtoms(indices=c.atoms))
        opt = BFGS(atoms, maxstep=0.2, logfile='-')
        opt.run(fmax=fmax, steps=maxsteps)
        apos, es = self._from_ase(atoms)
        if hasattr(geom, 'apos'):
            from ..AtomicSystem import AtomicSystem
            out = AtomicSystem(); out.apos = apos; out.enames = es
            out.lvec = atoms.cell.array if atoms.cell.rank > 0 else None
            return out
        return (apos, es)

    def run_vibrations(self, geom, method=None, basis=None, **kw):
        self.check('vibrations')
        from ase.vibrations import Vibrations
        atoms = self._to_ase(geom)
        calc = self._make_calc()
        atoms.calc = calc
        if method is not None:
            calc.set(xc=method)
        vib = Vibrations(atoms)
        vib.run()
        freqs = vib.get_frequencies()
        # modes: Vibrations stores them but we need to extract
        import numpy as np
        return self._vib_result(atoms, freqs, vib)

    def _vib_result(self, atoms, freqs, vib):
        from ..tasks.base import VibResult
        import numpy as np
        na = len(atoms)
        # Extract mass-weighted modes from vib object
        # ASE Vibrations stores in vib.vib[i] = (displacement vector, mode_num)
        # We reconstruct approximate modes
        modes = []
        for i in range(len(freqs)):
            mode = vib.get_mode(i)
            modes.append(mode)
        modes = np.array(modes) if modes else np.zeros((0, na, 3))
        masses = atoms.get_masses()
        return VibResult(geom=None, frequencies=np.array(freqs), modes=modes, masses=masses)

    # ---- export: write a self-contained Python runner script
    def _export_script(self, atoms, script_name, setup_code, run_code, outdir):
        os.makedirs(outdir, exist_ok=True)
        fpath = os.path.join(outdir, script_name)
        with open(fpath, 'w') as f:
            f.write("#!/usr/bin/env python3\n")
            f.write("import numpy as np\n")
            f.write("from ase import Atoms\n")
            f.write("from ase.io import write, read\n")
            f.write("from gpaw import GPAW, PW, LCAO\n")
            f.write("\n")
            # geometry
            f.write(f"symbols = {list(atoms.get_chemical_symbols())}\n")
            f.write(f"positions = np.array({atoms.positions.tolist()})\n")
            cell = atoms.cell.array if atoms.cell.rank > 0 else None
            f.write(f"cell = {cell.tolist() if cell is not None else None}\n")
            f.write("pbc = (cell is not None)\n")
            f.write("atoms = Atoms(symbols=symbols, positions=positions, cell=cell, pbc=pbc)\n")
            f.write("\n")
            # calc setup
            f.write(setup_code + "\n")
            # run
            f.write(run_code + "\n")
        return os.path.abspath(fpath)

    def export_energy(self, geom, method=None, basis=None, outdir='.', fname='gpaw_sp.py', **kw) -> List[str]:
        atoms = self._to_ase(geom)
        xc = method or self.xc
        setup = f"""calc = GPAW(xc='{xc}', kpts={self.kpts}, spinpol={self.spinpol},
            charge={self.charge}, symmetry='{self.symmetry}', maxiter={self.maxiter})"""
        if self.mode == 'pw' and self.h is None:
            setup = f"""calc = GPAW(mode=PW({self.ecut}), xc='{xc}', kpts={self.kpts},
            spinpol={self.spinpol}, charge={self.charge}, symmetry='{self.symmetry}', maxiter={self.maxiter})"""
        run = "atoms.calc = calc\nprint('E =', atoms.get_potential_energy(), 'eV')"
        fpath = self._export_script(atoms, fname, setup, run, outdir)
        return [fpath]

    def export_relax(self, geom, method=None, basis=None, constraints=None,
                     outdir='.', fname='gpaw_relax.py', **kw) -> List[str]:
        atoms = self._to_ase(geom)
        xc = method or self.xc
        setup = f"""calc = GPAW(mode=PW({self.ecut}), xc='{xc}', kpts={self.kpts},
            spinpol={self.spinpol}, charge={self.charge}, symmetry='{self.symmetry}', maxiter={self.maxiter})"""
        run = """from ase.optimize import BFGS
atoms.calc = calc
opt = BFGS(atoms)
opt.run(fmax=0.05)
write('relaxed.xyz', atoms)
print('E =', atoms.get_potential_energy(), 'eV')"""
        fpath = self._export_script(atoms, fname, setup, run, outdir)
        return [fpath]
