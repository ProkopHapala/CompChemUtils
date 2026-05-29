import subprocess
import time
import os

# Start cp2k_shell
p = subprocess.Popen(['cp2k_shell'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

# Wait for initial READY
line = p.stdout.readline().strip()
print(f"Got: {line}")
assert line == "* READY", f"Expected * READY, got: {line}"

# Send RUN
p.stdin.write("RUN ch4_direct.inp ch4_direct_run.out\n")
p.stdin.flush()
print("RUN sent")

# Wait for output file
for i in range(60):
    time.sleep(1)
    if os.path.exists('ch4_direct_run.out') and os.path.getsize('ch4_direct_run.out') > 100:
        with open('ch4_direct_run.out', 'r') as f:
            content = f.read()
            if 'PROGRAM ENDED' in content:
                print(f"Calculation done after {i+1}s")
                break
            elif 'ABORT' in content or 'ERROR' in content:
                print(f"Error in calculation after {i+1}s")
                break
    if i % 5 == 0:
        print(f"Waiting... {i+1}s")
else:
    print("Timeout waiting for calculation")

# Check stdout for any messages
import select
while True:
    ready, _, _ = select.select([p.stdout], [], [], 0.5)
    if ready:
        line = p.stdout.readline().strip()
        if line:
            print(f"STDOUT: {line}")
    else:
        break

# Send EXIT
p.stdin.write("EXIT\n")
p.stdin.flush()
try:
    p.wait(timeout=5)
except subprocess.TimeoutExpired:
    p.terminate()
    p.wait()
print(f"Return code: {p.returncode}")

# Check output
if os.path.exists('ch4_direct_run.out'):
    with open('ch4_direct_run.out', 'r') as f:
        lines = f.readlines()
    print(f"Output file: {len(lines)} lines")
    for line in lines:
        if 'ENERGY|' in line or 'Total energy' in line or 'PROGRAM ENDED' in line:
            print(line.strip())
else:
    print("No output file!")
