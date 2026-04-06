#!/usr/bin/env python3
"""
Sweep step_length and period to find optimal trot speed.
Constraints: robot must stay upright (height > 0.12m, roll < 20deg).
"""
import pybullet as p
import pybullet_data
import numpy as np
import os, sys

sys.path.insert(0, os.path.dirname(__file__))
from sim_standalone import (
    URDF_PATH, LEG_JOINTS, JOINT_MAP,
    leg_ik, TrotGait, set_joint_angles,
)

DT = 1.0 / 240
DURATION = 15.0
YAW_KP, YAW_KI, YAW_KD = 0.15, 0.08, 0.02
MAX_HIP_OFFSET, MAX_INTEGRAL = 0.30, 3.0


def run_trial(step_length, step_height, period):
    pid = p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(DT)
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.loadURDF("plane.urdf")

    JOINT_MAP.clear()
    robot = p.loadURDF(URDF_PATH, [0, 0, 0.25], p.getQuaternionFromEuler([0, 0, 0]), useFixedBase=False)
    for i in range(p.getNumJoints(robot)):
        info = p.getJointInfo(robot, i)
        JOINT_MAP[info[1].decode("utf-8")] = i

    gait = TrotGait(step_length=step_length, step_height=step_height, body_height=0.15, period=period)

    yaw_prev = yaw_integral = 0.0
    t = 0.0
    min_h = 999.0
    max_roll = 0.0
    fell = False

    for step in range(int(DURATION / DT)):
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
        p.stepSimulation()
        t += DT

        pos, _ = p.getBasePositionAndOrientation(robot)
        h = pos[2]
        r = abs(np.degrees(euler[0]))
        if h < min_h:
            min_h = h
        if r > max_roll:
            max_roll = r
        if h < 0.08 or r > 60:
            fell = True
            break

    final_pos, _ = p.getBasePositionAndOrientation(robot)
    final_euler = p.getEulerFromQuaternion(p.getBasePositionAndOrientation(robot)[1])
    p.disconnect()

    fwd = final_pos[0]
    speed = fwd / (t if t > 0 else 1)
    yaw_final = abs(np.degrees(final_euler[2]))

    return {
        "step_length": step_length,
        "step_height": step_height,
        "period": period,
        "speed_m_s": round(speed, 4),
        "fwd_m": round(fwd, 3),
        "min_h": round(min_h, 4),
        "max_roll": round(max_roll, 1),
        "yaw_final": round(yaw_final, 1),
        "fell": fell,
        "stable": not fell and min_h > 0.10 and max_roll < 20,
    }


if __name__ == "__main__":
    print("=" * 80)
    print("  TROT SPEED PARAMETER SWEEP")
    print("=" * 80)

    configs = []
    for sl in [0.04, 0.06, 0.08, 0.10, 0.12]:
        for sh in [0.03, 0.04, 0.05]:
            for per in [0.3, 0.4, 0.5, 0.6]:
                configs.append((sl, sh, per))

    print(f"\n  Testing {len(configs)} configurations (15s each) ...\n")
    print(f"  {'SL':>5} {'SH':>5} {'Per':>5} | {'Speed':>8} {'Fwd':>6} {'MinH':>6} {'MaxR':>6} {'Yaw':>6} {'Status'}")
    print(f"  {'-'*5} {'-'*5} {'-'*5}   {'-'*8} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*8}")

    results = []
    for sl, sh, per in configs:
        r = run_trial(sl, sh, per)
        results.append(r)
        status = "OK" if r["stable"] else "FELL" if r["fell"] else "UNSTABLE"
        mark = " *" if r["stable"] and r["speed_m_s"] > 0.04 else ""
        print(f"  {sl:5.2f} {sh:5.2f} {per:5.2f} | {r['speed_m_s']:8.4f} {r['fwd_m']:6.3f} "
              f"{r['min_h']:6.4f} {r['max_roll']:6.1f} {r['yaw_final']:6.1f} {status}{mark}")

    # Find best stable config
    stable = [r for r in results if r["stable"]]
    if stable:
        best = max(stable, key=lambda r: r["speed_m_s"])
        print(f"\n  BEST STABLE CONFIG:")
        print(f"    step_length={best['step_length']}, step_height={best['step_height']}, period={best['period']}")
        print(f"    speed={best['speed_m_s']} m/s, forward={best['fwd_m']}m, minH={best['min_h']}m")
    else:
        print("\n  No stable config found!")
