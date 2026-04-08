#!/usr/bin/env python3
"""
v6 Evaluation: record videos, compute metrics, generate training curves.
Uses the final model + VecNormalize from the completed training.
"""
import os
import sys
import json
import time
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "rl"))
from dino_env import DinoQuadrupedEnv
from record_eval_video import record_video, random_policy, make_rl_policy, plot_training_curves

PROJECT_ROOT = os.path.dirname(__file__)
LOG_DIR = os.path.join(PROJECT_ROOT, "rl_logs")
MODEL_DIR = os.path.join(LOG_DIR, "models")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "eval_output")


def run_eval_episodes(policy_fn, n_episodes=10, max_steps=1000):
    """Run multiple evaluation episodes and collect stats."""
    results = []
    for ep in range(n_episodes):
        env = DinoQuadrupedEnv(max_episode_steps=max_steps)
        obs, _ = env.reset()
        total_reward = 0
        vx_list = []
        heights = []
        contacts_list = []

        for step in range(max_steps):
            action = policy_fn(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            vx_list.append(info.get("vx", obs[4]))
            heights.append(obs[0])
            contacts_list.append(info.get("n_contacts", np.sum(obs[36:40])))
            if terminated or truncated:
                break

        results.append({
            "episode": ep,
            "steps": step + 1,
            "total_reward": float(total_reward),
            "mean_vx": float(np.mean(vx_list)),
            "mean_height": float(np.mean(heights)),
            "mean_contacts": float(np.mean(contacts_list)),
            "terminated": bool(terminated),
        })
        env.close()
    return results


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  Dino Quadruped v6 — Full Evaluation")
    print("=" * 60)

    # 1. Training curves
    print("\n[1/4] Training curves...")
    log_path = os.path.join(LOG_DIR, "training_log.json")
    chart_path = os.path.join(OUTPUT_DIR, "training_curves_v6.png")
    plot_training_curves(log_path, chart_path)

    # 2. Load RL policy
    print("\n[2/4] Loading v6 model...")
    model_path = os.path.join(MODEL_DIR, "latest_model.zip")
    norm_path = os.path.join(MODEL_DIR, "latest_vecnormalize.pkl")

    if not os.path.exists(model_path):
        print("  ERROR: latest_model.zip not found!")
        return
    if not os.path.exists(norm_path):
        print("  ERROR: latest_vecnormalize.pkl not found!")
        return

    # Check model timestamp
    model_time = os.path.getmtime(model_path)
    norm_time = os.path.getmtime(norm_path)
    print(f"  Model: {time.ctime(model_time)}")
    print(f"  Norm:  {time.ctime(norm_time)}")

    rl_policy = make_rl_policy(model_path, norm_path)

    # 3. Quantitative eval (10 episodes)
    print("\n[3/4] Running 10 evaluation episodes...")

    print("  Baseline (neutral pose)...")
    baseline_results = run_eval_episodes(random_policy, n_episodes=5, max_steps=300)
    bl_steps = np.mean([r["steps"] for r in baseline_results])
    bl_vx = np.mean([r["mean_vx"] for r in baseline_results])
    bl_rew = np.mean([r["total_reward"] for r in baseline_results])
    print(f"    Steps: {bl_steps:.0f}, Vx: {bl_vx:.4f} m/s, Reward: {bl_rew:.1f}")

    print("  RL v6 policy...")
    rl_results = run_eval_episodes(rl_policy, n_episodes=10, max_steps=1000)
    rl_steps = np.mean([r["steps"] for r in rl_results])
    rl_vx = np.mean([r["mean_vx"] for r in rl_results])
    rl_rew = np.mean([r["total_reward"] for r in rl_results])
    rl_height = np.mean([r["mean_height"] for r in rl_results])
    rl_contacts = np.mean([r["mean_contacts"] for r in rl_results])
    rl_survived = sum(1 for r in rl_results if not r["terminated"])
    print(f"    Steps: {rl_steps:.0f}, Vx: {rl_vx:.4f} m/s, Reward: {rl_rew:.1f}")
    print(f"    Height: {rl_height:.3f}m, Contacts: {rl_contacts:.1f}, Survived: {rl_survived}/10")

    # 4. Record videos
    print("\n[4/4] Recording videos...")

    print("  Baseline video...")
    env_bl = DinoQuadrupedEnv(render_mode="rgb_array", max_episode_steps=300)
    bl_vid = record_video(env_bl, random_policy,
                          os.path.join(OUTPUT_DIR, "baseline_v6.mp4"), max_steps=300)
    env_bl.close()

    print("  RL v6 policy video...")
    env_rl = DinoQuadrupedEnv(render_mode="rgb_array", max_episode_steps=1000)
    rl_vid = record_video(env_rl, rl_policy,
                          os.path.join(OUTPUT_DIR, "rl_v6_policy.mp4"), max_steps=1000)
    env_rl.close()

    # Summary
    print("\n" + "=" * 60)
    print("  v6 Evaluation Summary")
    print("=" * 60)
    print(f"  {'Metric':<25} {'Baseline':>12} {'RL v6':>12}")
    print(f"  {'-'*25} {'-'*12} {'-'*12}")
    print(f"  {'Steps survived':<25} {bl_steps:>12.0f} {rl_steps:>12.0f}")
    print(f"  {'Mean reward':<25} {bl_rew:>12.1f} {rl_rew:>12.1f}")
    print(f"  {'Mean Vx (m/s)':<25} {bl_vx:>12.4f} {rl_vx:>12.4f}")
    print(f"  {'Distance (m) [video]':<25} {bl_vid['distance_m']:>12.3f} {rl_vid['distance_m']:>12.3f}")
    print(f"  {'Survived full ep':<25} {'N/A':>12} {rl_survived:>9}/10")

    # Save full results
    summary = {
        "version": "v6",
        "training_steps": "2M",
        "baseline": {
            "mean_steps": float(bl_steps),
            "mean_reward": float(bl_rew),
            "mean_vx": float(bl_vx),
            "video_stats": bl_vid,
        },
        "rl_v6": {
            "mean_steps": float(rl_steps),
            "mean_reward": float(rl_rew),
            "mean_vx": float(rl_vx),
            "mean_height": float(rl_height),
            "mean_contacts": float(rl_contacts),
            "survived_full": rl_survived,
            "episodes": rl_results,
            "video_stats": rl_vid,
        }
    }
    with open(os.path.join(OUTPUT_DIR, "eval_v6_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Output files:")
    print(f"    {OUTPUT_DIR}/training_curves_v6.png")
    print(f"    {OUTPUT_DIR}/baseline_v6.mp4")
    print(f"    {OUTPUT_DIR}/rl_v6_policy.mp4")
    print(f"    {OUTPUT_DIR}/eval_v6_summary.json")
    print("  DONE!")


if __name__ == "__main__":
    main()
