#!/usr/bin/env python3
"""
Step 3: 全部舵机归中
组装前必做！先把所有舵机转到中位，再安装舵机角/连杆。
这样保证机械零位 = 电气零位。

用法:
    python3 03_servo_center_all.py           # 所有12个舵机归中
    python3 03_servo_center_all.py --leg fl  # 只归中左前腿
"""

import argparse
import time
import sys

try:
    from adafruit_servokit import ServoKit
except ImportError:
    print("[ERROR] 需要安装: pip3 install adafruit-circuitpython-servokit")
    sys.exit(1)

from servo_config import (
    CHANNEL_MAP, LEG_CHANNELS, SERVO_RANGE_DEG,
    SERVO_MIN_US, SERVO_MAX_US
)


def main():
    parser = argparse.ArgumentParser(description="舵机全部归中")
    parser.add_argument("--leg", choices=["fl", "fr", "rl", "rr"],
                        help="只归中指定腿")
    args = parser.parse_args()

    print("=" * 50)
    print("  Dino Quadruped - 舵机归中")
    print("=" * 50)
    print()
    print("  [重要] 此脚本将所有舵机转到 135°(中位)")
    print("  请确保腿部连杆尚未锁死，或已断开舵机角")
    print()

    kit = ServoKit(channels=16)
    for ch in range(16):
        kit.servo[ch].set_pulse_width_range(SERVO_MIN_US, SERVO_MAX_US)
        kit.servo[ch].actuation_range = SERVO_RANGE_DEG

    center = SERVO_RANGE_DEG / 2  # 135°

    if args.leg:
        joints = LEG_CHANNELS[args.leg]
        print(f"归中 {args.leg.upper()} 腿:")
    else:
        joints = list(CHANNEL_MAP.keys())
        print("归中全部 12 个舵机:")

    for name in joints:
        ch = CHANNEL_MAP[name]
        print(f"  CH{ch:2d} ({name:15s}) -> {center:.0f}°", end=" ", flush=True)
        kit.servo[ch].angle = center
        time.sleep(0.3)
        print("OK")

    print()
    print("=" * 50)
    print("  全部归中完成！")
    print()
    print("  下一步操作：")
    print("  1. 确认所有舵机已停在中位")
    print("  2. 安装舵机角(horn)，使腿部指向正下方")
    print("  3. 用 M2 自攻螺丝锁紧舵机角")
    print("  4. 组装连杆和脚掌")
    print("=" * 50)

    input("\n按 Enter 释放舵机(松弛)...")
    for ch in range(16):
        kit.servo[ch].angle = None
    print("舵机已释放")


if __name__ == "__main__":
    main()
