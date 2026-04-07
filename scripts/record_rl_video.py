#!/usr/bin/env python3
"""
Record video of the trained RL policy walking (headless).
Uses the PPO model from training to control the Dino Quadruped.
"""

import os
import sys
import numpy as np
import imageio
import pybullet as p
import pybullet_data

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize, VecMonitor
from stable_baselines3.common.utils import set_random_seed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rl"))
from dino_env import DinoQuadrupedEnv, JOINT_NAMES

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
LOG_DIR = os.path.join(PROJECT_ROOT, "rl_logs")
MODEL_DIR = os.path.join(LOG_DIR, "models")
BEST_MODEL_PATH = os.path.join(LOG_DIR, "best_model")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "logs")
URDF_PATH = os.path.join(PROJECT_ROOT, "urdf", "dino_quadruped.urdf")

# Video settings
WIDTH, HEIGHT = 640, 480
FPS = 30
SIM_DT = 1.0 / 240
ACTION_REPEAT = 4
CONTROL_DT = SIM_DT * ACTION_REPEAT
FRAMES_PER_VIDEO_FRAME = int(1.0 / (FPS * SIM_DT))


def render_frame(physics_client, robot, cam_distance=0.5, cam_yaw=45, cam_pitch=-25):
    """Render a single frame tracking the robot."""
    pos, _ = p.getBasePositionAndOrientation(robot, physicsClientId=physics_client)
    view_matrix = p.computeViewMatrixFromYawPitchRoll(
        cameraTargetPosition=list(pos),
        distance=cam_distance,
        yaw=cam_yaw,
        pitch=cam_pitch,
        roll=0,
        upAxisIndex=2,
    )
    proj_matrix = p.computeProjectionMatrixFOV(
        fov=60, aspect=WIDTH / HEIGHT, nearVal=0.01, farVal=10.0
    )
    _, _, rgb, _, _ = p.getCameraImage(
        WIDTH, HEIGHT, view_matrix, proj_matrix,
        renderer=p.ER_TINY_RENDERER,
        physicsClientId=physics_client,
    )
    return np.array(rgb, dtype=np.uint8).reshape(HEIGHT, WIDTH, 4)[:, :, :3]


def record_rl_video(duration=10.0):
    """Record the RL policy controlling the robot."""
    print("=" * 60)
    print("  Recording RL Policy Video")
    print(f"  Duration: {duration}s | FPS: {FPS} | Resolution: {WIDTH}x{HEIGHT}")
    print("=" * 60)

    # Find best model
    model_path = os.path.join(BEST_MODEL_PATH, "best_model.zip")
    if not os.path.exists(model_path):
        model_path = os.path.join(MODEL_DIR, "latest_model.zip")
    if not os.path.exists(model_path):
        print("  No trained model found!")
        return None
    print(f"  Model: {model_path}")

    # Load model with a dummy vec env for prediction
    def make_env():
        env = DinoQuadrupedEnv(max_episode_steps=2000)
        return env

    vec_env = SubprocVecEnv([lambda: make_env()])
    vec_env = VecMonitor(vec_env)

    norm_path = os.path.join(MODEL_DIR, "latest_vecnormalize.pkl")
    if os.path.exists(norm_path):
        vec_env = VecNormalize.load(norm_path, vec_env)
        vec_env.training = False
        vec_env.norm_reward = False
        print(f"  Loaded normalization stats")

    model = PPO.load(model_path, env=vec_env)
    print(f"  Model loaded successfully")

    # Setup separate rendering sim
    physics_client = p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81, physicsClientId=physics_client)
    p.setTimeStep(SIM_DT, physicsClientId=physics_client)
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.loadURDF("plane.urdf", physicsClientId=physics_client)

    robot = p.loadURDF(
        URDF_PATH,
        basePosition=[0, 0, 0.25],
        baseOrientation=p.getQuaternionFromEuler([0, 0, 0]),
        useFixedBase=False,
        physicsClientId=physics_client,
    )

    # Build joint map
    joint_map = {}
    for i in range(p.getNumJoints(robot, physicsClientId=physics_client)):
        info = p.getJointInfo(robot, i, physicsClientId=physics_client)
        joint_map[info[1].decode("utf-8")] = i

    # Use the vec env for observations, step the rendering sim in sync
    obs = vec_env.reset()
    frames = []
    total_frames = int(duration * FPS)
    steps_per_frame = max(1, int(CONTROL_DT * FPS))  # RL steps per video frame

    # Also reset the rendering sim with same initial pose
    init_angles = [0, -0.6, -1.2] * 4
    for i, name in enumerate(JOINT_NAMES):
        idx = joint_map[name]
        p.resetJointState(robot, idx, init_angles[i], physicsClientId=physics_client)
    for _ in range(50):
        for i, name in enumerate(JOINT_NAMES):
            idx = joint_map[name]
            p.setJointMotorControl2(
                robot, idx, controlMode=p.POSITION_CONTROL,
                targetPosition=init_angles[i], force=5.0, maxVelocity=10.0,
                physicsClientId=physics_client,
            )
        p.stepSimulation(physicsClientId=physics_client)

    print(f"\n  Recording {total_frames} frames...")

    from dino_env import JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH

    t = 0.0
    frame_idx = 0
    rl_step = 0

    while frame_idx < total_frames:
        # Get action from RL policy
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, dones, infos = vec_env.step(action)

        # Map action to joint angles (same as env)
        act = np.clip(action[0], -1.0, 1.0)
        mid = (JOINT_LIMITS_HIGH + JOINT_LIMITS_LOW) / 2
        half_range = (JOINT_LIMITS_HIGH - JOINT_LIMITS_LOW) / 2
        target_angles = mid + act * half_range

        # Apply to rendering sim
        for sub_step in range(ACTION_REPEAT):
            for i, name in enumerate(JOINT_NAMES):
                idx = joint_map[name]
                p.setJointMotorControl2(
                    robot, idx, controlMode=p.POSITION_CONTROL,
                    targetPosition=float(target_angles[i]),
                    force=5.0, maxVelocity=10.0,
                    physicsClientId=physics_client,
                )
            p.stepSimulation(physicsClientId=physics_client)

        t += CONTROL_DT
        rl_step += 1

        # Render frame at video FPS
        if rl_step % max(1, int(1.0 / (FPS * CONTROL_DT))) == 0 or frame_idx == 0:
            frame = render_frame(physics_client, robot, cam_distance=0.5, cam_yaw=45, cam_pitch=-25)
            frames.append(frame)
            frame_idx += 1

            if frame_idx % FPS == 0:
                pos, orn = p.getBasePositionAndOrientation(robot, physicsClientId=physics_client)
                euler = p.getEulerFromQuaternion(orn)
                print(f"  Frame {frame_idx}/{total_frames} | t={t:.1f}s | "
                      f"pos=({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f}) | "
                      f"yaw={np.degrees(euler[2]):+.1f}°")

        if dones[0]:
            print(f"  Episode ended at step {rl_step} (t={t:.1f}s), resetting...")
            obs = vec_env.reset()
            # Reset rendering sim too
            p.resetBasePositionAndOrientation(
                robot, [0, 0, 0.25], p.getQuaternionFromEuler([0, 0, 0]),
                physicsClientId=physics_client,
            )
            for i, name in enumerate(JOINT_NAMES):
                idx = joint_map[name]
                p.resetJointState(robot, idx, init_angles[i], physicsClientId=physics_client)

    p.disconnect(physicsClientId=physics_client)
    vec_env.close()

    # Write video
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "dino_rl_walk.mp4")
    writer = imageio.get_writer(output_path, fps=FPS, codec='libx264',
                                output_params=['-pix_fmt', 'yuv420p'])
    for f in frames:
        writer.append_data(f)
    writer.close()
    print(f"\n  Video saved: {output_path} ({len(frames)} frames, {len(frames)/FPS:.1f}s)")
    return output_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=10.0, help="Video duration in seconds")
    args = parser.parse_args()
    record_rl_video(duration=args.duration)
