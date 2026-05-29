import subprocess
import time

p = subprocess.Popen(['cp2k_shell'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

line = p.stdout.readline().strip()
print(f"Got: {line}")

# Send VERSION
p.stdin.write("VERSION\n")
p.stdin.flush()
line = p.stdout.readline().strip()
print(f"VERSION: {line}")

# Wait for READY
line = p.stdout.readline().strip()
print(f"After VERSION: {line}")

# Send EXIT
p.stdin.write("EXIT\n")
p.stdin.flush()
p.wait(timeout=5)
print(f"RC: {p.returncode}")
