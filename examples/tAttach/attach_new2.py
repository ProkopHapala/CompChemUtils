
import sys
import numpy as np
sys.path.append('../../')
from pyBall.atomicUtils import AtomicSystem
# (Make sure the free functions are imported as well.)

backbone  = AtomicSystem(fname='./backbones/thio_ene_SidePoly--.mol2')
endgroup1 = AtomicSystem(fname='./endgroups/guanine--.mol2')
endgroup2 = AtomicSystem(fname='./endgroups/cytosine-.mol2')

backbone.preinitialize_atomic_properties()
endgroup1.preinitialize_atomic_properties()
endgroup2.preinitialize_atomic_properties()


print("\nBackbone:"     ); backbone.print()
#print("Backbone bonds:" ); backbone.printBonds()
#print("Backbone neighs:"); backbone.printNeighs()
#print("Endgroup:"); endgroup.print()

# Attach endgroup copies to the backbone using marker elements.
# Here, the backbone is expected to contain marker atoms with element "Se" (attachment)
# and "F" (up direction), and the endgroup must contain exactly one such pair.
#backbone.attach_group_by_marker(endgroup, markerX="Se", markerY="F", forward_default=np.array([1.0, 0.0, 0.0]), _0=1, pre="X")

backbone.save_mol2('backbone.mol2')
endgroup1.save_mol2('endgroup1.mol2')

backbone.attach_group_by_marker(endgroup1, markerX="Al", markerY="Cl",  _0=1)

backbone.save_mol2('backbone_subs_1.mol2')
backbone.saveXYZ('backbone_subs_1.xyz')

print("Backbone neighs:"); backbone.printNeighs()

backbone.attach_group_by_marker(endgroup2, markerX="Se" , markerY="Cl", _0=1)

backbone.save_mol2('backbone_subs_2.mol2')
backbone.saveXYZ('backbone_subs_2.xyz')


#backbone.save_mol('backbone_with_endgroup.mol')