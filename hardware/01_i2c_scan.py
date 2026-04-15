#!/usr/bin/env python3
"""
Step 1: I2C Bus Scanner
扫描 I2C 总线，验证 PCA9685 (0x40) 和 MPU6050 (0x68) 是否在线。
在树莓派上运行，接线完成后第一步执行。
"""

import sys

try:
    import smbus2 as smbus
except ImportError:
    try:
        import smbus
    except ImportError:
        print("[ERROR] 需要安装 smbus2: pip3 install smbus2")
        sys.exit(1)

I2C_BUS = 1  # 树莓派 3B 使用 bus 1

EXPECTED_DEVICES = {
    0x40: "PCA9685 (舵机驱动板)",
    0x68: "MPU6050 (IMU 惯性测量单元)",
}


def scan_i2c(bus_num=I2C_BUS):
    """扫描 I2C 总线上所有设备。"""
    bus = smbus.SMBus(bus_num)
    found = []

    print(f"扫描 I2C 总线 {bus_num}...\n")
    print("     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f")

    for row in range(0, 128, 16):
        line = f"{row:02x}: "
        for col in range(16):
            addr = row + col
            if addr < 0x03 or addr > 0x77:
                line += "   "
                continue
            try:
                bus.read_byte(addr)
                line += f"{addr:02x} "
                found.append(addr)
            except OSError:
                line += "-- "
        print(line)

    bus.close()
    return found


def main():
    print("=" * 60)
    print("  Dino Quadruped - I2C 设备扫描")
    print("=" * 60)

    found = scan_i2c()

    print(f"\n发现 {len(found)} 个设备:")
    for addr in found:
        name = EXPECTED_DEVICES.get(addr, "未知设备")
        print(f"  0x{addr:02x} -> {name}")

    # 检查必要设备
    print("\n" + "-" * 40)
    all_ok = True
    for addr, name in EXPECTED_DEVICES.items():
        if addr in found:
            print(f"  [OK] {name} (0x{addr:02x})")
        else:
            print(f"  [FAIL] {name} (0x{addr:02x}) 未找到!")
            all_ok = False

    if all_ok:
        print("\n所有设备就绪，可以继续下一步！")
    else:
        print("\n[警告] 有设备未检测到，请检查:")
        print("  1. 接线是否正确 (SDA=Pin3, SCL=Pin5, GND=Pin6)")
        print("  2. 是否启用了 I2C: sudo raspi-config → Interfacing → I2C")
        print("  3. 设备是否供电 (PCA9685 需要 5V, MPU6050 需要 3.3V)")
        sys.exit(1)


if __name__ == "__main__":
    main()
