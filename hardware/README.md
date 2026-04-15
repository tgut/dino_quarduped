# 硬件验证脚本

在树莓派上按顺序执行：

```bash
# 0. 安装依赖
pip3 install adafruit-circuitpython-pca9685 adafruit-circuitpython-servokit smbus2 mpu6050-raspberrypi

# 1. I2C 设备扫描（最先跑）
python3 01_i2c_scan.py

# 2. 单个舵机测试（逐个验证12个舵机）
python3 02_servo_test.py --channel 0

# 3. 全部舵机归中（组装前必做）
python3 03_servo_center_all.py

# 4. IMU 数据读取验证
python3 04_imu_test.py

# 5. 站立姿态（组装完成后）
python3 05_stand_test.py

# 6. 行走测试
python3 06_trot_test.py
```
