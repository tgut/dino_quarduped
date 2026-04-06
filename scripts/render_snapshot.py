#!/usr/bin/env python3
"""
Render snapshots of the Dino Quadruped in PyBullet (headless).
Outputs PNG images to logs/ directory.
"""

import pybullet as p
import pybullet_data
import numpy as np
from PIL import Image
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from sim_standalone import leg_ik, LEG_JOINTS, JOINT_MAP, TrotGait

URDF_PATH = os.path.join(os.path.dirname(__file__), "..", "urdf", "dino_quadruped.urdf")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")


def render_camera(robot, cam_distance, cam_yaw, cam_pitch, cam_target, width=800, height=600):
    """Render a single camera view."""
    view_matrix = p.computeViewMatrixFromYawPitchRoll(
        cameraTargetPosition=cam_target,
        distance=cam_distance,
        yaw=cam_yaw,
        pitch=cam_pitch,
        roll=0,
        upAxisIndex=2,
    )
    proj_matrix = p.computeProjectionMatrixFOV(
        fov=60, aspect=width / height, nearVal=0.01, farVal=10.0
    )
    _, _, rgb, depth, seg = p.getCameraImage(
        width, height, view_matrix, proj_matrix,
        renderer=p.ER_TINY_RENDERER,
    )
    rgb_array = np.array(rgb, dtype=np.uint8).reshape(height, width, 4)
    return rgb_array[:, :, :3]  # drop alpha


def setup_sim():
    """Initialize simulation and load robot."""
    physics_client = p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(1.0 / 240)
    p.setAdditionalSearchPath(pybullet_data.getDataPath())

    # Ground plane
    p.loadURDF("plane.urdf")

    # Robot
    robot = p.loadURDF(
        URDF_PATH,
        basePosition=[0, 0, 0.25],
        baseOrientation=p.getQuaternionFromEuler([0, 0, 0]),
        useFixedBase=False,
    )

    # Build joint map
    for i in range(p.getNumJoints(robot)):
        info = p.getJointInfo(robot, i)
        JOINT_MAP[info[1].decode("utf-8")] = i

    return physics_client, robot


def set_leg_angles(robot, leg_name, angles):
    """Apply joint angles to a leg."""
    hip_a, shoulder_a, knee_a = angles
    joint_names = LEG_JOINTS[leg_name]
    for jname, angle in zip(joint_names, [hip_a, shoulder_a, knee_a]):
        if jname in JOINT_MAP:
            p.setJointMotorControl2(
                robot, JOINT_MAP[jname],
                controlMode=p.POSITION_CONTROL,
                targetPosition=angle,
                force=5.0, maxVelocity=10.0,
            )


def simulate_and_render():
    """Run simulation, let robot stand, then render snapshots."""
    physics_client, robot = setup_sim()

    # Apply standing pose
    body_height = 0.15
    for leg_name in LEG_JOINTS:
        side = "left" if leg_name.endswith("l") else "right"
        angles = leg_ik(0.0, 0.0, -body_height, side=side)
        set_leg_angles(robot, leg_name, angles)

    # Let physics settle
    print("Simulating 2 seconds to settle...")
    for _ in range(480):  # 2 seconds at 240Hz
        p.stepSimulation()

    pos, _ = p.getBasePositionAndOrientation(robot)
    cam_target = list(pos)
    print(f"Robot position: {pos}")

    # Render from multiple angles
    views = [
        ("front_perspective", 0.45, 30, -25),
        ("side_view", 0.45, 90, -20),
        ("top_down", 0.50, 30, -75),
        ("rear_perspective", 0.45, 210, -25),
    ]

    saved_files = []
    for name, dist, yaw, pitch in views:
        img = render_camera(robot, dist, yaw, pitch, cam_target)
        filepath = os.path.join(OUTPUT_DIR, f"dino_{name}.png")
        Image.fromarray(img).save(filepath)
        saved_files.append(filepath)
        print(f"  Saved: {filepath}")

    # Also render a trot mid-stride snapshot
    print("\nRendering trot mid-stride...")
    gait = TrotGait(step_length=0.04, step_height=0.03, body_height=0.15, period=0.5)
    t = 0.125  # mid-swing phase
    foot_positions = gait.get_foot_positions(t)
    for leg_name, (fx, fy, fz) in foot_positions.items():
        side = "left" if leg_name.endswith("l") else "right"
        angles = leg_ik(fx, fy, fz, side=side)
        set_leg_angles(robot, leg_name, angles)

    for _ in range(120):  # 0.5s settle
        p.stepSimulation()

    pos2, _ = p.getBasePositionAndOrientation(robot)
    cam_target2 = list(pos2)
    img = render_camera(robot, 0.45, 45, -20, cam_target2)
    filepath = os.path.join(OUTPUT_DIR, "dino_trot_midstride.png")
    Image.fromarray(img).save(filepath)
    saved_files.append(filepath)
    print(f"  Saved: {filepath}")

    p.disconnect()
    print(f"\nDone! {len(saved_files)} images rendered.")
    return saved_files


if __name__ == "__main__":
    simulate_and_render()
