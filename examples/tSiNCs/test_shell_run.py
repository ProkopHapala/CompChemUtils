import subprocess
import time
import os

p = subprocess.Popen(['cp2k_shell'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

line = p.stdout.readline().strip()
print(f"Got: {line}")
assert line == "* READY"

# Send RUN
p.stdin.write("RUN ch4_direct.inp ch4_direct_run2.out\n")
p.stdin.flush()
print("RUN command sent")

# cp2k_shell might not print anything during RUN
# Let's poll the output file
for i in range(30):
    time.sleep(1)
    if os.path.exists('ch4_direct_run2.out'):
        size = os.path.getsize('ch4_direct_run2.out')
        if size > 100:
            with open('ch4_direct_run2.out', 'r') as f:
                content = f.read()
                if 'PROGRAM ENDED' in content:
                    print(f"Done after {i+1}s, {size} bytes")
                    break
                elif 'ABORT' in content:
                    print(f"ABORT after {i+1}s")
                    break
    if i % 5 == 4:
        print(f"Waiting {i+1}s...")

# Read any stdout
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
except:
    p.terminate()
    p.wait()
print(f"RC: {p.returncode}")

# Check output
if os.path.exists('ch4_direct_run2.out'):
    with open('ch4_direct_run2.out') as f:
        lines = f.readlines()
    print(f"Output: {len(lines)} lines")
    for line in lines[-10:]:
        print(line.strip())
else:
    print("No output file")
