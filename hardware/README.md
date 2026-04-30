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

# 测试结果

```bash
# 04 imu测试结果：

pi@raspberrypi:~/hardware $ python3 04_imu_test.py 
==================================================
  Dino Quadruped - IMU 测试
==================================================
[警告] WHO_AM_I = 0x70, 预期 0x68

--- 快速检查 ---
请将机器人水平放置...

  平均加速度: X= +3.02  Y= -1.17  Z= +9.77 m/s²
  总加速度:   10.29 m/s² (理想值: 9.81)
  Roll:  -6.8°  Pitch: -16.7° (水平时应接近 0°)

结果:
  [OK  ] Z 轴读数: 9.77 m/s²
  [FAIL] X/Y 轴漂移: X=3.02, Y=-1.17
  [OK  ] 总 G 值: 10.29 m/s²
  [FAIL] 水平度: roll=-6.8°, pitch=-16.7°

[警告] 有项目未通过，请检查:
  - IMU 是否水平安装
  - 接线是否正确 (3.3V 供电, I2C)
  - 安装方向: 芯片面朝上, X 轴朝前


--- 持续读取 (Ctrl+C 停止) ---

 Accel X  Accel Y  Accel Z  |   Gyro X  Gyro Y  Gyro Z  |    Roll  Pitch
--------------------------------------------------------------------------------
^C -1.02    +1.86    +9.93  |     -1.9    -0.8    -0.4  |    +9.7   +5.8
```