#!/usr/bin/env python3
"""
Record animated GIF of RL policy with speed overlay + v6 vs v7 comparison chart.
Outputs:
  - eval_output/v7_5M_walk.gif       (RL policy animation)
  - eval_output/v7_speed_analysis.png (speed comparison chart)
"""

import os, sys, json, pickle
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rl"))
from dino_env import DinoQuadrupedEnv

import pybullet as p
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
MODEL_DIR = os.path.join(PROJECT_ROOT, "rl_logs", "models")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "eval_output")


def make_rl_policy(model_path, norm_path):
    from stable_baselines3 import PPO
    model = PPO.load(model_path)
    with open(norm_path, "rb") as f:
        vn = pickle.load(f)
    obs_rms = vn.obs_rms
    clip_obs = vn.clip_obs
    epsilon = vn.epsilon

    def policy(obs):
        obs_norm = np.clip(
            (obs - obs_rms.mean) / np.sqrt(obs_rms.var + epsilon),
            -clip_obs, clip_obs
        ).astype(np.float32)
        action, _ = model.predict(obs_norm.reshape(1, -1), deterministic=True)
        return action[0]
    return policy


def render_frame(env, width=800, height=600):
    """Render a frame with camera tracking."""
    client = env._physics_client
    pos, orn = p.getBasePositionAndOrientation(env._robot, physicsClientId=client)

    view = p.computeViewMatrixFromYawPitchRoll(
        cameraTargetPosition=[pos[0], pos[1], 0.12],
        distance=0.65, yaw=40, pitch=-25, roll=0,
        upAxisIndex=2, physicsClientId=client,
    )
    proj = p.computeProjectionMatrixFOV(
        fov=50, aspect=width / height,
        nearVal=0.01, farVal=10.0, physicsClientId=client,
    )
    _, _, img, _, _ = p.getCameraImage(
        width=width, height=height,
        viewMatrix=view, projectionMatrix=proj,
        lightDirection=[1.0, 0.5, 1.5],
        lightColor=[1.0, 0.95, 0.85],
        physicsClientId=client,
    )
    return np.array(img, dtype=np.uint8).reshape(height, width, 4)[:, :, :3]


def add_overlay(frame, step, vx, total_dist, height_m, num_contacts):
    """Add HUD overlay with metrics."""
    img = Image.fromarray(frame)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except (IOError, OSError):
        font = ImageFont.load_default()
        font_sm = font

    # Background box
    draw.rectangle([(10, 10), (320, 130)], fill=(0, 0, 0, 160))

    lines = [
        f"Dino Quadruped v7  |  5M steps",
        f"Step: {step:4d}  |  Vx: {vx:+.3f} m/s",
        f"Distance: {total_dist:.3f} m",
        f"Height: {height_m:.3f} m  |  Contacts: {num_contacts}",
    ]
    y = 18
    for i, line in enumerate(lines):
        color = (100, 255, 100) if i == 0 else (220, 220, 220)
        f = font if i == 0 else font_sm
        draw.text((20, y), line, fill=color, font=f)
        y += 26

    return np.array(img)


def record_gif():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading v7 5M model...")
    model_path = os.path.join(MODEL_DIR, "latest_model.zip")
    norm_path = os.path.join(MODEL_DIR, "latest_vecnormalize.pkl")
    policy = make_rl_policy(model_path, norm_path)

    print("Setting up environment...")
    env = DinoQuadrupedEnv(render_mode="rgb_array", max_episode_steps=2000)
    obs, _ = env.reset()
    client = env._physics_client

    frames = []
    positions = []
    velocities = []
    max_steps = 1500  # ~12.5s at 120Hz
    total_reward = 0

    print("Recording frames...")
    for step in range(max_steps):
        action = policy(obs)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward

        pos, orn = p.getBasePositionAndOrientation(env._robot, physicsClientId=client)
        vel, _ = p.getBaseVelocity(env._robot, physicsClientId=client)
        positions.append(pos)
        velocities.append(vel[0])  # linear velocity x

        # Capture every 4 steps → ~30 fps in GIF (120Hz / 4 = 30)
        if step % 4 == 0:
            frame = render_frame(env)

            dist = np.sqrt((pos[0] - positions[0][0])**2 + (pos[1] - positions[0][1])**2)
            # Contacts
            contacts = p.getContactPoints(bodyA=env._robot, physicsClientId=client)
            foot_indices = set()
            for name in env.FOOT_LINK_NAMES:
                idx = env._link_name_to_idx.get(name)
                if idx is not None:
                    foot_indices.add(idx)
            num_contacts = sum(1 for c in contacts if c[3] in foot_indices)

            frame = add_overlay(frame, step, vel[0], dist, pos[2], num_contacts)
            frames.append(frame)

        if terminated or truncated:
            print(f"  Episode ended at step {step}: terminated={terminated}")
            break

    env.close()

    # Compute stats
    final_dist = np.sqrt((positions[-1][0] - positions[0][0])**2 +
                         (positions[-1][1] - positions[0][1])**2)
    avg_vx = np.mean([v for v in velocities])
    max_vx = np.max([v for v in velocities])
    time_s = len(positions) * env.control_dt

    print(f"\n  Steps: {len(positions)}")
    print(f"  Distance: {final_dist:.3f} m")
    print(f"  Avg Vx: {avg_vx:.4f} m/s")
    print(f"  Max Vx: {max_vx:.4f} m/s")
    print(f"  Time: {time_s:.1f} s")
    print(f"  Total Reward: {total_reward:.1f}")

    # Save GIF
    gif_path = os.path.join(OUTPUT_DIR, "v7_5M_walk.gif")
    print(f"\nSaving GIF ({len(frames)} frames)...")
    pil_frames = [Image.fromarray(f) for f in frames]
    pil_frames[0].save(
        gif_path,
        save_all=True,
        append_images=pil_frames[1:],
        duration=33,  # ~30fps
        loop=0,
    )
    print(f"  Saved: {gif_path}")

    # Also save as MP4 for better quality
    try:
        import imageio
        mp4_path = os.path.join(OUTPUT_DIR, "v7_5M_walk.mp4")
        imageio.mimsave(mp4_path, frames, fps=30)
        print(f"  Saved: {mp4_path}")
    except ImportError:
        pass

    # ── Speed comparison chart ──
    print("\nGenerating speed analysis chart...")
    generate_speed_chart(velocities, env.control_dt)

    return {
        "gif_path": gif_path,
        "steps": len(positions),
        "distance_m": final_dist,
        "avg_vx": avg_vx,
        "max_vx": max_vx,
        "total_reward": total_reward,
    }


def generate_speed_chart(velocities, control_dt):
    """Generate v6 vs v7 speed comparison chart."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    time_axis = np.arange(len(velocities)) * control_dt

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle("Dino Quadruped — Speed Analysis: v7 (5M steps) vs v6 Benchmark",
                 fontsize=15, fontweight="bold")

    # Left: instantaneous velocity over time
    ax = axes[0]
    window = 50
    vx_smooth = np.convolve(velocities, np.ones(window)/window, mode='valid')
    t_smooth = np.arange(len(vx_smooth)) * control_dt

    ax.plot(time_axis, velocities, alpha=0.2, color='blue', linewidth=0.5, label='Raw Vx')
    ax.plot(t_smooth, vx_smooth, color='blue', linewidth=2, label=f'Smoothed (w={window})')
    ax.axhline(y=0.23, color='green', linestyle='--', linewidth=2, label='v6 avg (0.23 m/s)')
    ax.axhline(y=0.20, color='orange', linestyle='--', linewidth=1.5, label='v7 target (0.20 m/s)')
    ax.axhline(y=0.031, color='red', linestyle=':', linewidth=1, label='Hand-tuned (0.031)')
    ax.set_xlabel("Time (s)", fontsize=12)
    ax.set_ylabel("Forward Velocity Vx (m/s)", fontsize=12)
    ax.set_title("Instantaneous Forward Speed", fontsize=13)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(-0.1, 0.4)

    # Right: speed distribution histogram
    ax = axes[1]
    ax.hist(velocities, bins=60, alpha=0.7, color='steelblue', edgecolor='navy',
            density=True, label='v7 (5M)')
    ax.axvline(x=np.mean(velocities), color='blue', linewidth=2,
               label=f'v7 mean: {np.mean(velocities):.3f} m/s')
    ax.axvline(x=0.23, color='green', linewidth=2, linestyle='--',
               label='v6 mean: 0.230 m/s')
    ax.set_xlabel("Forward Velocity (m/s)", fontsize=12)
    ax.set_ylabel("Density", fontsize=12)
    ax.set_title("Speed Distribution", fontsize=13)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    chart_path = os.path.join(OUTPUT_DIR, "v7_speed_analysis.png")
    plt.savefig(chart_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {chart_path}")


if __name__ == "__main__":
    stats = record_gif()
    print("\n" + "=" * 50)
    print(f"  GIF: {stats['gif_path']}")
    print(f"  Avg Speed: {stats['avg_vx']:.4f} m/s")
    print(f"  Distance:  {stats['distance_m']:.3f} m")
    print("=" * 50)
