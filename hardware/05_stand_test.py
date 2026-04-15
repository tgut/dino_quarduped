#!/usr/bin/env python3
"""
Step 5: 站立姿态测试
组装完成后，让机器人站起来。
直接复用仿真中的 IK 解算，把角度发给真实舵机。

用法:
    python3 05_stand_test.py                # 默认站立高度 150mm
    python3 05_stand_test.py --height 0.12  # 自定义高度 (米)
    python3 05_stand_test.py --calibrate    # 进入校准模式
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
    SERVO_MIN_US, SERVO_MAX_US, SERVO_MID_US,
    SERVO_DIRECTION, SERVO_OFFSET_US
)

# 复用仿真代码中的 IK
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from sim_standalone import leg_ik


def rad_to_servo_angle(rad, joint_name):
    """
    弧度 -> 舵机角度 (0-270°)
    仿真中 0 rad 对应舵机中位 (135°)
    """
    direction = SERVO_DIRECTION.get(joint_name, 1)
    offset_us = SERVO_OFFSET_US.get(joint_name, 0)
    # 弧度转角度偏移
    deg_offset = math.degrees(rad) * direction
    # 中位 + 偏移
    servo_deg = (SERVO_RANGE_DEG / 2) + deg_offset * (SERVO_RANGE_DEG / 270.0)
    # 加校准偏移
    us_offset_deg = offset_us / (SERVO_MAX_US - SERVO_MIN_US) * SERVO_RANGE_DEG
    servo_deg += us_offset_deg
    return max(0, min(SERVO_RANGE_DEG, servo_deg))


def set_leg_pose(kit, leg_name, hip_rad, shoulder_rad, knee_rad):
    """设置一条腿的三个关节角度。"""
    joints = LEG_CHANNELS[leg_name]
    rads = [hip_rad, shoulder_rad, knee_rad]

    for jname, rad in zip(joints, rads):
        ch = CHANNEL_MAP[jname]
        angle = rad_to_servo_angle(rad, jname)
        kit.servo[ch].angle = angle


def stand(kit, body_height=0.15):
    """让四条腿站立。"""
    print(f"\n站立姿态: 高度 = {body_height * 1000:.0f}mm")

    for leg_name in ["fl", "fr", "rl", "rr"]:
        side = "left" if leg_name.endswith("l") else "right"
        hip_rad, shoulder_rad, knee_rad = leg_ik(0.0, 0.0, -body_height, side=side)
        set_leg_pose(kit, leg_name, hip_rad, shoulder_rad, knee_rad)
        print(f"  {leg_name.upper()}: hip={math.degrees(hip_rad):+6.1f}°"
              f"  shoulder={math.degrees(shoulder_rad):+6.1f}°"
              f"  knee={math.degrees(knee_rad):+6.1f}°")
        time.sleep(0.2)

    print("\n站立完成！")
    print("验证项目:")
    print("  1. 四脚是否均匀着地")
    print("  2. 机身是否水平 (用 04_imu_test.py --check 验证)")
    print("  3. 站立高度是否约 150mm (用尺量地面到机身底板)")


def calibrate_mode(kit):
    """交互式校准：微调每个舵机的偏移量。"""
    print("\n=== 校准模式 ===")
    print("先执行站立，然后逐个调整偏移量")
    print("目标: 所有腿垂直朝下，机身水平\n")

    stand(kit, 0.15)

    print("\n输入格式: <关节名> <偏移微秒>")
    print("例如: fl_shoulder +50  (正值=正转, 负值=反转)")
    print("输入 'show' 查看当前偏移, 'stand' 重新站立, 'save' 保存, 'q' 退出\n")

    while True:
        try:
            cmd = input("校准> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if cmd == 'q':
            break
        elif cmd == 'show':
            for name, offset in SERVO_OFFSET_US.items():
                if offset != 0:
                    print(f"  {name}: {offset:+d} μs")
            if all(v == 0 for v in SERVO_OFFSET_US.values()):
                print("  (所有偏移为 0)")
        elif cmd == 'stand':
            stand(kit, 0.15)
        elif cmd == 'save':
            print("将以下偏移量更新到 servo_config.py 的 SERVO_OFFSET_US:")
            for name, offset in SERVO_OFFSET_US.items():
                if offset != 0:
                    print(f'    "{name}": {offset},')
            print("(请手动更新文件)")
        else:
            parts = cmd.split()
            if len(parts) == 2 and parts[0] in SERVO_OFFSET_US:
                try:
                    offset = int(parts[1])
                    SERVO_OFFSET_US[parts[0]] = offset
                    print(f"  {parts[0]} 偏移设为 {offset:+d} μs")
                    # 立即应用
                    stand(kit, 0.15)
                except ValueError:
                    print("  偏移量必须是整数")
            else:
                print(f"  无效输入。可用关节: {', '.join(CHANNEL_MAP.keys())}")


def main():
    parser = argparse.ArgumentParser(description="站立姿态测试")
    parser.add_argument("--height", type=float, default=0.15,
                        help="站立高度 (米, 默认 0.15)")
    parser.add_argument("--calibrate", action="store_true",
                        help="进入校准模式")
    args = parser.parse_args()

    print("=" * 50)
    print("  Dino Quadruped - 站立测试")
    print("=" * 50)

    kit = ServoKit(channels=16)
    for ch in range(16):
        kit.servo[ch].set_pulse_width_range(SERVO_MIN_US, SERVO_MAX_US)
        kit.servo[ch].actuation_range = SERVO_RANGE_DEG

    if args.calibrate:
        calibrate_mode(kit)
    else:
        stand(kit, args.height)
        input("\n按 Enter 释放舵机...")

    for ch in range(16):
        kit.servo[ch].angle = None
    print("舵机已释放")


if __name__ == "__main__":
    main()
