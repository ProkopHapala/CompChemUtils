#!/usr/bin/env python3
"""
MetaCentrum Job Monitor & Babysitter Daemon
Runs on your local machine or a persistent MetaCentrum frontend session
Monitors PBS jobs, detects crashes, and can trigger recovery actions

Usage:
    python3 metacentrum_monitor.py --user YOUR_USERNAME --frontend tarkil.metacentrum.cz

For resident operation, add to crontab:
    */10 * * * * /usr/bin/python3 /path/to/metacentrum_monitor.py --user YOUR_USERNAME --frontend tarkil.metacentrum.cz >> /path/to/monitor.log 2>&1

Or run as systemd service / tmux session for continuous monitoring.
"""

import subprocess
import argparse
import json
import os
import sys
import time
import re
from datetime import datetime
from pathlib import Path

class MetaCentrumMonitor:
    def __init__(self, username, frontend, ssh_key=None, notify_cmd=None, 
                 state_file="~/.metacentrum_monitor_state.json",
                 auto_resubmit=False, max_resubmits=2):
        self.username = username
        self.frontend = frontend
        self.ssh_key = ssh_key
        self.notify_cmd = notify_cmd
        self.state_file = os.path.expanduser(state_file)
        self.auto_resubmit = auto_resubmit
        self.max_resubmits = max_resubmits
        self.state = self.load_state()

    def load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {"jobs": {}, "last_check": None}

    def save_state(self):
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def ssh_command(self, cmd):
        """Execute command on MetaCentrum frontend via SSH"""
        ssh_args = ["ssh"]
        if self.ssh_key:
            ssh_args.extend(["-i", self.ssh_key])
        ssh_args.extend([
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            f"{self.username}@{self.frontend}",
            cmd
        ])
        try:
            result = subprocess.run(ssh_args, capture_output=True, text=True, timeout=30)
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "SSH timeout", 1
        except Exception as e:
            return "", str(e), 1

    def get_running_jobs(self):
        """Get list of currently running/queued jobs"""
        stdout, stderr, rc = self.ssh_command(f"qstat -u {self.username}")
        if rc != 0:
            print(f"Error getting job status: {stderr}")
            return []

        jobs = []
        for line in stdout.strip().split('
')[2:]:  # Skip header lines
            parts = line.split()
            if len(parts) >= 6:
                jobs.append({
                    'jobid': parts[0],
                    'name': parts[1],
                    'user': parts[2],
                    'time': parts[3],
                    'state': parts[4],
                    'queue': parts[5]
                })
        return jobs

    def get_finished_jobs(self):
        """Get recently finished jobs"""
        stdout, stderr, rc = self.ssh_command(f"qstat -x -u {self.username}")
        if rc != 0:
            return []

        finished = []
        for line in stdout.strip().split('
')[2:]:
            parts = line.split()
            if len(parts) >= 6 and parts[4] in ['F', 'E']:
                finished.append({
                    'jobid': parts[0],
                    'name': parts[1],
                    'state': parts[4]
                })
        return finished

    def check_job_output(self, jobid, jobname):
        """Check output files for errors"""
        # Check stderr file
        stdout, stderr, rc = self.ssh_command(
            f"find ~ -name '{jobname}.e{jobid.split('.')[0]}' -type f 2>/dev/null | head -1"
        )
        stderr_file = stdout.strip()

        errors = []
        if stderr_file:
            stdout, _, rc = self.ssh_command(f"cat {stderr_file}")
            if stdout.strip():
                errors.append(f"STDERR: {stdout[:500]}")

        # Check stdout for common error patterns
        stdout, _, rc = self.ssh_command(
            f"find ~ -name '{jobname}.o{jobid.split('.')[0]}' -type f 2>/dev/null | head -1"
        )
        stdout_file = stdout.strip()

        if stdout_file:
            stdout_content, _, _ = self.ssh_command(f"cat {stdout_file}")

            error_patterns = [
                r'(?i)out of memory',
                r'(?i)segmentation fault',
                r'(?i)kill',
                r'(?i)error',
                r'(?i)failed',
                r'(?i)not converged',
                r'(?i)walltime exceeded',
                r'(?i)disk quota exceeded',
            ]

            for pattern in error_patterns:
                matches = re.findall(pattern, stdout_content)
                if matches:
                    errors.append(f"Pattern '{pattern}' found in stdout")

        return errors

    def check_job_success(self, jobid, jobname):
        """Determine if job completed successfully"""
        errors = self.check_job_output(jobid, jobname)

        # Check if expected output files exist
        # This is generic - customize for your specific workflow
        stdout, _, _ = self.ssh_command(
            f"find ~ -name '{jobname}.o{jobid.split('.')[0]}' -type f 2>/dev/null | wc -l"
        )
        has_stdout = int(stdout.strip()) > 0

        return len(errors) == 0 and has_stdout, errors

    def notify(self, message, level="INFO"):
        """Send notification"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = f"[{timestamp}] [{level}] {message}"
        print(full_msg)

        if self.notify_cmd:
            try:
                subprocess.run([self.notify_cmd, full_msg], capture_output=True)
            except:
                pass

    def resubmit_job(self, jobid, jobname):
        """Attempt to resubmit a failed job"""
        # Find original submission script
        stdout, _, _ = self.ssh_command(
            f"grep -l '{jobname}' ~/.*sh 2>/dev/null | head -1"
        )
        script = stdout.strip()

        if not script:
            self.notify(f"Could not find submission script for {jobname}", "ERROR")
            return None

        # Modify script for restart if needed (e.g., add restart flags)
        # This is code-specific - example for VASP:
        # self.ssh_command(f"sed -i 's/ISTART=0/ISTART=1/' {script}")

        stdout, stderr, rc = self.ssh_command(f"qsub {script}")
        if rc == 0:
            new_jobid = stdout.strip()
            self.notify(f"Resubmitted {jobname} as {new_jobid}", "INFO")
            return new_jobid
        else:
            self.notify(f"Resubmit failed: {stderr}", "ERROR")
            return None

    def run(self):
        """Main monitoring loop"""
        self.notify(f"Starting monitor check for {self.username}@{self.frontend}")

        running_jobs = self.get_running_jobs()
        finished_jobs = self.get_finished_jobs()

        # Update state with current running jobs
        for job in running_jobs:
            jobid = job['jobid']
            if jobid not in self.state['jobs']:
                self.state['jobs'][jobid] = {
                    'name': job['name'],
                    'state': job['state'],
                    'submitted': datetime.now().isoformat(),
                    'resubmits': 0,
                    'notified': False
                }
            else:
                self.state['jobs'][jobid]['state'] = job['state']

        # Check finished jobs
        for job in finished_jobs:
            jobid = job['jobid']
            if jobid in self.state['jobs'] and not self.state['jobs'][jobid].get('notified', False):
                success, errors = self.check_job_success(jobid, job['name'])

                if success:
                    self.notify(f"Job {job['name']} ({jobid}) completed successfully", "SUCCESS")
                else:
                    self.notify(
                        f"Job {job['name']} ({jobid}) FAILED. Errors: {errors}", 
                        "FAILURE"
                    )

                    if self.auto_resubmit:
                        resubmits = self.state['jobs'][jobid].get('resubmits', 0)
                        if resubmits < self.max_resubmits:
                            new_jobid = self.resubmit_job(jobid, job['name'])
                            if new_jobid:
                                self.state['jobs'][jobid]['resubmits'] = resubmits + 1
                                self.state['jobs'][new_jobid] = {
                                    'name': job['name'],
                                    'state': 'Q',
                                    'submitted': datetime.now().isoformat(),
                                    'resubmits': resubmits + 1,
                                    'notified': False,
                                    'parent_job': jobid
                                }
                        else:
                            self.notify(
                                f"Job {job['name']} exceeded max resubmits ({self.max_resubmits})", 
                                "WARNING"
                            )

                self.state['jobs'][jobid]['notified'] = True
                self.state['jobs'][jobid]['final_state'] = job['state']

        # Clean up old finished jobs from state (keep for 7 days)
        cutoff = time.time() - 7 * 24 * 3600
        to_remove = []
        for jobid, info in self.state['jobs'].items():
            if info.get('notified') and 'submitted' in info:
                try:
                    submitted_time = datetime.fromisoformat(info['submitted']).timestamp()
                    if submitted_time < cutoff:
                        to_remove.append(jobid)
                except:
                    pass

        for jobid in to_remove:
            del self.state['jobs'][jobid]

        self.state['last_check'] = datetime.now().isoformat()
        self.save_state()
        self.notify(f"Monitor check complete. Running: {len(running_jobs)}, Checked finished: {len(finished_jobs)}")


def main():
    parser = argparse.ArgumentParser(description='MetaCentrum Job Monitor')
    parser.add_argument('--user', required=True, help='MetaCentrum username')
    parser.add_argument('--frontend', default='tarkil.metacentrum.cz', help='Frontend server')
    parser.add_argument('--ssh-key', help='SSH private key path')
    parser.add_argument('--notify', help='Notification command (e.g., "notify-send")')
    parser.add_argument('--auto-resubmit', action='store_true', help='Auto-resubmit failed jobs')
    parser.add_argument('--max-resubmits', type=int, default=2, help='Max resubmits per job')
    parser.add_argument('--daemon', action='store_true', help='Run continuously with sleep interval')
    parser.add_argument('--interval', type=int, default=300, help='Check interval in seconds (default 300)')

    args = parser.parse_args()

    monitor = MetaCentrumMonitor(
        username=args.user,
        frontend=args.frontend,
        ssh_key=args.ssh_key,
        notify_cmd=args.notify,
        auto_resubmit=args.auto_resubmit,
        max_resubmits=args.max_resubmits
    )

    if args.daemon:
        print(f"Running in daemon mode, checking every {args.interval} seconds...")
        while True:
            try:
                monitor.run()
            except Exception as e:
                print(f"Error in monitor loop: {e}")
            time.sleep(args.interval)
    else:
        monitor.run()


if __name__ == '__main__':
    main()
