#!/usr/bin/env python3
"""
Dino Quadruped - PyBullet Standalone Simulation
Headless (DIRECT mode) simulation with IK, stand, and trot gait.
"""

import pybullet as p
import pybullet_data
import numpy as np
import time
import os
import json

# ============================================================
# Robot Configuration
# ============================================================
URDF_PATH = os.path.join(os.path.dirname(__file__), "..", "urdf", "dino_quadruped.urdf")

# Leg dimensions (meters) - must match URDF
L_HIP = 0.04      # hip offset (lateral)
L_UPPER = 0.10    # upper leg length
L_LOWER = 0.10    # lower leg length

# Leg mounting positions relative to body center [x, y] (meters)
LEG_ORIGINS = {
    "fl": ( 0.08,  0.095),   # front-left  (x, y with hip offset)
    "fr": ( 0.08, -0.095),   # front-right
    "rl": (-0.08,  0.095),   # rear-left
    "rr": (-0.08, -0.095),   # rear-right
}

# Joint name → PyBullet joint index mapping (populated at load time)
JOINT_MAP = {}

# Joint names per leg (order: hip, shoulder, knee)
LEG_JOINTS = {
    "fl": ["fl_hip_joint", "fl_shoulder_joint", "fl_knee_joint"],
    "fr": ["fr_hip_joint", "fr_shoulder_joint", "fr_knee_joint"],
    "rl": ["rl_hip_joint", "rl_shoulder_joint", "rl_knee_joint"],
    "rr": ["rr_hip_joint", "rr_shoulder_joint", "rr_knee_joint"],
}


# ============================================================
# Inverse Kinematics (Analytical, 3-DOF per leg)
# ============================================================
def leg_ik(x, y, z, side="left"):
    """
    Analytical IK for a single 3-DOF leg.

    Input: foot position (x, y, z) in hip-local frame
           x = forward, y = lateral (outward positive for left),
           z = vertical (negative = down)
    Output: (hip_angle, shoulder_angle, knee_angle) in radians
    """
    # Hip angle (abduction) - project to sagittal plane
    d_yz = np.sqrt(y**2 + z**2)
    hip_angle = np.arctan2(y, -z)
    if side == "right":
        hip_angle = -hip_angle

    # Sagittal plane distance from shoulder to foot
    dz_eff = -d_yz
    dx = x

    r = np.sqrt(dx**2 + dz_eff**2)
    r = np.clip(r, 0.001, L_UPPER + L_LOWER - 0.001)

    # Knee angle (law of cosines)
    cos_knee = (L_UPPER**2 + L_LOWER**2 - r**2) / (2 * L_UPPER * L_LOWER)
    cos_knee = np.clip(cos_knee, -1, 1)
    knee_angle = -(np.pi - np.arccos(cos_knee))

    # Shoulder angle
    alpha = np.arctan2(-dz_eff, dx)
    cos_beta = (L_UPPER**2 + r**2 - L_LOWER**2) / (2 * L_UPPER * r)
    cos_beta = np.clip(cos_beta, -1, 1)
    beta = np.arccos(cos_beta)
    shoulder_angle = alpha - beta

    return (hip_angle, shoulder_angle, knee_angle)


# ============================================================
# Gait Generator
# ============================================================
class TrotGait:
    """Trot gait with yaw correction: diagonal legs move together."""

    def __init__(self, step_length=0.04, step_height=0.03, body_height=0.15, period=0.5):
        self.step_length = step_length
        self.step_height = step_height
        self.body_height = body_height
        self.period = period
        # Yaw correction (applied externally via hip offsets)
        # Kept here for reference; actual correction in simulation loop

        # Phase offsets: diagonal legs in sync
        self.phase_offsets = {
            "fl": 0.0,
            "rr": 0.0,    # FL and RR in phase
            "fr": 0.5,
            "rl": 0.5,    # FR and RL in phase (opposite)
        }

    def get_foot_positions(self, t, yaw_error=0.0):
        """
        Return dict of {leg_name: (x, y, z)} in leg-local frame at time t.
        """
        positions = {}
        for leg_name, phase_offset in self.phase_offsets.items():
            phase = ((t / self.period) + phase_offset) % 1.0
            x, z = self._foot_trajectory(phase)
            positions[leg_name] = (x, 0.0, z)
        return positions

    def _foot_trajectory(self, phase):
        """
        Single foot trajectory in sagittal plane.
        phase 0~0.5: swing (foot in air)
        phase 0.5~1: stance (foot on ground)
        """
        if phase < 0.5:
            # Swing phase: semicircle-like trajectory
            swing_phase = phase / 0.5  # 0 → 1
            x = self.step_length * (0.5 - swing_phase)
            z_lift = self.step_height * np.sin(swing_phase * np.pi)
            z = -self.body_height + z_lift
        else:
            # Stance phase: linear push backward
            stance_phase = (phase - 0.5) / 0.5  # 0 → 1
            x = self.step_length * (-0.5 + stance_phase)
            z = -self.body_height
        return x, z


class CrawlGait:
    """Crawl gait: one leg swings at a time, three support. Most stable.
    Includes body shift toward support triangle center for stability."""

    # Leg positions relative to body center (sign conventions)
    LEG_POS = {
        "fl": (+1, +1),  # front-left
        "rr": (-1, -1),  # rear-right
        "fr": (+1, -1),  # front-right
        "rl": (-1, +1),  # rear-left
    }

    def __init__(self, step_length=0.03, step_height=0.025, body_height=0.15, period=2.4):
        self.step_length = step_length
        self.step_height = step_height
        self.body_height = body_height
        self.period = period
        # Crawl order: FL → RR → FR → RL (maximizes stability triangle)
        self.phase_offsets = {
            "fl": 0.00,
            "rr": 0.25,
            "fr": 0.50,
            "rl": 0.75,
        }
        self.swing_fraction = 0.20  # 20% swing, 80% stance
        self.body_shift = 0.012     # lateral/forward shift toward support triangle

    def get_foot_positions(self, t, yaw_error=0.0):
        """Returns foot positions with body shift compensation."""
        # Determine which leg is currently swinging
        swing_leg = None
        for leg_name, phase_offset in self.phase_offsets.items():
            phase = ((t / self.period) + phase_offset) % 1.0
            if phase < self.swing_fraction:
                swing_leg = leg_name
                break

        # Compute body shift: move body AWAY from swing leg (toward support triangle)
        body_dx, body_dy = 0.0, 0.0
        if swing_leg:
            sx, sy = self.LEG_POS[swing_leg]
            body_dx = -sx * self.body_shift  # shift body opposite to swing leg
            body_dy = -sy * self.body_shift

        positions = {}
        for leg_name, phase_offset in self.phase_offsets.items():
            phase = ((t / self.period) + phase_offset) % 1.0
            x, z = self._foot_trajectory(phase)
            # Apply body shift as foot offset (opposite sign: body moves left = feet move right)
            positions[leg_name] = (x - body_dx, -body_dy, z)
        return positions

    def _foot_trajectory(self, phase):
        sf = self.swing_fraction
        if phase < sf:
            # Swing: foot moves forward (negative x → positive x)
            swing_phase = phase / sf
            x = self.step_length * (-0.5 + swing_phase)
            z_lift = self.step_height * np.sin(swing_phase * np.pi)
            z = -self.body_height + z_lift
        else:
            # Stance: foot pushes backward (positive x → negative x)
            stance_phase = (phase - sf) / (1.0 - sf)
            x = self.step_length * (0.5 - stance_phase)
            z = -self.body_height
        return x, z


class StandPose:
    """Static standing pose."""

    def __init__(self, body_height=0.15):
        self.body_height = body_height

    def get_foot_positions(self, t=0):
        positions = {}
        for leg_name in LEG_JOINTS:
            positions[leg_name] = (0.0, 0.0, -self.body_height)
        return positions


# ============================================================
# Simulation
# ============================================================
def load_robot(physics_client):
    """Load URDF and build joint map."""
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.loadURDF("plane.urdf")

    start_height = 0.25  # start above ground
    robot = p.loadURDF(
        URDF_PATH,
        basePosition=[0, 0, start_height],
        baseOrientation=p.getQuaternionFromEuler([0, 0, 0]),
        useFixedBase=False,
    )

    # Build joint map
    num_joints = p.getNumJoints(robot)
    for i in range(num_joints):
        info = p.getJointInfo(robot, i)
        joint_name = info[1].decode("utf-8")
        JOINT_MAP[joint_name] = i

    print(f"Loaded robot with {num_joints} joints:")
    for name, idx in sorted(JOINT_MAP.items(), key=lambda x: x[1]):
        print(f"  [{idx}] {name}")

    return robot


def set_joint_angles(robot, leg_name, angles):
    """Set joint position targets for a leg."""
    hip_a, shoulder_a, knee_a = angles
    joint_names = LEG_JOINTS[leg_name]

    for jname, angle in zip(joint_names, [hip_a, shoulder_a, knee_a]):
        if jname in JOINT_MAP:
            p.setJointMotorControl2(
                robot, JOINT_MAP[jname],
                controlMode=p.POSITION_CONTROL,
                targetPosition=angle,
                force=5.0,
                maxVelocity=10.0,
            )


def get_body_state(robot):
    """Get body position and orientation."""
    pos, orn = p.getBasePositionAndOrientation(robot)
    euler = p.getEulerFromQuaternion(orn)
    return {
        "position": {"x": pos[0], "y": pos[1], "z": pos[2]},
        "orientation_deg": {
            "roll": np.degrees(euler[0]),
            "pitch": np.degrees(euler[1]),
            "yaw": np.degrees(euler[2]),
        },
    }


def run_simulation(mode="trot", duration=5.0, dt=1.0/240):
    """
    Run headless simulation.
    mode: "stand" or "trot"
    """
    print(f"\n{'='*60}")
    print(f"  Dino Quadruped Simulation - Mode: {mode}")
    print(f"  Duration: {duration}s | Timestep: {dt}s")
    print(f"{'='*60}\n")

    # Connect in DIRECT (headless) mode
    physics_client = p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(dt)

    robot = load_robot(physics_client)

    # Select gait
    if mode == "trot":
        gait = TrotGait(step_length=0.06, step_height=0.05, body_height=0.15, period=0.5)
    elif mode == "crawl":
        gait = CrawlGait(step_length=0.04, step_height=0.03, body_height=0.15, period=2.0)
    else:
        gait = StandPose(body_height=0.15)

    # Simulation log
    log = []
    steps = int(duration / dt)
    report_interval = int(1.0 / dt)  # report every 1 second

    # Yaw PID controller state
    yaw_prev = 0.0
    yaw_integral = 0.0
    YAW_KP = 0.15    # hip angle per radian of yaw error
    YAW_KI = 0.08    # integral gain (eliminates steady-state drift)
    YAW_KD = 0.02    # derivative gain (damping)
    MAX_HIP_OFFSET = 0.30  # max hip correction in radians (~17 deg)
    MAX_INTEGRAL = 3.0     # anti-windup (allow more integral accumulation)

    t = 0.0
    for step in range(steps):
        # Get yaw feedback for trot mode
        yaw_error = 0.0
        hip_offset = 0.0
        if mode in ("trot", "crawl"):
            _, orn = p.getBasePositionAndOrientation(robot)
            euler = p.getEulerFromQuaternion(orn)
            yaw_error = euler[2]  # radians

            # PID controller for hip angle offset
            yaw_rate = (yaw_error - yaw_prev) / dt
            yaw_integral = np.clip(yaw_integral + yaw_error * dt,
                                   -MAX_INTEGRAL, MAX_INTEGRAL)
            yaw_prev = yaw_error

            hip_offset = (YAW_KP * yaw_error +
                          YAW_KI * yaw_integral +
                          YAW_KD * yaw_rate)
            hip_offset = np.clip(hip_offset, -MAX_HIP_OFFSET, MAX_HIP_OFFSET)

        # Get foot targets from gait
        foot_positions = gait.get_foot_positions(t)

        # Foot x-offset for yaw correction (front/rear couple)
        foot_dx = np.clip(hip_offset * 0.05, -0.015, 0.015)

        # IK and apply with yaw correction via hip offsets + foot offsets
        for leg_name, (fx, fy, fz) in foot_positions.items():
            side = "left" if leg_name.endswith("l") else "right"

            # Front/rear differential foot offset creates yaw couple
            if leg_name.startswith("f"):
                fx += foot_dx
            else:
                fx -= foot_dx

            try:
                hip_a, shoulder_a, knee_a = leg_ik(fx, fy, fz, side=side)

                # Apply differential hip offset for yaw correction
                if side == "left":
                    hip_a += hip_offset
                else:
                    hip_a -= hip_offset

                set_joint_angles(robot, leg_name, (hip_a, shoulder_a, knee_a))
            except Exception as e:
                print(f"IK error for {leg_name}: {e}")

        # Step simulation
        p.stepSimulation()
        t += dt

        # Periodic report
        if step % report_interval == 0:
            state = get_body_state(robot)
            log.append({"time": round(t, 2), **state})
            pos = state["position"]
            orn = state["orientation_deg"]
            print(f"  t={t:5.1f}s | pos=({pos['x']:+.3f}, {pos['y']:+.3f}, {pos['z']:.3f}) | "
                  f"roll={orn['roll']:+5.1f} pitch={orn['pitch']:+5.1f} yaw={orn['yaw']:+5.1f}")

    # Final state
    final_state = get_body_state(robot)
    print(f"\n--- Final State ---")
    print(json.dumps(final_state, indent=2))

    # Summary
    final_z = final_state["position"]["z"]
    final_roll = abs(final_state["orientation_deg"]["roll"])
    final_pitch = abs(final_state["orientation_deg"]["pitch"])

    print(f"\n--- Assessment ---")
    if final_z > 0.10:
        print(f"  [OK] Body height: {final_z:.3f}m (above 0.10m threshold)")
    else:
        print(f"  [!!] Body height: {final_z:.3f}m (BELOW 0.10m - robot may have fallen)")

    if final_roll < 15 and final_pitch < 15:
        print(f"  [OK] Orientation stable (roll={final_roll:.1f}, pitch={final_pitch:.1f})")
    else:
        print(f"  [!!] Orientation unstable (roll={final_roll:.1f}, pitch={final_pitch:.1f})")

    # Save log
    log_path = os.path.join(os.path.dirname(__file__), "..", "logs", f"sim_{mode}.json")
    with open(log_path, "w") as f:
        json.dump(log, f, indent=2)
    print(f"\n  Log saved to: {log_path}")

    p.disconnect()
    return log


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Dino Quadruped Simulation")
    parser.add_argument("--mode", choices=["stand", "trot", "crawl"], default="stand",
                        help="Simulation mode: stand or trot")
    parser.add_argument("--duration", type=float, default=5.0,
                        help="Simulation duration in seconds")
    args = parser.parse_args()

    run_simulation(mode=args.mode, duration=args.duration)
