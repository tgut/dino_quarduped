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

    Observation (dim=41):
        - body height (1)
        - body roll, pitch, yaw (3)
        - body linear velocity (3)
        - body angular velocity (3)
        - joint angles (12)
        - joint velocities (12)
        - phase clock: sin(t), cos(t) (2)
        - foot contacts: FL, FR, RL, RR (4)
        - body contact: 1 if body/leg touching ground (1)

    Action (dim=12):
        - target joint angles, normalized to [-1, 1]

    Reward:
        - forward velocity reward
        - alive bonus
        - energy penalty (joint torques)
        - orientation penalty (roll/pitch)
        - gait rewards (trot pattern, foot contact balance)
        - action smoothness penalty
        - fall termination
    """

    metadata = {"render_modes": ["human", "rgb_array"]}

    # Foot link names for contact detection
    FOOT_LINK_NAMES = ["fl_foot", "fr_foot", "rl_foot", "rr_foot"]
    # Body/thigh links — contact with ground = bad (stumble/crawl)
    BODY_LINK_NAMES = [
        "base_link",
        "fl_hip", "fl_upper_leg", "fl_lower_leg",
        "fr_hip", "fr_upper_leg", "fr_lower_leg",
        "rl_hip", "rl_upper_leg", "rl_lower_leg",
        "rr_hip", "rr_upper_leg", "rr_lower_leg",
    ]

    # ── Domain Randomization defaults ─────────────────────────
    # Each key: (low, high) — sampled uniformly per episode in reset()
    # Set dr_enabled=False to disable (original v7 behavior)
    DR_RANGES = {
        # Dynamics
        "body_mass_scale":  (0.8,  1.2),    # multiplier on nominal 1.5 kg
        "friction":         (0.4,  1.0),    # ground lateral friction
        "joint_damping":    (0.01, 0.1),    # per-joint damping
        "joint_friction":   (0.0,  0.05),   # per-joint coulomb friction
        # Actuator
        "action_delay":     (0,    3),      # steps of delay (int), simulates servo lag
        "action_noise_std": (0.0,  0.02),   # rad, Gaussian noise on target angles
        "torque_scale":     (0.8,  1.2),    # multiplier on motor force
        # Sensor noise (applied to observation)
        "imu_accel_noise":  (0.0,  0.5),    # m/s² std
        "imu_gyro_noise":   (0.0,  0.05),   # rad/s std
        "imu_gyro_drift":   (0.0,  0.01),   # rad/s constant drift per axis
        # Environment
        "push_interval":    (100,  300),    # steps between random pushes
        "push_force":       (0.0,  3.0),    # N, lateral push magnitude
    }

    def __init__(self, render_mode=None, max_episode_steps=2000,
                 dr_enabled=False, dr_strength=1.0):
        super().__init__()

        self.render_mode = render_mode
        self.max_episode_steps = max_episode_steps
        self.dt = 1.0 / 240.0
        self.action_repeat = 2  # v7: 4→2, control freq 60Hz→120Hz for smoother motion
        self.control_dt = self.dt * self.action_repeat

        # Domain Randomization config
        self.dr_enabled = dr_enabled
        self.dr_strength = np.clip(dr_strength, 0.0, 1.0)  # 0=no DR, 1=full range

        # Spaces
        obs_dim = 41
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32
        )
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(12,), dtype=np.float32
        )

        # PyBullet
        self._physics_client = None
        self._robot = None
        self._plane = None
        self._joint_map = {}
        self._link_name_to_idx = {}  # link name → link index for contact detection
        self._step_count = 0
        self._t = 0.0
        self._prev_action = np.zeros(12, dtype=np.float32)
        self._prev_joint_vels = np.zeros(12, dtype=np.float32)  # v7: for joint accel penalty

        # DR per-episode state (set in reset)
        self._dr = {}
        self._action_delay_buf = []  # ring buffer for action delay
        self._gyro_drift = np.zeros(3, dtype=np.float32)
        self._next_push_step = 0

    def _connect(self):
        if self._physics_client is not None:
            return
        if self.render_mode == "human":
            self._physics_client = p.connect(p.GUI)
        else:
            self._physics_client = p.connect(p.DIRECT)

    def set_dr_strength(self, strength):
        """Update DR strength (called by DRScheduleCallback)."""
        self.dr_strength = np.clip(strength, 0.0, 1.0)

    def _sample_dr(self):
        """Sample domain randomization parameters for this episode."""
        dr = {}
        if not self.dr_enabled:
            # Nominal values (no randomization)
            dr["body_mass_scale"] = 1.0
            dr["friction"] = 0.7
            dr["joint_damping"] = 0.05
            dr["joint_friction"] = 0.01
            dr["action_delay"] = 0
            dr["action_noise_std"] = 0.0
            dr["torque_scale"] = 1.0
            dr["imu_accel_noise"] = 0.0
            dr["imu_gyro_noise"] = 0.0
            dr["imu_gyro_drift"] = 0.0
            dr["push_interval"] = 9999
            dr["push_force"] = 0.0
            return dr

        rng = self.np_random
        s = self.dr_strength  # interpolation factor: 0=nominal, 1=full range
        for key, (lo, hi) in self.DR_RANGES.items():
            nominal = (lo + hi) / 2.0
            rand_lo = nominal + s * (lo - nominal)
            rand_hi = nominal + s * (hi - nominal)
            if key == "action_delay":
                dr[key] = int(rng.integers(int(rand_lo), int(rand_hi) + 1))
            else:
                dr[key] = float(rng.uniform(rand_lo, rand_hi))
        return dr

    def _load_robot(self):
        pc = self._physics_client
        p.resetSimulation(physicsClientId=pc)
        p.setGravity(0, 0, -9.81, physicsClientId=pc)
        p.setTimeStep(self.dt, physicsClientId=pc)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        self._plane = p.loadURDF("plane.urdf", physicsClientId=pc)

        # DR: randomize ground friction
        p.changeDynamics(
            self._plane, -1,
            lateralFriction=self._dr["friction"],
            physicsClientId=pc,
        )

        self._robot = p.loadURDF(
            URDF_PATH,
            basePosition=[0, 0, 0.25],
            baseOrientation=p.getQuaternionFromEuler([0, 0, 0]),
            useFixedBase=False,
            physicsClientId=pc,
        )

        # Build joint map and link name → index map
        self._joint_map = {}
        self._link_name_to_idx = {}
        num_joints = p.getNumJoints(self._robot, physicsClientId=pc)
        for i in range(num_joints):
            info = p.getJointInfo(self._robot, i, physicsClientId=pc)
            joint_name = info[1].decode("utf-8")
            link_name = info[12].decode("utf-8")  # child link name
            self._joint_map[joint_name] = i
            self._link_name_to_idx[link_name] = i

        # DR: randomize body mass
        mass_scale = self._dr["body_mass_scale"]
        dyn = p.getDynamicsInfo(self._robot, -1, physicsClientId=pc)
        nominal_mass = dyn[0]  # base link mass from URDF
        p.changeDynamics(
            self._robot, -1,
            mass=nominal_mass * mass_scale,
            physicsClientId=pc,
        )

        # Disable default motor + DR: randomize joint dynamics
        for name in JOINT_NAMES:
            idx = self._joint_map[name]
            p.setJointMotorControl2(
                self._robot, idx,
                controlMode=p.VELOCITY_CONTROL,
                force=0,
                physicsClientId=pc,
            )
            # Apply per-joint damping and friction
            p.changeDynamics(
                self._robot, idx,
                jointDamping=self._dr["joint_damping"],
                lateralFriction=self._dr["joint_friction"],
                physicsClientId=pc,
            )

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._connect()

        # Sample DR parameters before loading robot
        self._dr = self._sample_dr()
        self._load_robot()

        self._step_count = 0
        self._t = 0.0
        self._prev_action = np.zeros(12, dtype=np.float32)
        self._prev_joint_vels = np.zeros(12, dtype=np.float32)

        # DR: init action delay buffer
        delay = self._dr["action_delay"]
        init_act = np.zeros(12, dtype=np.float32)
        self._action_delay_buf = [init_act.copy() for _ in range(max(delay, 1))]

        # DR: init gyro drift (constant per episode, per axis)
        drift_mag = self._dr["imu_gyro_drift"]
        self._gyro_drift = self.np_random.uniform(-drift_mag, drift_mag, size=3).astype(np.float32)

        # DR: schedule first random push
        self._next_push_step = int(self._dr["push_interval"])

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

        action = np.clip(action, -1.0, 1.0).astype(np.float32)

        # DR: action delay — push current action into buffer, use delayed one
        delay = self._dr["action_delay"]
        if delay > 0 and self.dr_enabled:
            self._action_delay_buf.append(action.copy())
            delayed_action = self._action_delay_buf.pop(0)
        else:
            delayed_action = action

        # Map action [-1,1] to joint angle limits
        target_angles = self._action_to_angles(delayed_action)

        # DR: action noise (simulates servo imprecision)
        noise_std = self._dr["action_noise_std"]
        if noise_std > 0 and self.dr_enabled:
            target_angles = target_angles + self.np_random.normal(0, noise_std, size=12).astype(np.float32)

        # DR: random push
        if self.dr_enabled and self._step_count >= self._next_push_step:
            push_mag = self._dr["push_force"]
            if push_mag > 0:
                fx = self.np_random.uniform(-push_mag, push_mag)
                fy = self.np_random.uniform(-push_mag, push_mag)
                p.applyExternalForce(
                    self._robot, -1,
                    forceObj=[fx, fy, 0],
                    posObj=[0, 0, 0],
                    flags=p.LINK_FRAME,
                    physicsClientId=self._physics_client,
                )
            self._next_push_step = self._step_count + int(self._dr["push_interval"])

        # Apply action for multiple physics steps
        torques = []
        for _ in range(self.action_repeat):
            t = self._apply_joint_targets(target_angles)
            torques.append(t)
            p.stepSimulation(physicsClientId=self._physics_client)

        obs = self._get_obs()
        reward, reward_info = self._compute_reward(obs, torques, action)
        terminated = self._check_termination(obs)
        truncated = self._step_count >= self.max_episode_steps

        # Death penalty — large negative reward on termination (not truncation)
        # This makes "sprint and crash" strategies unprofitable
        if terminated:
            reward -= 20.0
            reward_info["r_death"] = -20.0
        else:
            reward_info["r_death"] = 0.0

        self._prev_action = action.copy()

        return obs, reward, terminated, truncated, reward_info

    def _action_to_angles(self, action):
        """Map [-1,1] action to joint angle range."""
        action = np.clip(action, -1.0, 1.0)
        mid = (JOINT_LIMITS_HIGH + JOINT_LIMITS_LOW) / 2
        half_range = (JOINT_LIMITS_HIGH - JOINT_LIMITS_LOW) / 2
        return mid + action * half_range

    def _apply_joint_targets(self, target_angles):
        """Apply position control and return applied torques."""
        # DR: scale motor force
        motor_force = 5.0 * self._dr.get("torque_scale", 1.0)

        torques = np.zeros(12, dtype=np.float32)
        for i, name in enumerate(JOINT_NAMES):
            idx = self._joint_map[name]
            p.setJointMotorControl2(
                self._robot, idx,
                controlMode=p.POSITION_CONTROL,
                targetPosition=float(target_angles[i]),
                force=motor_force,
                maxVelocity=10.0,
                physicsClientId=self._physics_client,
            )
            # Read actual torque
            state = p.getJointState(self._robot, idx, physicsClientId=self._physics_client)
            torques[i] = state[3]  # appliedJointMotorTorque
        return torques

    def _get_obs(self):
        """Build observation vector (dim=41)."""
        pos, orn = p.getBasePositionAndOrientation(
            self._robot, physicsClientId=self._physics_client
        )
        euler = list(p.getEulerFromQuaternion(orn))
        lin_vel, ang_vel = p.getBaseVelocity(
            self._robot, physicsClientId=self._physics_client
        )
        lin_vel = list(lin_vel)
        ang_vel = list(ang_vel)

        # DR: IMU sensor noise
        if self.dr_enabled:
            accel_std = self._dr["imu_accel_noise"]
            gyro_std = self._dr["imu_gyro_noise"]
            if accel_std > 0:
                lin_vel = [v + float(self.np_random.normal(0, accel_std)) for v in lin_vel]
            if gyro_std > 0:
                ang_vel = [v + float(self.np_random.normal(0, gyro_std)) for v in ang_vel]
            # Gyro drift (constant per episode, accumulates in orientation)
            ang_vel = [v + float(d) for v, d in zip(ang_vel, self._gyro_drift)]

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

        # Foot contact detection — check foot link vs ground plane
        foot_contacts = np.zeros(4, dtype=np.float32)
        for fi, lname in enumerate(self.FOOT_LINK_NAMES):
            link_idx = self._link_name_to_idx.get(lname)
            if link_idx is not None:
                contacts = p.getContactPoints(
                    bodyA=self._robot, bodyB=self._plane,
                    linkIndexA=link_idx,
                    physicsClientId=self._physics_client
                )
                foot_contacts[fi] = 1.0 if len(contacts) > 0 else 0.0

        # Body/leg contact detection — any non-foot touching ground is bad
        body_contact = 0.0
        for lname in self.BODY_LINK_NAMES:
            link_idx = self._link_name_to_idx.get(lname)
            if link_idx is not None:
                contacts = p.getContactPoints(
                    bodyA=self._robot, bodyB=self._plane,
                    linkIndexA=link_idx,
                    physicsClientId=self._physics_client
                )
                if len(contacts) > 0:
                    body_contact = 1.0
                    break
            # base_link uses linkIndex=-1
            elif lname == "base_link":
                contacts = p.getContactPoints(
                    bodyA=self._robot, bodyB=self._plane,
                    linkIndexA=-1,
                    physicsClientId=self._physics_client
                )
                if len(contacts) > 0:
                    body_contact = 1.0
                    break

        obs = np.concatenate([
            [pos[2]],                              # body height (1)
            euler,                                 # roll, pitch, yaw (3)
            lin_vel,                               # linear velocity (3)
            ang_vel,                               # angular velocity (3)
            joint_angles,                          # joint angles (12)
            joint_vels,                            # joint velocities (12)
            [phase_sin, phase_cos],                # phase clock (2) [idx 34-35]
            foot_contacts,                         # foot contacts (4) [idx 36-39]
            [body_contact],                        # body touching ground (1) [idx 40]
        ]).astype(np.float32)

        return obs

    def _compute_reward(self, obs, torques_list, action):
        """
        Reward function v7 — anti-tremor: smoother gaits via higher control freq + penalties.

        v6 achieved stable forward walking but with visible leg tremor.
        Root causes: low control freq (60Hz), weak smoothness penalty, short stance phase.

        v7 changes (on top of v6):
        - action_repeat 4→2 (60Hz→120Hz control) — handled in __init__
        - Action smoothness penalty: -0.015 → -0.04 (2.7x stronger)
        - NEW: joint acceleration penalty -0.002 * Σ(Δjoint_vel²)
        - Foot contact reward: 0.15 → 0.25 per foot (longer stance phase)
        - Gait phase reward: 0.5 → 0.7 (stronger trot incentive)
        - Slight alive bonus bump 2.0→2.2 to offset increased penalties
        """
        height = obs[0]
        roll, pitch, yaw = obs[1], obs[2], obs[3]
        vx, vy, vz = obs[4], obs[5], obs[6]
        ang_vel_z = obs[9]
        joint_angles = obs[10:22]
        joint_vels = obs[22:34]
        phase_sin, phase_cos = obs[34], obs[35]
        foot_contacts = obs[36:40]  # FL, FR, RL, RR
        body_contact = obs[40]

        n_contacts = np.sum(foot_contacts)
        fl, fr, rl, rr = foot_contacts

        # ============================================================
        # POSITIVE TRACKING REWARDS (always >= 0)
        # ============================================================

        # 1. Velocity tracking: PRIMARY reward, tighter sigma
        #    Perfect match → 3.0, standing(vx=0) → 2.3, backwards → 0.6
        #    sigma=0.15 (tighter than v5's 0.25) for more precise tracking
        target_vx = 0.20
        r_velocity = 3.0 * np.exp(-((vx - target_vx) ** 2) / 0.15)

        # 2. Alive bonus — slight bump to offset v7's stronger penalties
        r_alive = 2.2

        # 3. Height tracking: exp reward, always positive
        target_height = 0.155
        r_height = 1.0 * np.exp(-((height - target_height) ** 2) / 0.005)

        # 4. Orientation tracking: reward for being upright
        r_orientation = 0.5 * np.exp(-(roll ** 2 + pitch ** 2) / 0.5)

        # ============================================================
        # GAIT REWARDS (always >= 0)
        # ============================================================

        # 5. Foot contact: more feet on ground = better (0 to 1.0)
        #    v7: 0.15→0.25 per foot, encourage longer stance phase
        r_contact = 0.25 * n_contacts  # 0, 0.25, 0.5, 0.75, 1.0

        # 6. Phase-conditioned trot (0 to 0.7)
        #    v7: 0.5→0.7, stronger trot incentive for rhythmic gait
        diag1_stance = fl * rr
        diag2_stance = fr * rl
        if phase_sin >= 0:
            r_gait = 0.7 * (diag1_stance + (1.0 - fr) * (1.0 - rl))
        else:
            r_gait = 0.7 * (diag2_stance + (1.0 - fl) * (1.0 - rr))

        # 7. Front-rear symmetry (0 or 0.3)
        front_any = min(fl + fr, 1.0)
        rear_any = min(rl + rr, 1.0)
        r_symmetry = 0.3 * front_any * rear_any

        # ============================================================
        # MILD PENALTIES (halved from v3/v4, capped total)
        # These guide behavior but never dominate the alive bonus
        # ============================================================

        # 8. Body contact penalty (mild)
        r_body_contact = -0.5 * body_contact

        # 9. Vertical velocity (anti-bounce, moderate)
        r_vertical = -2.0 * min(vz ** 2, 1.0)  # capped at -2.0

        # 10. Lateral velocity
        r_lateral = -0.15 * min(vy ** 2, 1.0)  # capped

        # 11. Yaw rate
        r_yaw = -0.05 * min(ang_vel_z ** 2, 4.0)  # capped

        # 12. Action smoothness — v7: STRENGTHENED to reduce tremor
        #     v6 had -0.015 (too weak → jerky actions), now -0.04
        action_diff = action - self._prev_action
        r_smooth = -0.04 * np.sum(action_diff ** 2)

        # 13. Energy (halved)
        mean_torques = np.mean([np.abs(t) for t in torques_list], axis=0)
        r_energy = -0.0015 * np.sum(mean_torques ** 2)

        # 14. Joint velocity (halved)
        r_joint_vel = -0.0005 * np.sum(joint_vels ** 2)

        # 15. Joint acceleration — v7 NEW: penalize sudden velocity changes
        #     This directly discourages the high-freq tremor pattern
        joint_accel = joint_vels - self._prev_joint_vels
        r_joint_accel = -0.002 * np.sum(joint_accel ** 2)
        self._prev_joint_vels = joint_vels.copy()

        # 16. Default pose regularization (halved)
        default_angles = np.array([0, -0.6, -1.2] * 4, dtype=np.float32)
        pose_error = joint_angles - default_angles
        r_pose = -0.01 * np.sum(pose_error ** 2)

        # ============================================================
        # TOTAL — v7: still positive for random exploration
        # ============================================================
        reward = (r_velocity + r_alive + r_height + r_orientation +
                  r_contact + r_gait + r_symmetry +
                  r_body_contact + r_vertical + r_lateral + r_yaw +
                  r_smooth + r_energy + r_joint_vel + r_joint_accel + r_pose)

        info = {
            "r_velocity": r_velocity,
            "r_alive": r_alive,
            "r_height": r_height,
            "r_orientation": r_orientation,
            "r_body_contact": r_body_contact,
            "r_contact": r_contact,
            "r_gait": r_gait,
            "r_symmetry": r_symmetry,
            "r_vertical": r_vertical,
            "r_smooth": r_smooth,
            "r_energy": r_energy,
            "r_joint_accel": r_joint_accel,
            "r_pose": r_pose,
            "vx": vx,
            "height": height,
            "n_contacts": n_contacts,
            "body_contact": body_contact,
        }
        return float(reward), info

    def _check_termination(self, obs):
        """Terminate if robot falls — moderate thresholds (between v1 and v2)."""
        height = obs[0]
        roll, pitch = obs[1], obs[2]

        # Height: 0.06m — allows crouching but not belly-on-ground
        # (v1=0.05 too low, v2=0.08 too high)
        if height < 0.06:
            return True
        # Tilt: 1.0 rad (~57°) — clearly falling but not overly strict
        # (v1=1.2 too loose, v2=0.8 too strict)
        if abs(roll) > 1.0 or abs(pitch) > 1.0:
            return True
        return False

    def close(self):
        if self._physics_client is not None:
            p.disconnect(physicsClientId=self._physics_client)
            self._physics_client = None
