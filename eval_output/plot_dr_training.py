#!/usr/bin/env python3
"""Generate training visualization charts for DR training run."""
import json, os, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

LOG = os.path.join(os.path.dirname(__file__), '..', 'rl_logs', 'training_log.json')
OUT = os.path.dirname(__file__)

with open(LOG) as f:
    data = json.load(f)

ts   = np.array([d['timesteps'] / 1e6 for d in data])
rews = np.array([d['mean_reward'] for d in data])
lens = np.array([d['mean_length'] for d in data])
vxs  = np.array([d['mean_vx'] for d in data])
maxr = np.array([d['max_reward'] for d in data])

def smooth(y, w=15):
    if len(y) < w: return y
    return np.convolve(y, np.ones(w)/w, mode='valid')

ts_s = ts[len(ts)-len(smooth(rews)):]
DR_WARMUP = 1.5

# --- Figure 1: 4-panel training curves ---
fig, axes = plt.subplots(2, 2, figsize=(16, 11))
fig.suptitle('Dino Quadruped - DR Training (5M steps, PPO)', fontsize=18, fontweight='bold', y=0.98)

for ax in axes.flat:
    ax.axvspan(0, DR_WARMUP, alpha=0.08, color='orange')
    ax.axvline(DR_WARMUP, color='orange', linestyle='--', alpha=0.6, linewidth=1)

ax = axes[0, 0]
ax.plot(ts, rews, alpha=0.2, color='#2196F3', linewidth=0.5)
ax.plot(ts_s, smooth(rews), color='#1565C0', linewidth=2.5, label='Mean Reward (smoothed)')
ax.set_ylabel('Reward', fontsize=12)
ax.set_title('Mean Episode Reward', fontsize=14, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)

ax = axes[0, 1]
ax.plot(ts, lens, alpha=0.2, color='#4CAF50', linewidth=0.5)
ax.plot(ts_s, smooth(lens), color='#2E7D32', linewidth=2.5, label='Mean Length (smoothed)')
ax.axhline(2000, color='red', linestyle=':', alpha=0.5, label='Episode limit (2000)')
ax.set_ylabel('Steps', fontsize=12)
ax.set_title('Mean Episode Length', fontsize=14, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)

ax = axes[1, 0]
ax.plot(ts, vxs, alpha=0.2, color='#FF9800', linewidth=0.5)
ax.plot(ts_s, smooth(vxs), color='#E65100', linewidth=2.5, label='Mean Vx (smoothed)')
ax.axhline(0.031, color='gray', linestyle='--', alpha=0.7, label='Hand-tuned baseline (0.031)')
ax.axhline(0, color='black', linestyle='-', alpha=0.2)
ax.set_xlabel('Timesteps (M)', fontsize=12)
ax.set_ylabel('Speed (m/s)', fontsize=12)
ax.set_title('Mean Forward Speed (Vx)', fontsize=14, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)

ax = axes[1, 1]
ax.plot(ts, maxr, alpha=0.2, color='#9C27B0', linewidth=0.5)
ax.plot(ts_s, smooth(maxr), color='#6A1B9A', linewidth=2.5, label='Max Reward (smoothed)')
ax.set_xlabel('Timesteps (M)', fontsize=12)
ax.set_ylabel('Reward', fontsize=12)
ax.set_title('Max Episode Reward', fontsize=14, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.95])
path1 = os.path.join(OUT, 'training_curves_dr.png')
plt.savefig(path1, dpi=150, bbox_inches='tight')
plt.close()
print('Saved:', path1)

# --- Figure 2: DR Strength + Reward ---
fig, ax1 = plt.subplots(figsize=(14, 6))
fig.suptitle('Domain Randomization Schedule vs Reward', fontsize=16, fontweight='bold')

dr_strength = np.minimum(1.0, ts / DR_WARMUP)
ax1.fill_between(ts, dr_strength, alpha=0.15, color='orange')
ax1.plot(ts, dr_strength, 'orange', linewidth=2, label='DR Strength')
ax1.set_ylabel('DR Strength', fontsize=13, color='darkorange')
ax1.set_ylim(-0.05, 1.15)
ax1.tick_params(axis='y', labelcolor='darkorange')
ax1.set_xlabel('Timesteps (M)', fontsize=13)

ax2 = ax1.twinx()
ax2.plot(ts, rews, alpha=0.15, color='#2196F3', linewidth=0.5)
ax2.plot(ts_s, smooth(rews), color='#1565C0', linewidth=2.5, label='Mean Reward')
ax2.set_ylabel('Mean Reward', fontsize=13, color='#1565C0')
ax2.tick_params(axis='y', labelcolor='#1565C0')

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1+lines2, labels1+labels2, loc='upper left', fontsize=11)
ax1.grid(True, alpha=0.3)

path2 = os.path.join(OUT, 'dr_schedule_vs_reward.png')
plt.savefig(path2, dpi=150, bbox_inches='tight')
plt.close()
print('Saved:', path2)

# --- Figure 3: Summary card ---
fig, ax = plt.subplots(figsize=(10, 6))
ax.axis('off')

last50_mean = np.mean(rews[-50:])
last50_std = np.std(rews[-50:])
cv_pct = last50_std / last50_mean * 100

labels = [
    'Total Steps', 'Final Mean Reward', 'Peak Mean Reward',
    'Best Single Episode', 'Final Avg Length', 'Final Avg Speed',
    'Reward Growth', 'Convergence (last 500K)', 'DR Warmup'
]
values = [
    '{:,}'.format(data[-1]['timesteps']),
    '{:.0f}'.format(rews[-1]),
    '{:.0f} @ {:.1f}M'.format(rews.max(), ts[rews.argmax()]),
    '{:.0f}'.format(maxr.max()),
    '{:.0f} / 2000'.format(lens[-1]),
    '{:.3f} m/s'.format(vxs[-1]),
    '{:.0f}x ({:.0f} -> {:.0f})'.format(rews[-1]/rews[0], rews[0], rews[-1]),
    '{:.0f} +/- {:.0f} (CV={:.1f}%)'.format(last50_mean, last50_std, cv_pct),
    '0 -> 100% over first 1.5M steps'
]

y_start = 0.92
for i in range(len(labels)):
    y = y_start - i * 0.095
    ax.text(0.05, y, labels[i] + ':', fontsize=13, fontweight='bold',
            transform=ax.transAxes, va='top')
    ax.text(0.45, y, values[i], fontsize=13, transform=ax.transAxes,
            va='top', color='#1565C0')

ax.set_title('Training Summary - DR PPO (5M steps)', fontsize=16, fontweight='bold', pad=20)
path3 = os.path.join(OUT, 'training_summary.png')
plt.savefig(path3, dpi=150, bbox_inches='tight')
plt.close()
print('Saved:', path3)
print('All charts done!')
