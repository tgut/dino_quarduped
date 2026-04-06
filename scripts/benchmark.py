#!/usr/bin/env python3
"""
Dino Quadruped — Comprehensive Performance Benchmark
=====================================================
Tests 6 representative metrics:
  1. Static Stability    — CoM height holding under standing
  2. Dynamic Stability   — roll/pitch bounds during trot
  3. Locomotion Speed    — forward velocity (m/s)
  4. Heading Accuracy    — yaw drift after PID correction
  5. Cost of Transport   — energy efficiency (lower = better)
  6. Disturbance Rejection — recovery from lateral push
"""

import pybullet as p
import pybullet_data
import numpy as np
import os, sys, json, time

# Reuse core from sim_standalone
sys.path.insert(0, os.path.dirname(__file__))
from sim_standalone import (
    URDF_PATH, LEG_JOINTS, JOINT_MAP,
    leg_ik, TrotGait, StandPose, set_joint_angles,
)

DT = 1.0 / 240

# Yaw PID (same as sim_standalone)
YAW_KP, YAW_KI, YAW_KD = 0.15, 0.08, 0.02
MAX_HIP_OFFSET = 0.30
MAX_INTEGRAL = 3.0


def load_robot():
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.loadURDF("plane.urdf")
    robot = p.loadURDF(
        URDF_PATH,
        basePosition=[0, 0, 0.25],
        baseOrientation=p.getQuaternionFromEuler([0, 0, 0]),
        useFixedBase=False,
    )
    JOINT_MAP.clear()
    for i in range(p.getNumJoints(robot)):
        info = p.getJointInfo(robot, i)
        JOINT_MAP[info[1].decode("utf-8")] = i
    return robot


def get_state(robot):
    pos, orn = p.getBasePositionAndOrientation(robot)
    vel, ang_vel = p.getBaseVelocity(robot)
    euler = p.getEulerFromQuaternion(orn)
    return {
        "pos": np.array(pos),
        "euler": np.array(euler),
        "vel": np.array(vel),
        "ang_vel": np.array(ang_vel),
    }


def step_trot(robot, gait, t, yaw_prev, yaw_integral):
    """One sim step of trot with PID yaw correction. Returns (t, yaw_prev, yaw_integral, torque_sum)."""
    _, orn = p.getBasePositionAndOrientation(robot)
    euler = p.getEulerFromQuaternion(orn)
    yaw_error = euler[2]

    yaw_rate = (yaw_error - yaw_prev) / DT
    yaw_integral = np.clip(yaw_integral + yaw_error * DT, -MAX_INTEGRAL, MAX_INTEGRAL)
    yaw_prev = yaw_error

    hip_offset = np.clip(
        YAW_KP * yaw_error + YAW_KI * yaw_integral + YAW_KD * yaw_rate,
        -MAX_HIP_OFFSET, MAX_HIP_OFFSET,
    )
    foot_dx = np.clip(hip_offset * 0.05, -0.015, 0.015)

    foot_positions = gait.get_foot_positions(t)
    torque_sum = 0.0

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

    # Measure total joint torque for energy calculation
    for leg_name in LEG_JOINTS:
        for jname in LEG_JOINTS[leg_name]:
            if jname in JOINT_MAP:
                js = p.getJointState(robot, JOINT_MAP[jname])
                torque_sum += abs(js[3])  # applied motor torque

    return t + DT, yaw_prev, yaw_integral, torque_sum


def step_stand(robot, stand):
    foot_positions = stand.get_foot_positions()
    for leg_name, (fx, fy, fz) in foot_positions.items():
        side = "left" if leg_name.endswith("l") else "right"
        angles = leg_ik(fx, fy, fz, side=side)
        set_joint_angles(robot, leg_name, angles)
    p.stepSimulation()


# =====================================================================
# Test 1: Static Stability — standing height maintenance
# =====================================================================
def test_static_stability(duration=5.0):
    pid = p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(DT)
    robot = load_robot()
    stand = StandPose(body_height=0.15)

    heights = []
    steps = int(duration / DT)
    for i in range(steps):
        step_stand(robot, stand)
        if i % 24 == 0:
            s = get_state(robot)
            heights.append(s["pos"][2])

    p.disconnect()

    h_arr = np.array(heights)
    settled = h_arr[len(h_arr)//4:]  # skip first 25% for settling
    return {
        "name": "Static Stability",
        "metric": "CoM Height",
        "mean_height_m": round(float(np.mean(settled)), 4),
        "height_std_m": round(float(np.std(settled)), 5),
        "min_height_m": round(float(np.min(settled)), 4),
        "pass": bool(np.min(settled) > 0.12 and np.std(settled) < 0.005),
    }


# =====================================================================
# Test 2: Dynamic Stability — roll/pitch during trot
# =====================================================================
def test_dynamic_stability(duration=15.0):
    pid = p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(DT)
    robot = load_robot()
    gait = TrotGait(step_length=0.04, step_height=0.03, body_height=0.15, period=0.5)

    rolls, pitches, heights = [], [], []
    yaw_prev = 0.0
    yaw_integral = 0.0
    t = 0.0
    steps = int(duration / DT)

    for i in range(steps):
        t, yaw_prev, yaw_integral, _ = step_trot(robot, gait, t, yaw_prev, yaw_integral)
        if i % 24 == 0:
            s = get_state(robot)
            rolls.append(np.degrees(s["euler"][0]))
            pitches.append(np.degrees(s["euler"][1]))
            heights.append(s["pos"][2])

    p.disconnect()

    r, pi, h = np.array(rolls), np.array(pitches), np.array(heights)
    # Skip settling period
    r, pi, h = r[len(r)//5:], pi[len(pi)//5:], h[len(h)//5:]
    return {
        "name": "Dynamic Stability",
        "metric": "Roll/Pitch bounds during trot",
        "roll_max_deg": round(float(np.max(np.abs(r))), 2),
        "pitch_max_deg": round(float(np.max(np.abs(pi))), 2),
        "roll_std_deg": round(float(np.std(r)), 3),
        "pitch_std_deg": round(float(np.std(pi)), 3),
        "min_height_m": round(float(np.min(h)), 4),
        "pass": bool(np.max(np.abs(r)) < 15 and np.max(np.abs(pi)) < 15 and np.min(h) > 0.10),
    }


# =====================================================================
# Test 3: Locomotion Speed
# =====================================================================
def test_locomotion_speed(duration=20.0):
    pid = p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(DT)
    robot = load_robot()
    gait = TrotGait(step_length=0.04, step_height=0.03, body_height=0.15, period=0.5)

    yaw_prev = 0.0
    yaw_integral = 0.0
    t = 0.0
    steps = int(duration / DT)

    for i in range(steps):
        t, yaw_prev, yaw_integral, _ = step_trot(robot, gait, t, yaw_prev, yaw_integral)

    s = get_state(robot)
    dist = np.linalg.norm(s["pos"][:2])  # 2D distance
    fwd_dist = s["pos"][0]
    speed = fwd_dist / duration

    p.disconnect()

    return {
        "name": "Locomotion Speed",
        "metric": "Forward velocity",
        "forward_distance_m": round(float(fwd_dist), 3),
        "total_2d_distance_m": round(float(dist), 3),
        "avg_speed_m_per_s": round(float(speed), 4),
        "avg_speed_body_len_per_s": round(float(speed / 0.20), 2),  # normalized by body length
        "pass": bool(speed > 0.01),
    }


# =====================================================================
# Test 4: Heading Accuracy (Yaw Drift)
# =====================================================================
def test_heading_accuracy(duration=30.0):
    pid = p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(DT)
    robot = load_robot()
    gait = TrotGait(step_length=0.04, step_height=0.03, body_height=0.15, period=0.5)

    yaw_history = []
    yaw_prev = 0.0
    yaw_integral = 0.0
    t = 0.0
    steps = int(duration / DT)

    for i in range(steps):
        t, yaw_prev, yaw_integral, _ = step_trot(robot, gait, t, yaw_prev, yaw_integral)
        if i % 240 == 0:  # every 1s
            s = get_state(robot)
            yaw_history.append(np.degrees(s["euler"][2]))

    p.disconnect()

    yaw_arr = np.array(yaw_history)
    peak_yaw = float(np.max(np.abs(yaw_arr)))
    final_yaw = float(yaw_arr[-1])
    # Lateral deviation per meter forward
    s = get_state(robot) if False else None  # already disconnected

    return {
        "name": "Heading Accuracy",
        "metric": "Yaw control with PID",
        "peak_yaw_deg": round(peak_yaw, 2),
        "final_yaw_deg": round(final_yaw, 2),
        "yaw_at_10s_deg": round(float(yaw_arr[10]) if len(yaw_arr) > 10 else 0, 2),
        "yaw_at_20s_deg": round(float(yaw_arr[20]) if len(yaw_arr) > 20 else 0, 2),
        "converged": bool(abs(final_yaw) < 10),
        "pass": bool(abs(final_yaw) < 15),
    }


# =====================================================================
# Test 5: Cost of Transport (Energy Efficiency)
# =====================================================================
def test_cost_of_transport(duration=20.0):
    pid = p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(DT)
    robot = load_robot()
    gait = TrotGait(step_length=0.04, step_height=0.03, body_height=0.15, period=0.5)

    yaw_prev = 0.0
    yaw_integral = 0.0
    t = 0.0
    steps = int(duration / DT)
    total_torque = 0.0
    total_power = 0.0

    for i in range(steps):
        t, yaw_prev, yaw_integral, torque = step_trot(robot, gait, t, yaw_prev, yaw_integral)
        total_torque += torque

        # Approximate power: sum of |torque * joint_velocity| for all joints
        power_step = 0.0
        for leg_name in LEG_JOINTS:
            for jname in LEG_JOINTS[leg_name]:
                if jname in JOINT_MAP:
                    js = p.getJointState(robot, JOINT_MAP[jname])
                    power_step += abs(js[3] * js[1])  # |torque * velocity|
        total_power += power_step * DT

    s = get_state(robot)
    fwd_dist = max(s["pos"][0], 0.001)

    # Robot mass (body=1.0 + 4*(hip0.1+upper0.15+lower0.1+foot0.02) = 1.0 + 4*0.37 = 2.48 kg)
    mass = 2.48
    g = 9.81
    # CoT = Energy / (mass * g * distance)
    cot = total_power / (mass * g * fwd_dist)

    p.disconnect()

    return {
        "name": "Cost of Transport",
        "metric": "Energy / (m*g*d)",
        "total_energy_J": round(float(total_power), 3),
        "forward_distance_m": round(float(fwd_dist), 3),
        "CoT": round(float(cot), 2),
        "CoT_rating": "Excellent" if cot < 5 else "Good" if cot < 15 else "Fair" if cot < 50 else "Poor",
        "pass": bool(cot < 100),  # biological reference: ~1-5 for animals
    }


# =====================================================================
# Test 6: Disturbance Rejection — lateral push during trot
# =====================================================================
def test_disturbance_rejection(duration=15.0, push_time=5.0, push_force=3.0):
    pid = p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(DT)
    robot = load_robot()
    gait = TrotGait(step_length=0.04, step_height=0.03, body_height=0.15, period=0.5)

    yaw_prev = 0.0
    yaw_integral = 0.0
    t = 0.0
    steps = int(duration / DT)
    push_step = int(push_time / DT)
    push_duration_steps = int(0.1 / DT)  # 100ms impulse

    pre_push_height = None
    min_height_after_push = 999.0
    max_roll_after_push = 0.0
    recovered = False
    recovery_time = None

    for i in range(steps):
        t, yaw_prev, yaw_integral, _ = step_trot(robot, gait, t, yaw_prev, yaw_integral)

        # Apply lateral push
        if push_step <= i < push_step + push_duration_steps:
            p.applyExternalForce(robot, -1, [0, push_force, 0], [0, 0, 0], p.LINK_FRAME)

        # Record pre-push state
        if i == push_step - 1:
            s = get_state(robot)
            pre_push_height = s["pos"][2]

        # Track post-push metrics
        if i > push_step + push_duration_steps:
            s = get_state(robot)
            min_height_after_push = min(min_height_after_push, s["pos"][2])
            max_roll_after_push = max(max_roll_after_push, abs(np.degrees(s["euler"][0])))

            # Check recovery (height back within 90% of pre-push)
            if not recovered and s["pos"][2] > pre_push_height * 0.9:
                recovered = True
                recovery_time = t - push_time

    s = get_state(robot)
    survived = s["pos"][2] > 0.10

    p.disconnect()

    return {
        "name": "Disturbance Rejection",
        "metric": f"Lateral push {push_force}N for 100ms at t={push_time}s",
        "survived": survived,
        "min_height_after_push_m": round(float(min_height_after_push), 4),
        "max_roll_after_push_deg": round(float(max_roll_after_push), 2),
        "recovered": recovered,
        "recovery_time_s": round(float(recovery_time), 3) if recovery_time else None,
        "pass": survived,
    }


# =====================================================================
# Main — Run All Tests
# =====================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("  DINO QUADRUPED — COMPREHENSIVE PERFORMANCE BENCHMARK")
    print("=" * 70)

    tests = [
        ("1/6", test_static_stability),
        ("2/6", test_dynamic_stability),
        ("3/6", test_locomotion_speed),
        ("4/6", test_heading_accuracy),
        ("5/6", test_cost_of_transport),
        ("6/6", test_disturbance_rejection),
    ]

    results = []
    for label, test_fn in tests:
        print(f"\n[{label}] Running: {test_fn.__name__} ...")
        t0 = time.time()
        result = test_fn()
        elapsed = time.time() - t0
        result["elapsed_s"] = round(elapsed, 1)
        results.append(result)
        status = "PASS" if result["pass"] else "FAIL"
        print(f"  [{status}] {result['name']} ({elapsed:.1f}s)")
        for k, v in result.items():
            if k not in ("name", "pass", "elapsed_s", "metric"):
                print(f"    {k}: {v}")

    # Summary table
    print("\n" + "=" * 70)
    print("  BENCHMARK SUMMARY")
    print("=" * 70)
    print(f"  {'Test':<28} {'Status':<8} {'Key Metric'}")
    print(f"  {'-'*28} {'-'*8} {'-'*32}")

    summary_data = {
        "Static Stability": ("mean_height_m", "m"),
        "Dynamic Stability": ("roll_max_deg", "deg max roll"),
        "Locomotion Speed": ("avg_speed_m_per_s", "m/s"),
        "Heading Accuracy": ("final_yaw_deg", "deg final yaw"),
        "Cost of Transport": ("CoT", "CoT"),
        "Disturbance Rejection": ("recovery_time_s", "s recovery"),
    }

    passed = 0
    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        if r["pass"]:
            passed += 1
        key = summary_data.get(r["name"], (None, ""))
        val = r.get(key[0], "N/A") if key[0] else "—"
        print(f"  {r['name']:<28} {status:<8} {val} {key[1]}")

    print(f"\n  Total: {passed}/{len(results)} passed")
    print("=" * 70)

    # Save results
    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "benchmark_results.json")
    with open(log_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Full results saved to: {log_path}")
