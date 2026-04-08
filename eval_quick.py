#!/usr/bin/env python3
"""Quick eval: record v1 model with relaxed termination."""
import os, sys, json, pickle, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "rl"))

import pybullet as p
from dino_env import DinoQuadrupedEnv

PROJECT_ROOT = os.path.dirname(__file__)
MODEL_DIR = os.path.join(PROJECT_ROOT, "rl_logs", "models")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "eval_output")


class DinoEnvRelaxed(DinoQuadrupedEnv):
    """Env with relaxed termination (v1-compatible)."""
    def _check_termination(self, obs):
        height = obs[0]
        roll, pitch = obs[1], obs[2]
        if height < 0.05:
            return True
        if abs(roll) > 1.2 or abs(pitch) > 1.2:
            return True
        return False


def record_video(env, policy_fn, filename, max_steps=500, width=640, height=480):
    import imageio
    frames = []
    obs, _ = env.reset()
    client = env._physics_client
    total_reward = 0
    positions = []
    heights = []
    contacts_total = []

    for step in range(max_steps):
        action = policy_fn(obs)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        pos, _ = p.getBasePositionAndOrientation(env._robot, physicsClientId=client)
        positions.append(pos)
        heights.append(pos[2])
        contacts_total.append(info.get("n_contacts", 0))

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
        "total_reward": round(float(total_reward), 1),
        "steps": step + 1,
        "distance_m": round(float(dist), 3),
        "speed_m_s": round(float(dist / ((step+1) * env.control_dt)), 4) if step > 0 else 0,
        "avg_height": round(float(np.mean(heights)), 4),
        "avg_contacts": round(float(np.mean(contacts_total)), 2),
    }


def make_policy(model_path, norm_path):
    from stable_baselines3 import PPO
    model = PPO.load(model_path, device="cpu")
    with open(norm_path, "rb") as f:
        vn = pickle.load(f)
    obs_rms = vn.obs_rms
    clip_obs = vn.clip_obs
    epsilon = vn.epsilon

    def policy(obs):
        obs40 = obs[:40] if len(obs) > 40 else obs
        obs_norm = np.clip(
            (obs40 - obs_rms.mean) / np.sqrt(obs_rms.var + epsilon),
            -clip_obs, clip_obs).astype(np.float32)
        action, _ = model.predict(obs_norm.reshape(1, -1), deterministic=True)
        return action[0]
    return policy


def neutral_policy(obs):
    return np.zeros(12, dtype=np.float32)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    v1_norm = os.path.join(MODEL_DIR, "latest_vecnormalize.pkl")
    results = {}

    # 1. Baseline
    print("[1/4] Baseline...")
    env = DinoEnvRelaxed(render_mode="rgb_array", max_episode_steps=500)
    r = record_video(env, neutral_policy,
                     os.path.join(OUTPUT_DIR, "baseline_neutral.mp4"), max_steps=500)
    env.close()
    results["baseline"] = r
    print(f"  {r}")

    # 2. v1 RL 1M (latest)
    print("[2/4] v1 RL 1M steps...")
    env = DinoEnvRelaxed(render_mode="rgb_array", max_episode_steps=1000)
    policy = make_policy(os.path.join(MODEL_DIR, "latest_model.zip"), v1_norm)
    r = record_video(env, policy,
                     os.path.join(OUTPUT_DIR, "rl_v1_1M.mp4"), max_steps=1000)
    env.close()
    results["rl_v1_1M"] = r
    print(f"  {r}")

    # 3. v1 RL 500K
    print("[3/4] v1 RL 500K steps...")
    env = DinoEnvRelaxed(render_mode="rgb_array", max_episode_steps=1000)
    policy = make_policy(os.path.join(MODEL_DIR, "dino_ppo_500000_steps.zip"), v1_norm)
    r = record_video(env, policy,
                     os.path.join(OUTPUT_DIR, "rl_v1_500k.mp4"), max_steps=1000)
    env.close()
    results["rl_v1_500k"] = r
    print(f"  {r}")

    # 4. v1 RL 200K (early)
    print("[4/4] v1 RL 200K steps...")
    env = DinoEnvRelaxed(render_mode="rgb_array", max_episode_steps=1000)
    policy = make_policy(os.path.join(MODEL_DIR, "dino_ppo_200000_steps.zip"), v1_norm)
    r = record_video(env, policy,
                     os.path.join(OUTPUT_DIR, "rl_v1_200k.mp4"), max_steps=1000)
    env.close()
    results["rl_v1_200k"] = r
    print(f"  {r}")

    # Save
    with open(os.path.join(OUTPUT_DIR, "eval_summary.json"), "w") as f:
        json.dump(results, f, indent=2)

    # Print table
    print("\n" + "=" * 80)
    print(f"  {'Policy':<16} {'Steps':>6} {'Dist(m)':>8} {'Speed':>10} {'Reward':>8} {'Height':>8} {'Contacts':>8}")
    print(f"  {'-'*16} {'-'*6} {'-'*8} {'-'*10} {'-'*8} {'-'*8} {'-'*8}")
    for name, r in results.items():
        print(f"  {name:<16} {r['steps']:>6} {r['distance_m']:>8.3f} {r['speed_m_s']:>10.4f} {r['total_reward']:>8.1f} {r['avg_height']:>8.4f} {r['avg_contacts']:>8.2f}")

    print(f"\n  Videos at: http://10.21.31.54:18888/eval_output/")


if __name__ == "__main__":
    main()
