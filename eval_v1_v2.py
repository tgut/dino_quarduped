#!/usr/bin/env python3
"""
Evaluate and record videos for both v1 and v2 RL policies.
v1 model has obs_dim=40, v2 has obs_dim=41.
"""
import os, sys, json, pickle, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "rl"))
import pybullet as p

PROJECT_ROOT = os.path.dirname(__file__)
LOG_DIR = os.path.join(PROJECT_ROOT, "rl_logs")
MODEL_DIR = os.path.join(LOG_DIR, "models")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "eval_output")


def record_video(env, policy_fn, filename, max_steps=500, width=640, height=480):
    """Record video of policy."""
    import imageio
    frames = []
    obs, _ = env.reset()
    client = env._physics_client
    total_reward = 0
    positions = []

    for step in range(max_steps):
        action = policy_fn(obs)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        pos, _ = p.getBasePositionAndOrientation(env._robot, physicsClientId=client)
        positions.append(pos)

        if step % 2 == 0:
            _, _, img, _, _ = p.getCameraImage(
                width=width, height=height,
                viewMatrix=p.computeViewMatrixFromYawPitchRoll(
                    cameraTargetPosition=[pos[0], pos[1], 0.15],
                    distance=0.8, yaw=45, pitch=-30, roll=0,
                    upAxisIndex=2, physicsClientId=client),
                projectionMatrix=p.computeProjectionMatrixFOV(
                    fov=60, aspect=width/height, nearVal=0.1, farVal=10.0,
                    physicsClientId=client),
                physicsClientId=client)
            frame = np.reshape(img, (height, width, 4))[:, :, :3]
            frames.append(frame)

        if terminated or truncated:
            break

    os.makedirs(os.path.dirname(filename), exist_ok=True)
    imageio.mimsave(filename, frames, fps=30)
    dist = np.sqrt((positions[-1][0]-positions[0][0])**2 +
                   (positions[-1][1]-positions[0][1])**2) if positions else 0
    return {
        "total_reward": float(total_reward),
        "steps": step + 1,
        "distance_m": float(dist),
        "speed_m_s": float(dist / ((step+1) * env.control_dt)) if step > 0 else 0,
        "height_final": float(positions[-1][2]) if positions else 0,
    }


def make_rl_policy_v1(model_path, norm_path):
    """Load v1 model (obs_dim=40)."""
    from stable_baselines3 import PPO
    model = PPO.load(model_path)
    with open(norm_path, "rb") as f:
        vn = pickle.load(f)
    obs_rms = vn.obs_rms
    clip_obs = vn.clip_obs
    epsilon = vn.epsilon

    def policy(obs):
        # v1 expects 40-dim obs, v2 env gives 41-dim — trim last element
        obs_v1 = obs[:40] if len(obs) > 40 else obs
        obs_norm = np.clip(
            (obs_v1 - obs_rms.mean) / np.sqrt(obs_rms.var + epsilon),
            -clip_obs, clip_obs
        ).astype(np.float32)
        action, _ = model.predict(obs_norm.reshape(1, -1), deterministic=True)
        return action[0]
    return policy


def neutral_policy(obs):
    return np.zeros(12, dtype=np.float32)


def main():
    from dino_env import DinoQuadrupedEnv
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = {}

    # 1. Baseline (neutral pose)
    print("[1/3] Recording baseline (neutral stand)...")
    env = DinoQuadrupedEnv(render_mode="rgb_array", max_episode_steps=500)
    r = record_video(env, neutral_policy,
                     os.path.join(OUTPUT_DIR, "baseline_neutral.mp4"), max_steps=500)
    env.close()
    results["baseline"] = r
    print(f"  Baseline: {r['steps']} steps, dist={r['distance_m']:.3f}m, speed={r['speed_m_s']:.4f} m/s")

    # 2. v1 RL policy (latest_model from Apr 7)
    print("\n[2/3] Recording v1 RL policy (1M steps, from Apr 7)...")
    v1_model = os.path.join(MODEL_DIR, "latest_model.zip")
    v1_norm = os.path.join(MODEL_DIR, "latest_vecnormalize.pkl")
    if os.path.exists(v1_model) and os.path.exists(v1_norm):
        env = DinoQuadrupedEnv(render_mode="rgb_array", max_episode_steps=1000)
        rl_policy = make_rl_policy_v1(v1_model, v1_norm)
        r = record_video(env, rl_policy,
                         os.path.join(OUTPUT_DIR, "rl_v1_latest.mp4"), max_steps=1000)
        env.close()
        results["rl_v1"] = r
        print(f"  v1 RL: {r['steps']} steps, dist={r['distance_m']:.3f}m, speed={r['speed_m_s']:.4f} m/s")
    else:
        print("  v1 model not found, skipping")

    # 3. v1 RL policy at 500K checkpoint
    print("\n[3/3] Recording v1 RL policy (500K steps)...")
    v1_500k = os.path.join(MODEL_DIR, "dino_ppo_500000_steps.zip")
    if os.path.exists(v1_500k):
        env = DinoQuadrupedEnv(render_mode="rgb_array", max_episode_steps=1000)
        rl_policy_500k = make_rl_policy_v1(v1_500k, v1_norm)
        r = record_video(env, rl_policy_500k,
                         os.path.join(OUTPUT_DIR, "rl_v1_500k.mp4"), max_steps=1000)
        env.close()
        results["rl_v1_500k"] = r
        print(f"  v1 500K: {r['steps']} steps, dist={r['distance_m']:.3f}m, speed={r['speed_m_s']:.4f} m/s")

    # Save results
    with open(os.path.join(OUTPUT_DIR, "eval_summary_v2.json"), "w") as f:
        json.dump(results, f, indent=2)

    # Print comparison table
    print("\n" + "=" * 70)
    print("  Evaluation Comparison")
    print("=" * 70)
    print(f"  {'Policy':<20} {'Steps':>8} {'Dist(m)':>10} {'Speed(m/s)':>12} {'Reward':>10}")
    print(f"  {'-'*20} {'-'*8} {'-'*10} {'-'*12} {'-'*10}")
    for name, r in results.items():
        print(f"  {name:<20} {r['steps']:>8} {r['distance_m']:>10.3f} {r['speed_m_s']:>12.4f} {r['total_reward']:>10.1f}")

    print(f"\n  Videos saved to: {OUTPUT_DIR}/")
    print(f"  Gallery: http://10.21.31.54:18888/eval_output/")


if __name__ == "__main__":
    main()
