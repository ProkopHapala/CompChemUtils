import subprocess
import time

# Start cp2k_shell
p = subprocess.Popen(['cp2k_shell'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

# Wait for READY
line = p.stdout.readline().strip()
print(f"START: {line}")
assert line == "* READY", f"Expected * READY, got: {line}"

# Send RUN command
p.stdin.write("RUN ch4_direct.inp ch4_direct.out\n")
p.stdin.flush()

# cp2k_shell should now process the RUN command
# It may print various things or just nothing until done
# Let's wait and check if output file is being written
print("RUN sent, waiting...")

# Wait up to 60 seconds for output to appear
for i in range(60):
    import os
    if os.path.exists('ch4_direct.out') and os.path.getsize('ch4_direct.out') > 0:
        with open('ch4_direct.out') as f:
            content = f.read()
            if 'PROGRAM ENDED' in content:
                print(f"Done after {i+1}s")
                break
    time.sleep(1)
else:
    print("Timeout waiting for RUN")

# Now read any remaining stdout
import select
import os
while True:
    import select
    ready, _, _ = select.select([p.stdout], [], [], 0.1)
    if ready:
        line = p.stdout.readline().strip()
        if line:
            print(f"OUT: {line}")
    else:
        break

# Send EXIT
p.stdin.write("EXIT\n")
p.stdin.flush()

# Wait for process to finish
p.wait(timeout=5)
print(f"Return code: {p.returncode}")
