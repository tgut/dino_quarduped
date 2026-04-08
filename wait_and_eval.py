#!/usr/bin/env python3
"""Wait for training to finish, then run evaluation."""
import subprocess
import time
import os

def is_training_running():
    result = subprocess.run(["pgrep", "-f", "train_ppo"], capture_output=True, text=True)
    return len(result.stdout.strip()) > 0

print("Waiting for v6 training to complete...")
while is_training_running():
    time.sleep(30)
    # Check progress
    try:
        import json
        log_path = "/mnt/data/tgut/code/dino_quadruped/rl_logs/training_log.json"
        with open(log_path) as f:
            data = json.load(f)
        if data:
            last = data[-1]
            pct = last["timesteps"] / 2000000 * 100
            print(f"  {last['timesteps']/1000:.0f}K / 2000K ({pct:.0f}%) "
                  f"reward={last['mean_reward']:.0f} ep_len={last['mean_length']:.0f} "
                  f"vx={last['mean_vx']:.3f}")
    except Exception:
        pass

print("\nTraining complete! Starting evaluation...")
time.sleep(2)  # Let files flush

os.chdir("/mnt/data/tgut/code/dino_quadruped")
os.execvp("python3", ["python3", "eval_v6.py"])
