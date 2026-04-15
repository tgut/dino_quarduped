#!/usr/bin/env python3
"""
Step 6: Trot 步态行走测试
让机器人以 trot 步态行走。直接复用仿真中的 TrotGait。

用法:
    python3 06_trot_test.py                    # 默认参数行走
    python3 06_trot_test.py --duration 10      # 走 10 秒
    python3 06_trot_test.py --step-length 0.03 # 小步幅
    python3 06_trot_test.py --slow             # 慢速模式 (首次推荐)

安全提示:
    首次测试请用 --slow，并准备随时拔电源！
    确保已通过 05_stand_test.py 验证站立正常。
"""

import argparse
import math
import time
import sys
import os

try:
    from adafruit_servokit import ServoKit
except ImportError:
    print("[ERROR] 需要安装: pip3 install adafruit-circuitpython-servokit")
    sys.exit(1)

from servo_config import (
    CHANNEL_MAP, LEG_CHANNELS, SERVO_RANGE_DEG,
    SERVO_MIN_US, SERVO_MAX_US, SERVO_DIRECTION, SERVO_OFFSET_US
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from sim_standalone import leg_ik, TrotGait


def rad_to_servo_angle(rad, joint_name):
    """弧度 -> 舵机角度 (0-270°)"""
    direction = SERVO_DIRECTION.get(joint_name, 1)
    offset_us = SERVO_OFFSET_US.get(joint_name, 0)
    deg_offset = math.degrees(rad) * direction
    servo_deg = (SERVO_RANGE_DEG / 2) + deg_offset * (SERVO_RANGE_DEG / 270.0)
    us_offset_deg = offset_us / (SERVO_MAX_US - SERVO_MIN_US) * SERVO_RANGE_DEG
    servo_deg += us_offset_deg
    return max(0, min(SERVO_RANGE_DEG, servo_deg))


def set_all_legs(kit, foot_positions):
    """一次性设置四条腿的位置。"""
    for leg_name, (fx, fy, fz) in foot_positions.items():
        side = "left" if leg_name.endswith("l") else "right"
        hip_rad, shoulder_rad, knee_rad = leg_ik(fx, fy, fz, side=side)
        joints = LEG_CHANNELS[leg_name]
        rads = [hip_rad, shoulder_rad, knee_rad]

        for jname, rad in zip(joints, rads):
            ch = CHANNEL_MAP[jname]
            angle = rad_to_servo_angle(rad, jname)
            kit.servo[ch].angle = angle


def main():
    parser = argparse.ArgumentParser(description="Trot 步态行走测试")
    parser.add_argument("--duration", type=float, default=5.0,
                        help="行走时长 (秒, 默认 5)")
    parser.add_argument("--step-length", type=float, default=0.04,
                        help="步幅 (米, 默认 0.04)")
    parser.add_argument("--step-height", type=float, default=0.03,
                        help="抬腿高度 (米, 默认 0.03)")
    parser.add_argument("--body-height", type=float, default=0.15,
                        help="站立高度 (米, 默认 0.15)")
    parser.add_argument("--period", type=float, default=0.5,
                        help="步态周期 (秒, 默认 0.5)")
    parser.add_argument("--freq", type=float, default=50.0,
                        help="控制频率 (Hz, 默认 50)")
    parser.add_argument("--slow", action="store_true",
                        help="慢速模式 (步幅减半, 周期加倍)")
    args = parser.parse_args()

    if args.slow:
        args.step_length *= 0.5
        args.period *= 2.0
        args.step_height *= 0.7

    print("=" * 50)
    print("  Dino Quadruped - Trot 步态测试")
    print("=" * 50)
    print(f"  步幅:     {args.step_length * 1000:.1f} mm")
    print(f"  抬腿:     {args.step_height * 1000:.1f} mm")
    print(f"  周期:     {args.period:.2f} s")
    print(f"  站高:     {args.body_height * 1000:.0f} mm")
    print(f"  时长:     {args.duration:.1f} s")
    print(f"  控制频率: {args.freq:.0f} Hz")
    if args.slow:
        print(f"  [慢速模式]")

    kit = ServoKit(channels=16)
    for ch in range(16):
        kit.servo[ch].set_pulse_width_range(SERVO_MIN_US, SERVO_MAX_US)
        kit.servo[ch].actuation_range = SERVO_RANGE_DEG

    # 先站起来
    print("\n1. 站立...")
    gait = TrotGait(
        step_length=args.step_length,
        step_height=args.step_height,
        body_height=args.body_height,
        period=args.period,
    )
    standing = gait.get_foot_positions(0.0)
    set_all_legs(kit, standing)
    time.sleep(1.5)

    # 开始行走
    input("2. 准备好后按 Enter 开始行走 (Ctrl+C 随时停止)...")
    print("   行走中...")

    dt = 1.0 / args.freq
    t = 0.0
    start_time = time.time()
    step_count = 0

    try:
        while (time.time() - start_time) < args.duration:
            loop_start = time.time()

            foot_positions = gait.get_foot_positions(t)
            set_all_legs(kit, foot_positions)

            t += dt
            step_count += 1

            # 控制循环定时
            elapsed = time.time() - loop_start
            sleep_time = dt - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n   [手动停止]")

    actual_duration = time.time() - start_time
    actual_freq = step_count / actual_duration if actual_duration > 0 else 0

    # 恢复站立
    print("\n3. 恢复站立...")
    set_all_legs(kit, standing)
    time.sleep(1.0)

    print(f"\n统计:")
    print(f"  实际时长: {actual_duration:.1f} s")
    print(f"  控制周期: {step_count} 次")
    print(f"  实际频率: {actual_freq:.1f} Hz")

    input("\n按 Enter 释放舵机...")
    for ch in range(16):
        kit.servo[ch].angle = None
    print("完成!")


if __name__ == "__main__":
    main()
