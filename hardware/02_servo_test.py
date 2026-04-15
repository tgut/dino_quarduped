#!/usr/bin/env python3
"""
Step 2: 单舵机测试
逐个验证舵机是否正常工作。
用法:
    python3 02_servo_test.py                 # 交互模式，测试所有通道
    python3 02_servo_test.py --channel 0     # 测试指定通道
    python3 02_servo_test.py --channel 0 --sweep  # 全行程扫描
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
    CHANNEL_MAP, SERVO_MIN_US, SERVO_MID_US, SERVO_MAX_US,
    PWM_FREQ, SERVO_RANGE_DEG
)


def create_kit():
    """初始化 PCA9685 ServoKit。"""
    kit = ServoKit(channels=16)
    for ch in range(16):
        kit.servo[ch].set_pulse_width_range(SERVO_MIN_US, SERVO_MAX_US)
        kit.servo[ch].actuation_range = SERVO_RANGE_DEG
    return kit


def test_single(kit, channel):
    """测试单个通道：归中 → 左转 → 右转 → 归中。"""
    center = SERVO_RANGE_DEG / 2  # 135°
    print(f"\n--- 测试通道 CH{channel} ---")

    # 查找对应关节名
    name = "未知"
    for jname, ch in CHANNEL_MAP.items():
        if ch == channel:
            name = jname
            break
    print(f"  关节: {name}")

    print(f"  归中 ({center:.0f}°)...", end=" ", flush=True)
    kit.servo[channel].angle = center
    time.sleep(0.8)
    print("OK")

    print(f"  左转 ({center - 45:.0f}°)...", end=" ", flush=True)
    kit.servo[channel].angle = center - 45
    time.sleep(0.8)
    print("OK")

    print(f"  右转 ({center + 45:.0f}°)...", end=" ", flush=True)
    kit.servo[channel].angle = center + 45
    time.sleep(0.8)
    print("OK")

    print(f"  回归中...", end=" ", flush=True)
    kit.servo[channel].angle = center
    time.sleep(0.5)
    print("OK")


def sweep_test(kit, channel, step=5, delay=0.03):
    """全行程扫描测试。"""
    print(f"\n--- 全行程扫描 CH{channel} (0° → {SERVO_RANGE_DEG}° → 0°) ---")

    # 正向扫描
    for angle in range(0, SERVO_RANGE_DEG + 1, step):
        kit.servo[channel].angle = angle
        time.sleep(delay)

    time.sleep(0.3)

    # 反向扫描
    for angle in range(SERVO_RANGE_DEG, -1, -step):
        kit.servo[channel].angle = angle
        time.sleep(delay)

    # 归中
    kit.servo[channel].angle = SERVO_RANGE_DEG / 2
    print("  扫描完成，已归中")


def interactive_mode(kit):
    """交互模式，逐个测试。"""
    print("\n=== 交互模式 ===")
    print("可用通道:")
    for name, ch in sorted(CHANNEL_MAP.items(), key=lambda x: x[1]):
        print(f"  CH{ch:2d} = {name}")

    while True:
        try:
            cmd = input("\n输入通道号 (0-11), 's'扫描, 'a'测试全部, 'q'退出: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if cmd.lower() == 'q':
            break
        elif cmd.lower() == 'a':
            for ch in range(12):
                test_single(kit, ch)
                time.sleep(0.3)
        elif cmd.lower().startswith('s'):
            parts = cmd.split()
            ch = int(parts[1]) if len(parts) > 1 else 0
            sweep_test(kit, ch)
        else:
            try:
                ch = int(cmd)
                if 0 <= ch <= 15:
                    test_single(kit, ch)
                else:
                    print("通道范围: 0-15")
            except ValueError:
                print("无效输入")


def main():
    parser = argparse.ArgumentParser(description="DS3218 舵机测试")
    parser.add_argument("--channel", "-c", type=int, help="指定测试通道 (0-15)")
    parser.add_argument("--sweep", "-s", action="store_true", help="全行程扫描")
    parser.add_argument("--all", "-a", action="store_true", help="测试所有12个通道")
    args = parser.parse_args()

    print("=" * 50)
    print("  Dino Quadruped - 舵机测试")
    print("=" * 50)

    kit = create_kit()
    print("[OK] PCA9685 初始化成功")

    if args.channel is not None:
        if args.sweep:
            sweep_test(kit, args.channel)
        else:
            test_single(kit, args.channel)
    elif args.all:
        for ch in range(12):
            test_single(kit, ch)
            time.sleep(0.3)
        print("\n全部测试完成！")
    else:
        interactive_mode(kit)

    # 释放所有舵机 (断开 PWM 信号，舵机松弛)
    print("\n释放所有舵机...")
    for ch in range(16):
        kit.servo[ch].angle = None
    print("完成")


if __name__ == "__main__":
    main()
