#!/bin/bash
# 树莓派硬件验证步骤（非舵机部分）
# 在树莓派上执行此脚本

echo "=========================================="
echo " Dino Quadruped 硬件验证"
echo "=========================================="
echo ""

# 步骤 0: 检查 I2C 是否启用
echo "--- 步骤 0: 检查 I2C 状态 ---"
if lsmod | grep -q i2c_bcm2835; then
    echo "✓ I2C 已启用"
else
    echo "✗ I2C 未启用，请执行: sudo raspi-config → Interface Options → I2C → Enable"
    exit 1
fi

# 步骤 1: 使用 i2cdetect 快速扫描
echo ""
echo "--- 步骤 1: I2C 设备扫描 (系统工具) ---"
if command -v i2cdetect >/dev/null 2>&1; then
    sudo i2cdetect -y 1
    echo ""
    echo "预期看到:"
    echo "  0x40 - PCA9685 舵机驱动板"
    echo "  0x68 - MPU6050 IMU 惯性测量单元"
else
    echo "i2cdetect 未安装，执行: sudo apt-get install i2c-tools"
fi

# 步骤 2: 安装 Python 依赖
echo ""
echo "--- 步骤 2: 安装 Python 依赖 ---"
echo "执行: pip3 install smbus2 mpu6050-raspberrypi adafruit-circuitpython-pca9685 adafruit-circuitpython-servokit"
echo ""
read -p "是否现在安装? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pip3 install smbus2 mpu6050-raspberrypi adafruit-circuitpython-pca9685 adafruit-circuitpython-servokit
fi

echo ""
echo "=========================================="
echo " 接下来在 Python 脚本所在目录执行:"
echo "   python3 01_i2c_scan.py      # I2C 详细扫描"
echo "   python3 04_imu_test.py --check  # IMU 快速检查"
echo "=========================================="
