#!/bin/bash
set -euo pipefail
umask 077
cd /home/admin/gpu-job
exec 9>/home/admin/gpu-job/.job.lock
flock -n 9 || { echo 'A GPU job is already running through this launcher' >&2; exit 1; }
export CUDA_VISIBLE_DEVICES=0
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
run_dir=$(mktemp -d /home/admin/gpu-job/runs/run-XXXXXXXX)
printf 'Run directory: %s\n' "$run_dir"
cp pyproject.toml uv.lock .python-version "$run_dir/"
cp src/train.py "$run_dir/"
if .venv/bin/python -u src/train.py --output "$run_dir" "$@" 2>&1 | tee "$run_dir/train.log"; then
    printf '0\n' > "$run_dir/exit-code.txt"
else
    result=$?
    printf '%s\n' "$result" > "$run_dir/exit-code.txt"
    exit "$result"
fi
