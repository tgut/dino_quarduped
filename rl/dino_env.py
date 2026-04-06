#!/usr/bin/env python3
"""
Dino Quadruped RL Environment — Gymnasium + PyBullet
Observation: body state + joint states
Action: 12 joint target angles (continuous)
Reward: forward velocity - energy cost - fall penalty + alive bonus
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pybullet as p
import pybullet_data
import os

URDF_PATH = os.path.join(os.path.dirname(__file__), "..", "urdf", "dino_quadruped.urdf")

# Joint limits from URDF
HIP_LIMIT = 0.5        # ±0.5 rad
SHOULDER_LIMIT = 1.57   # ±1.57 rad
KNEE_LOW = -2.6
KNEE_HIGH = -0.1

# Ordered joint names (must match URDF)
JOINT_NAMES = [
    "fl_hip_joint", "fl_shoulder_joint", "fl_knee_joint",
    "fr_hip_joint", "fr_shoulder_joint", "fr_knee_joint",
    "rl_hip_joint", "rl_shoulder_joint", "rl_knee_joint",
    "rr_hip_joint", "rr_shoulder_joint", "rr_knee_joint",
]

# Per-joint action limits [low, high]
JOINT_LIMITS_LOW = np.array([
    -HIP_LIMIT, -SHOULDER_LIMIT, KNEE_LOW,  # FL
    -HIP_LIMIT, -SHOULDER_LIMIT, KNEE_LOW,  # FR
    -HIP_LIMIT, -SHOULDER_LIMIT, KNEE_LOW,  # RL
    -HIP_LIMIT, -SHOULDER_LIMIT, KNEE_LOW,  # RR
], dtype=np.float32)

JOINT_LIMITS_HIGH = np.array([
    HIP_LIMIT, SHOULDER_LIMIT, KNEE_HIGH,  # FL
    HIP_LIMIT, SHOULDER_LIMIT, KNEE_HIGH,  # FR
    HIP_LIMIT, SHOULDER_LIMIT, KNEE_HIGH,  # RL
    HIP_LIMIT, SHOULDER_LIMIT, KNEE_HIGH,  # RR
], dtype=np.float32)


class DinoQuadrupedEnv(gym.Env):
    """
    Gymnasium environment for Dino Quadruped locomotion.

    Observation (dim=36):
        - body height (1)
        - body roll, pitch, yaw (3)
        - body linear velocity (3)
        - body angular velocity (3)
        - joint angles (12)
        - joint velocities (12)
        - phase clock: sin(t), cos(t) (2)

    Action (dim=12):
        - target joint angles, normalized to [-1, 1]

    Reward:
        - forward velocity reward
        - alive bonus
        - energy penalty (joint torques)
        - orientation penalty (roll/pitch)
        - yaw penalty
        - fall termination
    """

    metadata = {"render_modes": ["human", "rgb_array"]}

    def __init__(self, render_mode=None, max_episode_steps=1000):
        super().__init__()

        self.render_mode = render_mode
        self.max_episode_steps = max_episode_steps
        self.dt = 1.0 / 240.0
        self.action_repeat = 4  # apply action for 4 physics steps → 60Hz control
        self.control_dt = self.dt * self.action_repeat

        # Spaces
        obs_dim = 36
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32
        )
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(12,), dtype=np.float32
        )

        # PyBullet
        self._physics_client = None
        self._robot = None
        self._joint_map = {}
        self._step_count = 0
        self._t = 0.0

    def _connect(self):
        if self._physics_client is not None:
            return
        if self.render_mode == "human":
            self._physics_client = p.connect(p.GUI)
        else:
            self._physics_client = p.connect(p.DIRECT)

    def _load_robot(self):
        p.resetSimulation(physicsClientId=self._physics_client)
        p.setGravity(0, 0, -9.81, physicsClientId=self._physics_client)
        p.setTimeStep(self.dt, physicsClientId=self._physics_client)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.loadURDF("plane.urdf", physicsClientId=self._physics_client)

        self._robot = p.loadURDF(
            URDF_PATH,
            basePosition=[0, 0, 0.25],
            baseOrientation=p.getQuaternionFromEuler([0, 0, 0]),
            useFixedBase=False,
            physicsClientId=self._physics_client,
        )

        # Build joint map
        self._joint_map = {}
        num_joints = p.getNumJoints(self._robot, physicsClientId=self._physics_client)
        for i in range(num_joints):
            info = p.getJointInfo(self._robot, i, physicsClientId=self._physics_client)
            name = info[1].decode("utf-8")
            self._joint_map[name] = i

        # Disable default motor (we control via torque/position)
        for name in JOINT_NAMES:
            idx = self._joint_map[name]
            p.setJointMotorControl2(
                self._robot, idx,
                controlMode=p.VELOCITY_CONTROL,
                force=0,
                physicsClientId=self._physics_client,
            )

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._connect()
        self._load_robot()
        self._step_count = 0
        self._t = 0.0

        # Set initial standing pose
        init_angles = [0, -0.6, -1.2] * 4  # slight crouch
        for i, name in enumerate(JOINT_NAMES):
            idx = self._joint_map[name]
            p.resetJointState(
                self._robot, idx, init_angles[i],
                physicsClientId=self._physics_client,
            )

        # Let settle for a moment
        for _ in range(50):
            self._apply_joint_targets(np.array(init_angles, dtype=np.float32))
            p.stepSimulation(physicsClientId=self._physics_client)

        obs = self._get_obs()
        return obs, {}

    def step(self, action):
        self._step_count += 1
        self._t += self.control_dt

        # Map action [-1,1] to joint angle limits
        target_angles = self._action_to_angles(action)

        # Apply action for multiple physics steps
        torques = []
        for _ in range(self.action_repeat):
            t = self._apply_joint_targets(target_angles)
            torques.append(t)
            p.stepSimulation(physicsClientId=self._physics_client)

        obs = self._get_obs()
        reward, reward_info = self._compute_reward(obs, torques)
        terminated = self._check_termination(obs)
        truncated = self._step_count >= self.max_episode_steps

        return obs, reward, terminated, truncated, reward_info

    def _action_to_angles(self, action):
        """Map [-1,1] action to joint angle range."""
        action = np.clip(action, -1.0, 1.0)
        mid = (JOINT_LIMITS_HIGH + JOINT_LIMITS_LOW) / 2
        half_range = (JOINT_LIMITS_HIGH - JOINT_LIMITS_LOW) / 2
        return mid + action * half_range

    def _apply_joint_targets(self, target_angles):
        """Apply position control and return applied torques."""
        torques = np.zeros(12, dtype=np.float32)
        for i, name in enumerate(JOINT_NAMES):
            idx = self._joint_map[name]
            p.setJointMotorControl2(
                self._robot, idx,
                controlMode=p.POSITION_CONTROL,
                targetPosition=float(target_angles[i]),
                force=5.0,
                maxVelocity=10.0,
                physicsClientId=self._physics_client,
            )
            # Read actual torque
            state = p.getJointState(self._robot, idx, physicsClientId=self._physics_client)
            torques[i] = state[3]  # appliedJointMotorTorque
        return torques

    def _get_obs(self):
        """Build observation vector (dim=36)."""
        pos, orn = p.getBasePositionAndOrientation(
            self._robot, physicsClientId=self._physics_client
        )
        euler = p.getEulerFromQuaternion(orn)
        lin_vel, ang_vel = p.getBaseVelocity(
            self._robot, physicsClientId=self._physics_client
        )

        joint_angles = np.zeros(12, dtype=np.float32)
        joint_vels = np.zeros(12, dtype=np.float32)
        for i, name in enumerate(JOINT_NAMES):
            idx = self._joint_map[name]
            state = p.getJointState(self._robot, idx, physicsClientId=self._physics_client)
            joint_angles[i] = state[0]
            joint_vels[i] = state[1]

        # Phase clock (helps learn periodic gaits)
        freq = 2.0  # 2 Hz target gait frequency
        phase_sin = np.sin(2 * np.pi * freq * self._t)
        phase_cos = np.cos(2 * np.pi * freq * self._t)

        obs = np.concatenate([
            [pos[2]],                              # body height (1)
            list(euler),                           # roll, pitch, yaw (3)
            list(lin_vel),                         # linear velocity (3)
            list(ang_vel),                         # angular velocity (3)
            joint_angles,                          # joint angles (12)
            joint_vels,                            # joint velocities (12)
            [phase_sin, phase_cos],                # phase clock (2)
        ]).astype(np.float32)

        return obs

    def _compute_reward(self, obs, torques_list):
        """
        Reward function designed for forward locomotion.
        """
        height = obs[0]
        roll, pitch, yaw = obs[1], obs[2], obs[3]
        vx, vy, vz = obs[4], obs[5], obs[6]

        # 1. Forward velocity reward (main objective)
        r_velocity = 5.0 * vx  # reward forward, penalize backward

        # 2. Alive bonus
        r_alive = 0.5

        # 3. Orientation penalty (keep upright)
        r_orientation = -2.0 * (roll ** 2 + pitch ** 2)

        # 4. Yaw penalty (go straight)
        r_yaw = -0.5 * yaw ** 2

        # 5. Lateral velocity penalty (don't drift sideways)
        r_lateral = -1.0 * vy ** 2

        # 6. Energy penalty (minimize torque)
        mean_torques = np.mean([np.abs(t) for t in torques_list], axis=0)
        r_energy = -0.005 * np.sum(mean_torques ** 2)

        # 7. Vertical velocity penalty (don't bounce)
        r_vertical = -0.5 * vz ** 2

        # 8. Joint velocity smoothness
        joint_vels = obs[16:28]
        r_smooth = -0.001 * np.sum(joint_vels ** 2)

        reward = (r_velocity + r_alive + r_orientation + r_yaw +
                  r_lateral + r_energy + r_vertical + r_smooth)

        info = {
            "r_velocity": r_velocity,
            "r_alive": r_alive,
            "r_orientation": r_orientation,
            "r_energy": r_energy,
            "vx": vx,
            "height": height,
        }
        return float(reward), info

    def _check_termination(self, obs):
        """Terminate if robot falls."""
        height = obs[0]
        roll, pitch = obs[1], obs[2]

        # Fell below threshold
        if height < 0.05:
            return True
        # Flipped over
        if abs(roll) > 1.2 or abs(pitch) > 1.2:  # ~70 degrees
            return True
        return False

    def close(self):
        if self._physics_client is not None:
            p.disconnect(physicsClientId=self._physics_client)
            self._physics_client = None
