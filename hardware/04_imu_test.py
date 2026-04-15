#!/usr/bin/env python3
"""
Step 4: MPU6050 IMU 测试
读取加速度计和陀螺仪数据，验证 IMU 工作正常。
将机器人放平，Z 轴加速度应接近 +9.8 m/s²。

用法:
    python3 04_imu_test.py              # 持续打印数据
    python3 04_imu_test.py --check      # 快速检查模式
"""

import argparse
import time
import sys
import math

try:
    import smbus2 as smbus
except ImportError:
    try:
        import smbus
    except ImportError:
        print("[ERROR] 需要安装: pip3 install smbus2")
        sys.exit(1)

# MPU6050 寄存器
MPU6050_ADDR = 0x68
PWR_MGMT_1 = 0x6B
ACCEL_XOUT_H = 0x3B
GYRO_XOUT_H = 0x43
WHO_AM_I = 0x75

ACCEL_SCALE = 16384.0  # ±2g 量程
GYRO_SCALE = 131.0     # ±250°/s 量程
G = 9.81


class MPU6050:
    def __init__(self, bus_num=1, addr=MPU6050_ADDR):
        self.bus = smbus.SMBus(bus_num)
        self.addr = addr
        self._init_sensor()

    def _init_sensor(self):
        # 唤醒 (清除 sleep bit)
        self.bus.write_byte_data(self.addr, PWR_MGMT_1, 0x00)
        time.sleep(0.1)

        # 验证 WHO_AM_I
        who = self.bus.read_byte_data(self.addr, WHO_AM_I)
        if who != 0x68:
            print(f"[警告] WHO_AM_I = 0x{who:02x}, 预期 0x68")
        else:
            print(f"[OK] MPU6050 WHO_AM_I = 0x{who:02x}")

    def _read_raw(self, reg):
        """读取 16-bit 有符号值。"""
        high = self.bus.read_byte_data(self.addr, reg)
        low = self.bus.read_byte_data(self.addr, reg + 1)
        value = (high << 8) | low
        if value > 32767:
            value -= 65536
        return value

    def read_accel(self):
        """读取加速度 (m/s²)。"""
        ax = self._read_raw(ACCEL_XOUT_H) / ACCEL_SCALE * G
        ay = self._read_raw(ACCEL_XOUT_H + 2) / ACCEL_SCALE * G
        az = self._read_raw(ACCEL_XOUT_H + 4) / ACCEL_SCALE * G
        return ax, ay, az

    def read_gyro(self):
        """读取角速度 (°/s)。"""
        gx = self._read_raw(GYRO_XOUT_H) / GYRO_SCALE
        gy = self._read_raw(GYRO_XOUT_H + 2) / GYRO_SCALE
        gz = self._read_raw(GYRO_XOUT_H + 4) / GYRO_SCALE
        return gx, gy, gz

    def read_roll_pitch(self):
        """从加速度计计算 roll/pitch (°)。"""
        ax, ay, az = self.read_accel()
        roll = math.degrees(math.atan2(ay, az))
        pitch = math.degrees(math.atan2(-ax, math.sqrt(ay**2 + az**2)))
        return roll, pitch


def quick_check(imu):
    """快速检查：读几次数据，判断是否正常。"""
    print("\n--- 快速检查 ---")
    print("请将机器人水平放置...\n")
    time.sleep(1)

    readings = []
    for i in range(10):
        ax, ay, az = imu.read_accel()
        readings.append((ax, ay, az))
        time.sleep(0.05)

    avg_ax = sum(r[0] for r in readings) / len(readings)
    avg_ay = sum(r[1] for r in readings) / len(readings)
    avg_az = sum(r[2] for r in readings) / len(readings)

    total_g = math.sqrt(avg_ax**2 + avg_ay**2 + avg_az**2)

    print(f"  平均加速度: X={avg_ax:+6.2f}  Y={avg_ay:+6.2f}  Z={avg_az:+6.2f} m/s²")
    print(f"  总加速度:   {total_g:.2f} m/s² (理想值: 9.81)")

    roll, pitch = imu.read_roll_pitch()
    print(f"  Roll: {roll:+5.1f}°  Pitch: {pitch:+5.1f}° (水平时应接近 0°)")

    # 判定
    checks = []
    checks.append(("Z 轴读数", 8.5 < avg_az < 11.0, f"{avg_az:.2f} m/s²"))
    checks.append(("X/Y 轴漂移", abs(avg_ax) < 1.5 and abs(avg_ay) < 1.5,
                    f"X={avg_ax:.2f}, Y={avg_ay:.2f}"))
    checks.append(("总 G 值", 9.0 < total_g < 10.5, f"{total_g:.2f} m/s²"))
    checks.append(("水平度", abs(roll) < 10 and abs(pitch) < 10,
                    f"roll={roll:.1f}°, pitch={pitch:.1f}°"))

    print("\n结果:")
    all_ok = True
    for name, ok, detail in checks:
        status = "OK" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"  [{status:4s}] {name}: {detail}")

    if all_ok:
        print("\nIMU 工作正常！")
    else:
        print("\n[警告] 有项目未通过，请检查:")
        print("  - IMU 是否水平安装")
        print("  - 接线是否正确 (3.3V 供电, I2C)")
        print("  - 安装方向: 芯片面朝上, X 轴朝前")


def continuous_mode(imu):
    """持续打印 IMU 数据。"""
    print("\n--- 持续读取 (Ctrl+C 停止) ---\n")
    print(f"{'Accel X':>8s} {'Accel Y':>8s} {'Accel Z':>8s}  |"
          f"  {'Gyro X':>7s} {'Gyro Y':>7s} {'Gyro Z':>7s}  |"
          f"  {'Roll':>6s} {'Pitch':>6s}")
    print("-" * 80)

    try:
        while True:
            ax, ay, az = imu.read_accel()
            gx, gy, gz = imu.read_gyro()
            roll, pitch = imu.read_roll_pitch()
            print(f"{ax:+8.2f} {ay:+8.2f} {az:+8.2f}  |"
                  f"  {gx:+7.1f} {gy:+7.1f} {gz:+7.1f}  |"
                  f"  {roll:+6.1f} {pitch:+6.1f}",
                  end="\r", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n\n已停止")


def main():
    parser = argparse.ArgumentParser(description="MPU6050 IMU 测试")
    parser.add_argument("--check", action="store_true", help="快速检查模式")
    args = parser.parse_args()

    print("=" * 50)
    print("  Dino Quadruped - IMU 测试")
    print("=" * 50)

    imu = MPU6050()

    if args.check:
        quick_check(imu)
    else:
        quick_check(imu)
        print()
        continuous_mode(imu)


if __name__ == "__main__":
    main()
