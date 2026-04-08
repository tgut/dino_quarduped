#!/usr/bin/env python3
"""
Train Dino Quadruped with PPO (Stable-Baselines3).

Usage:
    python3 rl/train_ppo.py                        # default 500K steps
    python3 rl/train_ppo.py --timesteps 2000000    # 2M steps
    python3 rl/train_ppo.py --resume               # resume from checkpoint
"""

import argparse
import os
import sys
import time
import json
import numpy as np

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize, VecMonitor
from stable_baselines3.common.callbacks import (
    CheckpointCallback, EvalCallback, BaseCallback
)
from stable_baselines3.common.utils import set_random_seed

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))
from dino_env import DinoQuadrupedEnv

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
LOG_DIR = os.path.join(PROJECT_ROOT, "rl_logs")
MODEL_DIR = os.path.join(LOG_DIR, "models")
TB_DIR = os.path.join(LOG_DIR, "tensorboard")
BEST_MODEL_PATH = os.path.join(LOG_DIR, "best_model")


def make_env(rank, seed=0):
    """Create a single environment instance."""
    def _init():
        env = DinoQuadrupedEnv(max_episode_steps=2000)  # v7: doubled to match action_repeat 4→2
        env.reset(seed=seed + rank)
        return env
    set_random_seed(seed + rank)
    return _init


class RewardLoggerCallback(BaseCallback):
    """Log detailed reward components to file periodically."""

    def __init__(self, log_path, verbose=0):
        super().__init__(verbose)
        self.log_path = log_path
        self.episode_rewards = []
        self.episode_lengths = []
        self.episode_vx = []
        self.log_data = []

    def _on_step(self) -> bool:
        # Collect info from vectorized env
        infos = self.locals.get("infos", [])
        for info in infos:
            if "episode" in info:
                self.episode_rewards.append(info["episode"]["r"])
                self.episode_lengths.append(info["episode"]["l"])

            if "vx" in info:
                self.episode_vx.append(info["vx"])

        # Log summary every 10K steps
        if self.num_timesteps % 10000 == 0 and len(self.episode_rewards) > 0:
            entry = {
                "timesteps": self.num_timesteps,
                "mean_reward": float(np.mean(self.episode_rewards[-50:])),
                "mean_length": float(np.mean(self.episode_lengths[-50:])),
                "mean_vx": float(np.mean(self.episode_vx[-200:])) if self.episode_vx else 0.0,
                "max_reward": float(np.max(self.episode_rewards[-50:])),
            }
            self.log_data.append(entry)

            print(f"  [{self.num_timesteps:>8d}] "
                  f"reward={entry['mean_reward']:+7.1f} | "
                  f"len={entry['mean_length']:5.0f} | "
                  f"vx={entry['mean_vx']:+.4f} m/s | "
                  f"max_r={entry['max_reward']:+7.1f}")

            with open(self.log_path, "w") as f:
                json.dump(self.log_data, f, indent=2)

        return True


def train(args):
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(TB_DIR, exist_ok=True)

    print("=" * 60)
    print("  Dino Quadruped RL Training (PPO)")
    print(f"  Timesteps:    {args.timesteps:,}")
    print(f"  Num envs:     {args.num_envs}")
    print(f"  Log dir:      {LOG_DIR}")
    print(f"  TensorBoard:  {TB_DIR}")
    print("=" * 60)

    # Create vectorized environments
    env = SubprocVecEnv([make_env(i, seed=args.seed) for i in range(args.num_envs)])
    env = VecMonitor(env)
    env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_obs=10.0)

    # Eval env (single, for evaluation callbacks)
    eval_env = SubprocVecEnv([make_env(100, seed=args.seed + 100)])
    eval_env = VecMonitor(eval_env)
    eval_env = VecNormalize(eval_env, norm_obs=True, norm_reward=False, clip_obs=10.0)

    if args.resume and os.path.exists(os.path.join(MODEL_DIR, "latest_model.zip")):
        print("\n  Resuming from checkpoint...")
        model = PPO.load(
            os.path.join(MODEL_DIR, "latest_model"),
            env=env,
            tensorboard_log=TB_DIR,
        )
        # Load normalization stats
        norm_path = os.path.join(MODEL_DIR, "latest_vecnormalize.pkl")
        if os.path.exists(norm_path):
            env = VecNormalize.load(norm_path, env)
    else:
        print("\n  Creating new PPO model (v7 anti-tremor hyperparams)...")
        model = PPO(
            "MlpPolicy",
            env,
            learning_rate=3e-4,
            n_steps=4096,          # v6: 2048→4096, more stable gradients
            batch_size=128,        # v6: 64→128, larger mini-batches
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.005,        # v6: 0.01→0.005, less random exploration
            vf_coef=0.5,
            max_grad_norm=0.5,
            policy_kwargs=dict(
                net_arch=dict(pi=[256, 128, 64], vf=[256, 128, 64]),  # v6: 3-layer
            ),
            tensorboard_log=TB_DIR,
            verbose=1,
            seed=args.seed,
            device="cuda",
        )

    # Callbacks
    checkpoint_cb = CheckpointCallback(
        save_freq=max(50000 // args.num_envs, 1),
        save_path=MODEL_DIR,
        name_prefix="dino_ppo",
    )
    eval_cb = EvalCallback(
        eval_env,
        best_model_save_path=BEST_MODEL_PATH,
        log_path=LOG_DIR,
        eval_freq=max(20000 // args.num_envs, 1),
        n_eval_episodes=5,
        deterministic=True,
    )
    reward_logger = RewardLoggerCallback(
        log_path=os.path.join(LOG_DIR, "training_log.json")
    )

    # Train
    print(f"\n  Starting training for {args.timesteps:,} timesteps...\n")
    t0 = time.time()

    model.learn(
        total_timesteps=args.timesteps,
        callback=[checkpoint_cb, eval_cb, reward_logger],
        progress_bar=True,
    )

    elapsed = time.time() - t0
    print(f"\n  Training complete in {elapsed:.0f}s ({elapsed/60:.1f} min)")

    # Save final model + normalization
    model.save(os.path.join(MODEL_DIR, "latest_model"))
    env.save(os.path.join(MODEL_DIR, "latest_vecnormalize.pkl"))
    print(f"  Model saved to {MODEL_DIR}/latest_model.zip")

    env.close()
    eval_env.close()


def evaluate(args):
    """Evaluate trained model and compare with hand-tuned baseline."""
    print("=" * 60)
    print("  Evaluating RL Policy vs Hand-Tuned Baseline")
    print("=" * 60)

    # Prefer best_model (from EvalCallback) over latest checkpoint
    model_path = os.path.join(BEST_MODEL_PATH, "best_model.zip")
    if not os.path.exists(model_path):
        model_path = os.path.join(MODEL_DIR, "latest_model.zip")
    if not os.path.exists(model_path):
        print("  No trained model found. Run training first.")
        return
    print(f"  Using model: {model_path}")

    # Load model
    env = SubprocVecEnv([make_env(0)])
    env = VecMonitor(env)

    norm_path = os.path.join(MODEL_DIR, "latest_vecnormalize.pkl")
    if os.path.exists(norm_path):
        env = VecNormalize.load(norm_path, env)
        env.training = False
        env.norm_reward = False

    model = PPO.load(model_path, env=env)

    # Run evaluation episodes
    n_episodes = 10
    episode_rewards = []
    episode_distances = []
    episode_speeds = []
    episode_lengths = []

    for ep in range(n_episodes):
        obs = env.reset()
        total_reward = 0
        steps = 0
        start_x = None

        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, dones, infos = env.step(action)
            total_reward += reward[0]
            steps += 1

            if start_x is None and "height" in infos[0]:
                start_x = 0.0

            if dones[0]:
                done = True

        episode_rewards.append(total_reward)
        episode_lengths.append(steps)
        duration = steps * (1.0 / 240.0 * 4)  # control_dt

        # Get final position from last info
        vx = infos[0].get("vx", 0.0) if infos else 0.0
        episode_speeds.append(vx)

    # Print results
    print(f"\n  RL Policy Results ({n_episodes} episodes):")
    print(f"  Mean reward:    {np.mean(episode_rewards):+.1f} ± {np.std(episode_rewards):.1f}")
    print(f"  Mean length:    {np.mean(episode_lengths):.0f} steps")
    print(f"  Mean speed(vx): {np.mean(episode_speeds):.4f} m/s")
    print(f"\n  Hand-Tuned Baseline (from benchmark):")
    print(f"  Speed: 0.031 m/s | CoT: 5.84")

    # Save comparison
    results = {
        "rl_policy": {
            "mean_reward": float(np.mean(episode_rewards)),
            "mean_length": float(np.mean(episode_lengths)),
            "mean_speed_m_per_s": float(np.mean(episode_speeds)),
        },
        "hand_tuned_baseline": {
            "speed_m_per_s": 0.031,
            "cot": 5.84,
        }
    }
    results_path = os.path.join(LOG_DIR, "eval_results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {results_path}")

    env.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Dino Quadruped with PPO")
    parser.add_argument("--timesteps", type=int, default=5_000_000,
                        help="Total training timesteps (v7: 5M for convergence)")
    parser.add_argument("--num-envs", type=int, default=8,
                        help="Number of parallel environments")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from checkpoint")
    parser.add_argument("--eval", action="store_true",
                        help="Evaluate trained model instead of training")
    args = parser.parse_args()

    if args.eval:
        evaluate(args)
    else:
        train(args)
