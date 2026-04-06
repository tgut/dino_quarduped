#!/usr/bin/env python3
"""Diagnose yaw drift: check FK foot positions and force symmetry."""
import pybullet as p
import pybullet_data
import numpy as np
import os, sys

sys.path.insert(0, os.path.dirname(__file__))
from sim_standalone import leg_ik, LEG_JOINTS, JOINT_MAP, TrotGait

URDF_PATH = os.path.join(os.path.dirname(__file__), "..", "urdf", "dino_quadruped.urdf")

c = p.connect(p.DIRECT)
p.setGravity(0, 0, -9.81)
p.setTimeStep(1.0/240)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.loadURDF("plane.urdf")
robot = p.loadURDF(URDF_PATH, [0, 0, 0.25], useFixedBase=True)

JOINT_MAP.clear()
for i in range(p.getNumJoints(robot)):
    info = p.getJointInfo(robot, i)
    JOINT_MAP[info[1].decode("utf-8")] = i

# Print joint axes and origins
print("=== Joint Info ===")
for leg in ["fl", "fr", "rl", "rr"]:
    print(f"\n{leg}:")
    for jname in LEG_JOINTS[leg]:
        idx = JOINT_MAP[jname]
        info = p.getJointInfo(robot, idx)
        axis = info[13]
        parent_pos = info[14]
        parent_orn = info[15]
        print(f"  {jname}: axis={axis}, parent_frame_pos={parent_pos}")

# Apply standing pose
print("\n=== Standing FK ===")
for leg in LEG_JOINTS:
    side = "left" if leg.endswith("l") else "right"
    angles = leg_ik(0.0, 0.0, -0.15, side=side)
    for jname, angle in zip(LEG_JOINTS[leg], angles):
        p.resetJointState(robot, JOINT_MAP[jname], angle)

for leg in ["fl", "fr", "rl", "rr"]:
    foot_idx = JOINT_MAP[f"{leg}_foot_joint"]
    state = p.getLinkState(robot, foot_idx)
    pos = state[0]
    print(f"  {leg} foot: ({pos[0]:+.4f}, {pos[1]:+.4f}, {pos[2]:.4f})")

# Check trot: compare forces at multiple time steps
print("\n=== Trot Force Symmetry ===")
gait = TrotGait(step_length=0.04, step_height=0.03, body_height=0.15, period=0.5)
for t in [0.0, 0.0625, 0.125, 0.1875, 0.25, 0.375, 0.5]:
    foot_pos = gait.get_foot_positions(t)
    positions = {}
    for leg in LEG_JOINTS:
        side = "left" if leg.endswith("l") else "right"
        fx, fy, fz = foot_pos[leg]
        angles = leg_ik(fx, fy, fz, side=side)
        for jname, angle in zip(LEG_JOINTS[leg], angles):
            p.resetJointState(robot, JOINT_MAP[jname], angle)
        foot_idx = JOINT_MAP[f"{leg}_foot_joint"]
        state = p.getLinkState(robot, foot_idx)
        positions[leg] = state[0]

    # Check x-symmetry: fl vs fr, rl vs rr
    fl_x, fr_x = positions["fl"][0], positions["fr"][0]
    rl_x, rr_x = positions["rl"][0], positions["rr"][0]
    fl_z, fr_z = positions["fl"][2], positions["fr"][2]
    rl_z, rr_z = positions["rl"][2], positions["rr"][2]
    print(f"  t={t:.4f} | fl_x={fl_x:+.4f} fr_x={fr_x:+.4f} dx={fl_x-fr_x:+.5f} | fl_z={fl_z:.4f} fr_z={fr_z:.4f} dz={fl_z-fr_z:+.5f}")

# Dynamic sim: track per-step yaw change
print("\n=== Dynamic Yaw Tracking (free-floating) ===")
p.disconnect()

c = p.connect(p.DIRECT)
p.setGravity(0, 0, -9.81)
p.setTimeStep(1.0/240)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.loadURDF("plane.urdf")
robot = p.loadURDF(URDF_PATH, [0, 0, 0.25], useFixedBase=False)

JOINT_MAP.clear()
for i in range(p.getNumJoints(robot)):
    info = p.getJointInfo(robot, i)
    JOINT_MAP[info[1].decode("utf-8")] = i

# Settle in standing
for leg in LEG_JOINTS:
    side = "left" if leg.endswith("l") else "right"
    angles = leg_ik(0.0, 0.0, -0.15, side=side)
    for jname, angle in zip(LEG_JOINTS[leg], angles):
        p.setJointMotorControl2(robot, JOINT_MAP[jname], p.POSITION_CONTROL,
                                targetPosition=angle, force=5.0, maxVelocity=10.0)
for _ in range(480):
    p.stepSimulation()

# Trot with detailed tracking
t = 0.0
dt = 1.0/240
prev_yaw = 0.0
for step in range(1200):  # 5 seconds
    foot_pos = gait.get_foot_positions(t)
    for leg in LEG_JOINTS:
        side = "left" if leg.endswith("l") else "right"
        fx, fy, fz = foot_pos[leg]
        angles = leg_ik(fx, fy, fz, side=side)
        for jname, angle in zip(LEG_JOINTS[leg], angles):
            p.setJointMotorControl2(robot, JOINT_MAP[jname], p.POSITION_CONTROL,
                                    targetPosition=angle, force=5.0, maxVelocity=10.0)
    p.stepSimulation()
    t += dt

    if step % 240 == 0:
        pos, orn = p.getBasePositionAndOrientation(robot)
        euler = p.getEulerFromQuaternion(orn)
        yaw = np.degrees(euler[2])
        yaw_rate = yaw - prev_yaw
        prev_yaw = yaw

        # Get contact points
        contacts = p.getContactPoints(robot)
        contact_legs = set()
        for cp in contacts:
            link_idx = cp[3]
            for leg, joints in LEG_JOINTS.items():
                foot_name = f"{leg}_foot_joint"
                if foot_name in JOINT_MAP and JOINT_MAP[foot_name] == link_idx:
                    contact_legs.add(leg)

        print(f"  t={t:.1f}s yaw={yaw:+6.1f} d_yaw={yaw_rate:+5.1f}/s contacts={contact_legs}")

p.disconnect()
