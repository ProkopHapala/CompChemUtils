#!/bin/bash
# MetaCentrum AI Agent Setup Script
# Run this on your local machine to configure everything

set -e

echo "=== MetaCentrum AI Agent Setup ==="

# Check arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <USERNAME> <FRONTEND> [SSH_KEY_NAME]"
    echo "Example: $0 novak tarkil.metacentrum.cz metacentrum_ai"
    exit 1
fi

USERNAME=$1
FRONTEND=$2
KEYNAME=${3:-metacentrum_ai}

echo "Setting up for user: $USERNAME on frontend: $FRONTEND"

# 1. Generate SSH key if it doesn't exist
if [ ! -f ~/.ssh/${KEYNAME} ]; then
    echo "Generating SSH key..."
    ssh-keygen -t ed25519 -f ~/.ssh/${KEYNAME} -C "ai-agent@${HOSTNAME}" -N ""
else
    echo "SSH key already exists"
fi

# 2. Copy key to MetaCentrum (user will need to enter password)
echo "Copying SSH key to MetaCentrum (enter your MetaCentrum password when prompted)..."
ssh-copy-id -i ~/.ssh/${KEYNAME}.pub ${USERNAME}@${FRONTEND}

# 3. Configure SSH config
echo "Configuring SSH..."
mkdir -p ~/.ssh
if ! grep -q "Host metacentrum-ai" ~/.ssh/config 2>/dev/null; then
    cat >> ~/.ssh/config <<EOF

Host metacentrum-ai
    HostName ${FRONTEND}
    User ${USERNAME}
    IdentityFile ~/.ssh/${KEYNAME}
    ServerAliveInterval 60
    ServerAliveCountMax 3
    ControlMaster auto
    ControlPath ~/.ssh/control-%r@%h:%p
    ControlPersist 4h
EOF
    echo "SSH config added"
else
    echo "SSH config already exists"
fi

chmod 600 ~/.ssh/config

# 4. Test connection
echo "Testing SSH connection..."
ssh metacentrum-ai "echo 'Connection successful'; qstat -u ${USERNAME} || true"

# 5. Create local workspace
echo "Creating workspace..."
mkdir -p ~/meta-workflows/{skills,scripts,inputs,outputs,logs}

# 6. Install monitor script if available
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "${SCRIPT_DIR}/metacentrum_monitor.py" ]; then
    cp "${SCRIPT_DIR}/metacentrum_monitor.py" ~/meta-workflows/scripts/
    chmod +x ~/meta-workflows/scripts/metacentrum_monitor.py
    echo "Monitor script installed"
fi

# 7. Copy skill files if available
if [ -f "${SCRIPT_DIR}/metacentrum_pbs_skill.md" ]; then
    cp "${SCRIPT_DIR}/metacentrum_pbs_skill.md" ~/meta-workflows/skills/
fi
if [ -f "${SCRIPT_DIR}/dft_babysitter_skill.md" ]; then
    cp "${SCRIPT_DIR}/dft_babysitter_skill.md" ~/meta-workflows/skills/
fi

# 8. Create systemd service file (optional)
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/metacentrum-monitor.service <<EOF
[Unit]
Description=MetaCentrum Job Monitor
After=network.target

[Service]
Type=simple
ExecStart=%h/meta-workflows/scripts/metacentrum_monitor.py --user ${USERNAME} --frontend ${FRONTEND} --daemon --interval 300
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Configure your AI agent with the skill files in ~/meta-workflows/skills/"
echo "2. Start monitoring: systemctl --user start metacentrum-monitor"
echo "3. Or use cron: */10 * * * * %h/meta-workflows/scripts/metacentrum_monitor.py --user ${USERNAME} --frontend ${FRONTEND}"
echo "4. Test job submission: ssh metacentrum-ai 'qsub -I -l walltime=00:10:00 -l select=1:ncpus=1:mem=1gb'"
echo ""
echo "SSH alias 'metacentrum-ai' is ready to use."
