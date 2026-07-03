#!/bin/bash
# ==================================================================
# Submit all GPAW Fukui jobs to Metacentrum queue
# with per-molecule resource estimates
#
# Usage:
#   ./submit_all.sh          # submit all 8 molecules
#   ./submit_all.sh H2O      # submit only H2O (with small-mol resources)
# ==================================================================

# Per-molecule resources: "name:ncpus:mem:walltime"
SPECS=(
    "H2O:4:8gb:02:00:00"
    "CH2O:4:8gb:02:00:00"
    "CH2NH:4:8gb:02:00:00"
    "C2H4:4:8gb:02:00:00"
    "pyrrol:8:16gb:04:00:00"
    "pyridine:8:16gb:04:00:00"
    "pentacene:16:32gb:12:00:00"
    "PTCDA:16:32gb:12:00:00"
)

if [ -n "$1" ]; then
    SPECS=("$1:0:0:0")  # placeholder, will be replaced below
    # Find matching spec
    found=""
    for spec in "${SPECS[@]}"; do
        name=$(echo "$spec" | cut -d: -f1)
        if [ "$name" = "$1" ]; then found="$spec"; break; fi
    done
    if [ -z "$found" ]; then
        echo "Unknown molecule: $1"
        echo "Available: H2O CH2O CH2NH C2H4 pyrrol pyridine pentacene PTCDA"
        exit 1
    fi
    SPECS=("$found")
fi

for spec in "${SPECS[@]}"; do
    IFS=':' read -r name ncpus mem walltime <<< "$spec"
    echo "Submitting $name  (ncpus=$ncpus, mem=$mem, walltime=$walltime)"
    qsub -v mol=$name \
         -l select=1:ncpus=$ncpus:mem=$mem:scratch_local=10gb \
         -l walltime=$walltime \
         -N fukui_${name} \
         submit.pbs
done

echo ""
echo "Check status: qstat -u prokop"
