#!/usr/bin/env python3
"""Generate training curve comparison chart."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
LOG_DIR = os.path.join(PROJECT_ROOT, "rl_logs")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "logs")

# Load training log
with open(os.path.join(LOG_DIR, "training_log.json")) as f:
    log = json.load(f)

steps = [e['timesteps'] for e in log]
rewards = [e['mean_reward'] for e in log]
lengths = [e['mean_length'] for e in log]
vx = [e['mean_vx'] for e in log]
max_rewards = [e['max_reward'] for e in log]

# Load eval results
with open(os.path.join(LOG_DIR, "eval_results.json")) as f:
    eval_res = json.load(f)

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('Dino Quadruped RL Training - 500K Steps PPO', fontsize=16, fontweight='bold')

# 1. Mean Reward
ax = axes[0, 0]
ax.plot(np.array(steps)/1000, rewards, 'b-', linewidth=2, label='Mean Reward')
ax.fill_between(np.array(steps)/1000, rewards, alpha=0.15, color='blue')
ax.axhline(y=0, color='red', linestyle='--', alpha=0.5, label='Zero line')
ax.axhline(y=eval_res['rl_policy']['mean_reward'], color='green', linestyle='--',
           alpha=0.7, label='Eval: {:.0f}'.format(eval_res['rl_policy']['mean_reward']))
ax.set_xlabel('Timesteps (K)')
ax.set_ylabel('Mean Reward')
ax.set_title('Training Reward Curve')
ax.legend()
ax.grid(True, alpha=0.3)

# 2. Episode Length
ax = axes[0, 1]
ax.plot(np.array(steps)/1000, lengths, 'g-', linewidth=2)
ax.axhline(y=1000, color='red', linestyle='--', alpha=0.5, label='Max (1000)')
ax.axhline(y=eval_res['rl_policy']['mean_length'], color='orange', linestyle='--',
           alpha=0.7, label='Eval: {:.0f}'.format(eval_res['rl_policy']['mean_length']))
ax.set_xlabel('Timesteps (K)')
ax.set_ylabel('Mean Episode Length')
ax.set_title('Survival Duration')
ax.legend()
ax.grid(True, alpha=0.3)

# 3. Forward Speed
ax = axes[1, 0]
ax.plot(np.array(steps)/1000, vx, 'r-', linewidth=2, label='RL Policy')
ax.axhline(y=0.031, color='blue', linestyle='--', alpha=0.7, linewidth=2,
           label='Hand-tuned: 0.031 m/s')
ax.axhline(y=eval_res['rl_policy']['mean_speed_m_per_s'], color='green', linestyle='--',
           alpha=0.7, label='Eval: {:.3f} m/s'.format(eval_res['rl_policy']['mean_speed_m_per_s']))
ax.set_xlabel('Timesteps (K)')
ax.set_ylabel('Vx (m/s)')
ax.set_title('Forward Speed (RL vs Hand-tuned)')
ax.legend()
ax.grid(True, alpha=0.3)

# 4. Eval Comparison Bar Chart
ax = axes[1, 1]
categories = ['Speed (m/s)', 'Ep Length / 1K', 'Reward / 1K']
rl_vals = [
    eval_res['rl_policy']['mean_speed_m_per_s'],
    eval_res['rl_policy']['mean_length'] / 1000,
    eval_res['rl_policy']['mean_reward'] / 1000,
]
ht_vals = [0.031, 0.029, 0.0]

x = np.arange(len(categories))
width = 0.35
bars1 = ax.bar(x - width/2, rl_vals, width, label='RL Policy (best)', color='#2196F3')
bars2 = ax.bar(x + width/2, ht_vals, width, label='Hand-tuned Baseline', color='#FF9800')
ax.set_ylabel('Normalized Value')
ax.set_title('RL vs Hand-Tuned Comparison')
ax.set_xticks(x)
ax.set_xticklabels(categories)
ax.legend()
ax.grid(True, alpha=0.3, axis='y')

for bar in bars1:
    h = bar.get_height()
    ax.annotate('{:.3f}'.format(h), xy=(bar.get_x() + bar.get_width()/2, h),
                xytext=(0, 3), textcoords='offset points', ha='center', fontsize=9)
for bar in bars2:
    h = bar.get_height()
    ax.annotate('{:.3f}'.format(h), xy=(bar.get_x() + bar.get_width()/2, h),
                xytext=(0, 3), textcoords='offset points', ha='center', fontsize=9)

plt.tight_layout()
os.makedirs(OUTPUT_DIR, exist_ok=True)
out_path = os.path.join(OUTPUT_DIR, "training_comparison.png")
plt.savefig(out_path, dpi=150)
print('Chart saved:', out_path)
