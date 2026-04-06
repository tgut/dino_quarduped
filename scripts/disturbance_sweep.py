#!/usr/bin/env python3
"""
Disturbance rejection stress test.
Apply lateral pushes of increasing force to find survival threshold.
Tests both trot and crawl gaits.
"""
import pybullet as p
import pybullet_data
import numpy as np
import os, sys

sys.path.insert(0, os.path.dirname(__file__))
from sim_standalone import (
    URDF_PATH, LEG_JOINTS, JOINT_MAP,
    leg_ik, TrotGait, CrawlGait, set_joint_angles,
)

DT = 1.0 / 240
YAW_KP, YAW_KI, YAW_KD = 0.15, 0.08, 0.02
MAX_HIP_OFFSET, MAX_INTEGRAL = 0.30, 3.0


def test_push(gait_class, gait_kwargs, push_force, push_dir="lateral",
              push_time=5.0, duration=12.0, push_duration=0.1):
    """Run simulation with a push and check survival."""
    pid = p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(DT)
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.loadURDF("plane.urdf")

    JOINT_MAP.clear()
    robot = p.loadURDF(URDF_PATH, [0, 0, 0.25],
                       p.getQuaternionFromEuler([0, 0, 0]), useFixedBase=False)
    for i in range(p.getNumJoints(robot)):
        info = p.getJointInfo(robot, i)
        JOINT_MAP[info[1].decode("utf-8")] = i

    gait = gait_class(**gait_kwargs)

    yaw_prev = yaw_integral = 0.0
    t = 0.0
    push_step = int(push_time / DT)
    push_steps = int(push_duration / DT)
    min_h_post = 999.0
    max_roll_post = 0.0
    recovery_time = None
    pre_push_h = None

    # Force direction
    if push_dir == "lateral":
        force_vec = [0, push_force, 0]
    elif push_dir == "frontal":
        force_vec = [push_force, 0, 0]
    elif push_dir == "diagonal":
        f = push_force / np.sqrt(2)
        force_vec = [f, f, 0]
    else:
        force_vec = [0, push_force, 0]

    for step in range(int(duration / DT)):
        # PID yaw correction
        _, orn = p.getBasePositionAndOrientation(robot)
        euler = p.getEulerFromQuaternion(orn)
        yaw_error = euler[2]
        yaw_rate = (yaw_error - yaw_prev) / DT
        yaw_integral = np.clip(yaw_integral + yaw_error * DT, -MAX_INTEGRAL, MAX_INTEGRAL)
        yaw_prev = yaw_error
        hip_offset = np.clip(
            YAW_KP * yaw_error + YAW_KI * yaw_integral + YAW_KD * yaw_rate,
            -MAX_HIP_OFFSET, MAX_HIP_OFFSET)
        foot_dx = np.clip(hip_offset * 0.05, -0.015, 0.015)

        foot_positions = gait.get_foot_positions(t)
        for leg_name, (fx, fy, fz) in foot_positions.items():
            side = "left" if leg_name.endswith("l") else "right"
            if leg_name.startswith("f"):
                fx += foot_dx
            else:
                fx -= foot_dx
            try:
                hip_a, shoulder_a, knee_a = leg_ik(fx, fy, fz, side=side)
                if side == "left":
                    hip_a += hip_offset
                else:
                    hip_a -= hip_offset
                set_joint_angles(robot, leg_name, (hip_a, shoulder_a, knee_a))
            except:
                pass

        # Apply push
        if push_step <= step < push_step + push_steps:
            p.applyExternalForce(robot, -1, force_vec, [0, 0, 0], p.LINK_FRAME)

        p.stepSimulation()
        t += DT

        pos, _ = p.getBasePositionAndOrientation(robot)
        h = pos[2]
        r = abs(np.degrees(euler[0]))

        if step == push_step - 1:
            pre_push_h = h

        if step > push_step + push_steps:
            if h < min_h_post:
                min_h_post = h
            if r > max_roll_post:
                max_roll_post = r
            if pre_push_h and not recovery_time and h > pre_push_h * 0.9:
                recovery_time = t - push_time

    pos, orn = p.getBasePositionAndOrientation(robot)
    euler = p.getEulerFromQuaternion(orn)
    p.disconnect()

    survived = pos[2] > 0.08 and abs(np.degrees(euler[0])) < 60
    return {
        "survived": survived,
        "min_h": round(min_h_post, 4),
        "max_roll": round(max_roll_post, 1),
        "recovery_s": round(recovery_time, 3) if recovery_time else None,
        "final_h": round(pos[2], 4),
    }


if __name__ == "__main__":
    print("=" * 80)
    print("  DISTURBANCE REJECTION STRESS TEST")
    print("=" * 80)

    gaits = {
        "Trot (optimized)": (TrotGait, dict(step_length=0.06, step_height=0.05, body_height=0.15, period=0.5)),
        "Crawl": (CrawlGait, dict(step_length=0.03, step_height=0.025, body_height=0.15, period=2.4)),
    }

    forces = [1, 2, 3, 5, 7, 10, 12, 15, 20]
    directions = ["lateral", "frontal", "diagonal"]

    for gait_name, (gait_cls, gait_kw) in gaits.items():
        print(f"\n{'─'*80}")
        print(f"  Gait: {gait_name}")
        print(f"{'─'*80}")
        print(f"  {'Force':>6} {'Direction':>10} │ {'Survived':>8} {'MinH':>7} {'MaxRoll':>8} {'Recovery':>9} {'FinalH':>7}")
        print(f"  {'─'*6} {'─'*10} ┼ {'─'*8} {'─'*7} {'─'*8} {'─'*9} {'─'*7}")

        max_survived = {}  # direction → max force survived

        for direction in directions:
            for force in forces:
                r = test_push(gait_cls, gait_kw, force, push_dir=direction)
                status = "OK" if r["survived"] else "FELL"
                rec = f"{r['recovery_s']:.3f}s" if r['recovery_s'] else "N/A"
                print(f"  {force:5}N {direction:>10} │ {status:>8} {r['min_h']:7.4f} {r['max_roll']:7.1f}° "
                      f"{rec:>9} {r['final_h']:7.4f}")
                if r["survived"]:
                    max_survived[direction] = force

        print(f"\n  Max survived push:")
        for d, f in max_survived.items():
            print(f"    {d}: {f}N")

    print(f"\n{'='*80}")
    print("  DONE")
    print("=" * 80)
