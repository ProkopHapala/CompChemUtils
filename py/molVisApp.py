#!/usr/bin/env python3
"""molVisApp.py -- Interactive molecular geometry visualizer using Vispy + PyQt5.

Usage:  python -m py.molVisApp  [<geometry_file.(xyz|POSCAR)>]"""

import sys, os, numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui
import vispy.scene
from vispy.scene import visuals

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from py import AtomicSystem
from py import elements

ATOM_SCALE = 0.5
VP_SIZE = 0.5
VP_COLOR = (0.0, 1.0, 1.0, 1.0)
VP_SEL = (1.0, 0.5, 0.0, 1.0)
VEC_COLOR = (1.0, 0.0, 1.0, 1.0)
BOND_COLOR = (0.5, 0.5, 0.5, 0.7)
SEL_COLOR = (1.0, 1.0, 0.0, 0.6)

def _hex2rgba(h): h=h.lstrip('#'); return tuple(int(h[i:i+2],16)/255.0 for i in (0,2,4))+(1.0,)

def _atom_props(enames):
    cols=np.empty((len(enames),4),dtype=np.float32); sizes=np.empty(len(enames),dtype=np.float32)
    for i,en in enumerate(enames):
        rec=elements.ELEMENT_DICT.get(en,(0,'X',1,0,'s','U',1.0,2.0,'#FF00FF',0,0))
        cols[i]=_hex2rgba(rec[8] if len(rec)>8 else '#FF00FF'); sizes[i]=(rec[7] if len(rec)>7 else 2.0)*ATOM_SCALE*2.0
    return cols,sizes

def _load_poscar(path):
    with open(path) as f: lines=[l.strip() for l in f]
    sc=float(lines[1]); lvec=np.array([[float(x) for x in lines[i].split()] for i in range(2,5)])*sc
    p5=lines[5].split(); p6=lines[6].split()
    if p5[0].isalpha():
        enames_line=p5; counts=[int(x) for x in p6]; st=7
    else:
        enames_line=['X']; counts=[int(x) for x in p5]; st=6
    if lines[st].lower().startswith('s'): st+=1
    ct=lines[st].lower()[0]; st+=1
    crds=[]
    for i in range(st,st+sum(counts)):
        crds.append([float(x) for x in lines[i].split()[:3]])
    crds=np.array(crds)
    if ct=='d': crds=crds@lvec
    enames=[]
    for e,c in zip(enames_line,counts): enames.extend([e]*c)
    return AtomicSystem.AtomicSystem(apos=crds,enames=enames,lvec=lvec)


class MolVisCanvas(vispy.scene.SceneCanvas):
    def __init__(self,parent=None):
        super().__init__(keys='interactive',show=True,parent=parent)
        self.unfreeze()
        self.view=self.central_widget.add_view(); self.view.camera='turntable'; self.view.camera.fov=45
        self.sys=None; self.sel=set(); self.vps=[]; self.vecs=[]
        self.atoms=None; self.bonds=None; self.vpm=None; self.vec=None; self.selh=None
        self._md=False
        self.freeze()

    def load(self,fname):
        if fname.lower().endswith('poscar') or os.path.basename(fname).upper().startswith('POSCAR'):
            self.sys=_load_poscar(fname)
        else:
            self.sys=AtomicSystem.AtomicSystem(fname=fname)
        self.sel.clear(); self.vps.clear(); self.vecs.clear()
        if self.sys.bonds is None or len(self.sys.bonds)==0: self.sys.findBonds(Rcut=3.5,RvdwCut=1.2)
        self._setup(); self._center()

    def _setup(self):
        for v in (self.atoms,self.bonds,self.vpm,self.vec,self.selh):
            if v is not None: v.parent=None
        s=self.sys
        ac,ar=_atom_props(s.enames)
        self.atoms=visuals.Markers(parent=self.view.scene,antialias=True,scaling='scene')
        self.atoms.set_data(pos=s.apos,face_color=ac,size=ar,edge_color='black',edge_width=1)
        if s.bonds is not None and len(s.bonds)>0:
            pos=[]
            for ia,ib in s.bonds: pos.append(s.apos[ia]); pos.append(s.apos[ib])
            self.bonds=visuals.Line(pos=np.array(pos),color=BOND_COLOR,width=2,parent=self.view.scene,method='gl')
        else: self.bonds=None
        self.selh=visuals.Markers(parent=self.view.scene,antialias=True,scaling='scene'); self._upd_sel()
        self.vpm=visuals.Markers(parent=self.view.scene,antialias=True,scaling='scene'); self._upd_vp()
        self.vec=visuals.Line(parent=self.view.scene,color=VEC_COLOR,width=3,method='gl'); self._upd_vec()

    def _center(self):
        if self.sys is None: return
        self.view.camera.center=np.mean(self.sys.apos,axis=0)
        bb=np.max(self.sys.apos,axis=0)-np.min(self.sys.apos,axis=0)
        self.view.camera.distance=max(np.max(bb)*2.5,5.0)

    def _upd_sel(self):
        if self.selh is None: return
        if self.sel:
            sp=np.array([self.sys.apos[i] for i in self.sel])
            sz=np.array([_atom_props([self.sys.enames[i]])[1][0]*1.3 for i in self.sel])
            self.selh.set_data(pos=sp,face_color=SEL_COLOR,size=sz,edge_color='yellow',edge_width=2)
            self.selh.visible=True
        else: self.selh.visible=False

    def _upd_vp(self):
        if self.vpm is None: return
        if self.vps:
            p=np.array([vp['pos'] for vp in self.vps])
            c=np.zeros((len(self.vps),4),dtype=np.float32)
            for i,vp in enumerate(self.vps): c[i]=VP_SEL if vp['sel'] else VP_COLOR
            self.vpm.set_data(pos=p,face_color=c,size=VP_SIZE,edge_color='white',edge_width=2)
            self.vpm.visible=True
        else: self.vpm.visible=False

    def _upd_vec(self):
        if self.vec is None: return
        if self.vecs:
            pos=[]
            for v in self.vecs:
                p1=self.vps[v['p1']]['pos']; p2=self.vps[v['p2']]['pos']; d=p2-p1
                pos.append(p1-d*5); pos.append(p2+d*5)
            self.vec.set_data(pos=np.array(pos),color=VEC_COLOR)
            self.vec.visible=True
        else: self.vec.visible=False

    # ---- picking ----
    def _pick_atom(self,epos):
        if self.sys is None or self.atoms is None: return None
        tr=self.atoms.transforms.get_transform('visual','document')
        mx,my=epos[0],epos[1]; best=None; bestd=float('inf')
        for i,p in enumerate(self.sys.apos):
            sp=tr.map(p)
            if sp[2]<0 or sp[2]>1: continue
            r=_atom_props([self.sys.enames[i]])[1][0]*0.5
            dx,dy=sp[0]-mx,sp[1]-my; d2=dx*dx+dy*dy
            if d2<r*r and d2<bestd: bestd=d2; best=i
        return best

    def _pick_vp(self,epos):
        if not self.vps or self.vpm is None: return None
        tr=self.vpm.transforms.get_transform('visual','document')
        mx,my=epos[0],epos[1]; best=None; bestd=float('inf')
        for i,vp in enumerate(self.vps):
            sp=tr.map(vp['pos'])
            if sp[2]<0 or sp[2]>1: continue
            dx,dy=sp[0]-mx,sp[1]-my; d2=dx*dx+dy*dy
            if d2<VP_SIZE*VP_SIZE and d2<bestd: bestd=d2; best=i
        return best

    # ---- events ----
    def on_mouse_press(self,ev):
        if ev.button==1 and not self._md:
            self._md=True
            vi=self._pick_vp(ev.pos)
            if vi is not None: self._tgl_vp(vi); return
            ai=self._pick_atom(ev.pos)
            if ai is not None: self._tgl_atom(ai); return
        super().on_mouse_press(ev)

    def on_mouse_release(self,ev):
        self._md=False
        super().on_mouse_release(ev)

    def _tgl_atom(self,i):
        self.sel.discard(i) if i in self.sel else self.sel.add(i); self._upd_sel()

    def _tgl_vp(self,i):
        self.vps[i]['sel']=not self.vps[i]['sel']; self._upd_vp()

    def mk_vp(self):
        if len(self.sel) not in (2,3,4):
            QtWidgets.QMessageBox.warning(self.native.parent(),"Selection","Select exactly 2, 3 or 4 atoms."); return
        idx=tuple(sorted(self.sel))
        for vp in self.vps:
            if vp['src']==idx: QtWidgets.QMessageBox.information(self.native.parent(),"Info","VP already exists."); return
        self.vps.append({'pos':np.mean([self.sys.apos[i] for i in idx],axis=0),'src':idx,'sel':False})
        self._upd_vp()

    def mk_vec(self):
        sv=[i for i,vp in enumerate(self.vps) if vp['sel']]
        if len(sv)!=2:
            QtWidgets.QMessageBox.warning(self.native.parent(),"Selection","Select exactly 2 virtual points."); return
        p1,p2=sv
        for v in self.vecs:
            if (v['p1']==p1 and v['p2']==p2) or (v['p1']==p2 and v['p2']==p1): return
        pos1=self.vps[p1]['pos']; pos2=self.vps[p2]['pos']
        self.vecs.append({'p1':p1,'p2':p2,'pos':(pos1+pos2)/2,'dir':pos2-pos1})
        self._upd_vec()

    def clear_sel(self):
        self.sel.clear()
        for vp in self.vps: vp['sel']=False
        self._upd_sel(); self._upd_vp()

    def clear_vp(self):
        self.vps.clear(); self.vecs.clear(); self._upd_vp(); self._upd_vec()


class MolVisApp(QtWidgets.QMainWindow):
    def __init__(self,fname=None):
        super().__init__()
        self.setWindowTitle("MolVis — Interactive Geometry & Vectors")
        self.resize(1200,800)
        cw=QtWidgets.QWidget(); self.setCentralWidget(cw)
        hl=QtWidgets.QHBoxLayout(cw)
        self.canvas=MolVisCanvas(parent=self)
        hl.addWidget(self.canvas.native,1)
        pl=QtWidgets.QVBoxLayout(); hl.addLayout(pl,0)
        btn=QtWidgets.QPushButton("Open File"); btn.clicked.connect(self.open_file); pl.addWidget(btn)
        if fname: self.canvas.load(fname)
        pl.addWidget(QtWidgets.QLabel("--- Atoms ---"))
        b=QtWidgets.QPushButton("Clear Atom Sel"); b.clicked.connect(self.canvas.clear_sel); pl.addWidget(b)
        pl.addWidget(QtWidgets.QLabel("--- Virtual Points ---"))
        b=QtWidgets.QPushButton("Create VP (2/3/4 atoms)"); b.clicked.connect(self.canvas.mk_vp); pl.addWidget(b)
        b=QtWidgets.QPushButton("Clear All VPs"); b.clicked.connect(self.canvas.clear_vp); pl.addWidget(b)
        pl.addWidget(QtWidgets.QLabel("--- Vectors ---"))
        b=QtWidgets.QPushButton("Create Vector (2 VPs)"); b.clicked.connect(self.canvas.mk_vec); pl.addWidget(b)
        pl.addStretch()

    def open_file(self):
        fn,_=QtWidgets.QFileDialog.getOpenFileName(self,"Open Geometry","","XYZ Files (*.xyz);;POSCAR (*POSCAR*);;All Files (*)")
        if fn: self.canvas.load(fn)


def main():
    app=QtWidgets.QApplication(sys.argv)
    fname=sys.argv[1] if len(sys.argv)>1 else None
    win=MolVisApp(fname=fname); win.show()
    sys.exit(app.exec_())

if __name__=='__main__':
    main()
