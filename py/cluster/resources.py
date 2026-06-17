"""
cluster/resources.py — hardware resource specification for cluster jobs.
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class ResourceSpec:
    """Specify compute resources for a cluster job.

    Attributes
    ----------
    n_cores    : number of CPU cores (OpenMP / MPI)
    n_nodes    : number of nodes (for MPI multi-node)
    mem_gb     : RAM in GB per node
    walltime_h : walltime limit in hours
    gpu        : GPU type string, e.g. 'a100', 'rtx2080'; None = no GPU
    n_gpu      : number of GPUs per node
    queue      : queue / partition name
    extra      : arbitrary extra PBS/SLURM directives
    """
    n_cores:    int = 1
    n_nodes:    int = 1
    mem_gb:     float = 4.0
    walltime_h: float = 24.0
    gpu:        Optional[str] = None
    n_gpu:      int = 0
    queue:      Optional[str] = None
    extra:      List[str] = field(default_factory=list)

    def walltime_str(self) -> str:
        """Format walltime as HH:MM:SS for PBS."""
        h = int(self.walltime_h)
        m = int((self.walltime_h - h) * 60)
        return f"{h:02d}:{m:02d}:00"

    def mem_mb(self) -> int:
        return int(self.mem_gb * 1024)
