#!/usr/bin/env python3
"""Kill training, backup log, clear for next version."""
import subprocess, os, signal, json, shutil

# Kill all train_ppo processes
result = subprocess.run(["pgrep", "-f", "train_ppo"], capture_output=True, text=True)
for pid in result.stdout.strip().split("\n"):
    pid = pid.strip()
    if pid:
        try:
            os.kill(int(pid), signal.SIGTERM)
            print("Killed PID " + pid)
        except Exception as e:
            print("Skip " + pid + ": " + str(e))

# Backup current log
src = "/mnt/data/tgut/code/dino_quadruped/rl_logs/training_log.json"
dst = "/mnt/data/tgut/code/dino_quadruped/rl_logs/training_log_v5_backup.json"
if os.path.exists(src):
    shutil.copy2(src, dst)
    print("v5 log backed up")

    # Clear log
    with open(src, "w") as f:
        json.dump([], f)
    print("Log cleared for v6")
