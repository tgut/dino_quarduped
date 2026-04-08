#!/usr/bin/env python3
"""
Record evaluation videos and generate training comparison chart.

Usage:
    python3 rl/record_eval_video.py
"""

import os
import sys
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from dino_env import DinoQuadrupedEnv

import pybullet as p

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
LOG_DIR = os.path.join(PROJECT_ROOT, "rl_logs")
MODEL_DIR = os.path.join(LOG_DIR, "models")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "eval_output")


def record_video(env, policy_fn, filename, max_steps=1000, width=640, height=480):
    """Record a video of the policy running in the environment."""
    try:
        import imageio
    except ImportError:
        os.system("pip install imageio[ffmpeg] -q")
        import imageio

    frames = []
    obs, _ = env.reset()

    # Get PyBullet client for rendering
    client = env._physics_client

    # Set up camera
    p.resetDebugVisualizerCamera(
        cameraDistance=0.8,
        cameraYaw=45,
        cameraPitch=-30,
        cameraTargetPosition=[0, 0, 0.15],
        physicsClientId=client,
    )

    total_reward = 0
    positions = []

    for step in range(max_steps):
        action = policy_fn(obs)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward

        # Get robot position for camera tracking
        pos, _ = p.getBasePositionAndOrientation(env._robot, physicsClientId=client)
        positions.append(pos)

        # Render frame (every 2 steps to keep video size manageable)
        if step % 2 == 0:
            # Update camera to follow robot
            p.resetDebugVisualizerCamera(
                cameraDistance=0.8,
                cameraYaw=45,
                cameraPitch=-30,
                cameraTargetPosition=[pos[0], pos[1], 0.15],
                physicsClientId=client,
            )

            _, _, img, _, _ = p.getCameraImage(
                width=width, height=height,
                viewMatrix=p.computeViewMatrixFromYawPitchRoll(
                    cameraTargetPosition=[pos[0], pos[1], 0.15],
                    distance=0.8,
                    yaw=45,
                    pitch=-30,
                    roll=0,
                    upAxisIndex=2,
                    physicsClientId=client,
                ),
                projectionMatrix=p.computeProjectionMatrixFOV(
                    fov=60, aspect=width/height,
                    nearVal=0.1, farVal=10.0,
                    physicsClientId=client,
                ),
                physicsClientId=client,
            )
            frame = np.reshape(img, (height, width, 4))[:, :, :3]
            frames.append(frame)

        if terminated or truncated:
            break

    # Save video
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    imageio.mimsave(filename, frames, fps=30)

    distance = np.sqrt((positions[-1][0] - positions[0][0])**2 +
                       (positions[-1][1] - positions[0][1])**2) if positions else 0

    return {
        "total_reward": total_reward,
        "steps": step + 1,
        "distance_m": float(distance),
        "avg_speed_m_per_s": float(distance / ((step + 1) * env.control_dt)) if step > 0 else 0,
    }


def random_policy(obs):
    """Random action baseline."""
    return np.zeros(12, dtype=np.float32)  # Stand still (neutral pose)


def make_rl_policy(model_path, norm_path):
    """Create RL policy function."""
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import VecNormalize as VN
    import pickle

    model = PPO.load(model_path)

    # Load normalization stats
    with open(norm_path, "rb") as f:
        vn = pickle.load(f)
    obs_rms = vn.obs_rms
    clip_obs = vn.clip_obs
    epsilon = vn.epsilon

    def policy(obs):
        # Normalize obs the same way VecNormalize does
        obs_norm = np.clip(
            (obs - obs_rms.mean) / np.sqrt(obs_rms.var + epsilon),
            -clip_obs, clip_obs
        ).astype(np.float32)
        action, _ = model.predict(obs_norm.reshape(1, -1), deterministic=True)
        return action[0]

    return policy


def plot_training_curves(log_path, output_path):
    """Generate training progress comparison chart."""
    with open(log_path) as f:
        data = json.load(f)

    timesteps = [d["timesteps"] / 1000 for d in data]
    rewards = [d["mean_reward"] for d in data]
    lengths = [d["mean_length"] for d in data]
    speeds = [d["mean_vx"] for d in data]
    max_rewards = [d["max_reward"] for d in data]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Dino Quadruped RL Training Progress", fontsize=16, fontweight="bold")

    # Mean Reward
    ax = axes[0, 0]
    ax.plot(timesteps, rewards, "b-", linewidth=2, label="Mean Reward")
    ax.fill_between(timesteps, rewards, alpha=0.1, color="blue")
    ax.axhline(y=0, color="red", linestyle="--", alpha=0.5, label="Zero baseline")
    ax.set_xlabel("Timesteps (K)")
    ax.set_ylabel("Mean Reward")
    ax.set_title("Mean Episode Reward")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Episode Length
    ax = axes[0, 1]
    ax.plot(timesteps, lengths, "g-", linewidth=2, label="Mean Length")
    ax.axhline(y=1000, color="red", linestyle="--", alpha=0.5, label="Max (1000)")
    ax.set_xlabel("Timesteps (K)")
    ax.set_ylabel("Steps")
    ax.set_title("Mean Episode Length")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Forward Speed
    ax = axes[1, 0]
    ax.plot(timesteps, speeds, "orange", linewidth=2, label="RL Policy")
    ax.axhline(y=0.031, color="red", linestyle="--", alpha=0.5, label="Hand-tuned (0.031 m/s)")
    ax.set_xlabel("Timesteps (K)")
    ax.set_ylabel("Speed (m/s)")
    ax.set_title("Mean Forward Speed (Vx)")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Max Reward
    ax = axes[1, 1]
    ax.plot(timesteps, max_rewards, "purple", linewidth=2, label="Max Reward")
    ax.set_xlabel("Timesteps (K)")
    ax.set_ylabel("Reward")
    ax.set_title("Max Episode Reward")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Training curves saved to {output_path}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  Dino Quadruped — Evaluation & Video Recording")
    print("=" * 60)

    # 1. Plot training curves
    print("\n[1/3] Generating training progress chart...")
    log_path = os.path.join(LOG_DIR, "training_log.json")
    chart_path = os.path.join(OUTPUT_DIR, "training_curves.png")
    plot_training_curves(log_path, chart_path)

    # 2. Record baseline video (neutral standing / random)
    print("\n[2/3] Recording baseline video (neutral pose)...")
    env_baseline = DinoQuadrupedEnv(render_mode="rgb_array", max_episode_steps=300)
    baseline_stats = record_video(
        env_baseline, random_policy,
        os.path.join(OUTPUT_DIR, "baseline_neutral.mp4"),
        max_steps=300,
    )
    env_baseline.close()
    print(f"  Baseline: {baseline_stats['steps']} steps, "
          f"distance={baseline_stats['distance_m']:.3f}m, "
          f"speed={baseline_stats['avg_speed_m_per_s']:.4f} m/s")

    # 3. Record RL policy video
    print("\n[3/3] Recording RL policy video...")
    env_rl = DinoQuadrupedEnv(render_mode="rgb_array", max_episode_steps=1000)

    model_path = os.path.join(MODEL_DIR, "latest_model.zip")
    norm_path = os.path.join(MODEL_DIR, "latest_vecnormalize.pkl")
    rl_policy = make_rl_policy(model_path, norm_path)

    rl_stats = record_video(
        env_rl, rl_policy,
        os.path.join(OUTPUT_DIR, "rl_policy_latest.mp4"),
        max_steps=1000,
    )
    env_rl.close()
    print(f"  RL Policy: {rl_stats['steps']} steps, "
          f"distance={rl_stats['distance_m']:.3f}m, "
          f"speed={rl_stats['avg_speed_m_per_s']:.4f} m/s")

    # Summary comparison
    print("\n" + "=" * 60)
    print("  Comparison Summary")
    print("=" * 60)
    print(f"  {'Metric':<25} {'Baseline':>12} {'RL (500K)':>12} {'Improvement':>12}")
    print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*12}")
    print(f"  {'Steps survived':<25} {baseline_stats['steps']:>12} {rl_stats['steps']:>12} "
          f"{rl_stats['steps']/max(baseline_stats['steps'],1):.1f}x")
    print(f"  {'Distance (m)':<25} {baseline_stats['distance_m']:>12.3f} {rl_stats['distance_m']:>12.3f} "
          f"{rl_stats['distance_m']/max(baseline_stats['distance_m'],0.001):.1f}x")
    print(f"  {'Speed (m/s)':<25} {baseline_stats['avg_speed_m_per_s']:>12.4f} {rl_stats['avg_speed_m_per_s']:>12.4f} "
          f"{rl_stats['avg_speed_m_per_s']/max(baseline_stats['avg_speed_m_per_s'],0.0001):.1f}x")

    # Save summary
    summary = {
        "baseline": baseline_stats,
        "rl_policy_latest": rl_stats,
    }
    with open(os.path.join(OUTPUT_DIR, "eval_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Output files in: {OUTPUT_DIR}/")
    print(f"    - training_curves.png")
    print(f"    - baseline_neutral.mp4")
    print(f"    - rl_policy_latest.mp4")
    print(f"    - eval_summary.json")


if __name__ == "__main__":
    main()
