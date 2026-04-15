# CHAMP 框架知识

CHAMP = **C**onfiguration-**H**andled **A**utonomous **M**otion **P**lanner

一个专为 SpotMicro 等小型四足机器人设计的开源 ROS 运动控制框架。
本项目基于 CHAMP 的架构思路，但用 RL 替换了核心步态规划模块。

---

## 1. CHAMP 是什么

CHAMP 是一个完整的四足机器人 ROS 软件栈，提供：
- 步态生成 (Gait Generator)
- 逆运动学求解 (IK Solver)
- 机身姿态控制 (Body Pose Controller)
- 里程计估计 (Odometry)
- 自主导航集成 (Navigation via move_base)

```
传感器输入 (IMU / LiDAR / 里程计)
         ↓
┌──────────────────────────────────────┐
│             CHAMP 框架                │
│                                      │
│  ┌──────────────┐  ┌──────────────┐  │
│  │  步态生成器    │  │  逆运动学     │  │
│  │  Gait        │→│  IK Solver   │  │
│  │  Generator   │  │  (解析解)     │  │
│  └──────────────┘  └──────┬───────┘  │
│                           ↓          │
│  ┌──────────────┐  ┌──────────────┐  │
│  │  姿态控制     │  │  关节控制     │  │
│  │  Body Pose   │  │  Joint       │  │
│  │  Controller  │  │  Publisher    │  │
│  └──────────────┘  └──────────────┘  │
└──────────────────────────────────────┘
         ↓
  /joint_states → 舵机/电机驱动
```

---

## 2. 核心组件详解

### 2.1 步态生成器 (Gait Generator)

生成四条腿的足端轨迹，支持多种步态：

| 步态 | 相位 | 特点 | 速度 |
|------|------|------|------|
| **Walk** | 0-25-50-75 | 始终三脚着地，最稳定 | 慢 |
| **Trot** | 0-50-50-0 | 对角腿同步，效率最高 | 中 |
| **Pace** | 0-50-0-50 | 同侧腿同步 | 中 |
| **Gallop** | 0-10-50-60 | 类似奔跑 | 快 |

步态生成器的核心参数：
```
step_length:  步幅 (前后方向移动距离)
step_height:  抬腿高度 (足端离地最高点)
period:       一个完整步态周期的时间
phase_offset: 各腿的相位差 (决定步态类型)
```

**Trot 步态的数学描述：**

```
对于每条腿，足端在一个周期内的轨迹:

摆动相 (swing, 腿在空中):
  x(t) = step_length * (0.5 - t/T_swing)          // 前后移动
  z(t) = step_height * sin(π * t / T_swing)        // 抬起-落下

支撑相 (stance, 腿在地面):
  x(t) = step_length * (t/T_stance - 0.5)          // 向后推
  z(t) = 0                                         // 贴地

Trot 相位:
  FL 和 RR: phase = 0    (同时摆动)
  FR 和 RL: phase = 0.5  (另一对角同时摆动)
```

### 2.2 逆运动学 (IK Solver)

将足端坐标 (x, y, z) 转换为关节角度 (hip, shoulder, knee)。

CHAMP 使用 **3-DOF 解析解**（不是数值迭代），计算速度极快：

```
输入: 足端目标位置 (x, y, z)，相对于髋关节
输出: (θ_hip, θ_shoulder, θ_knee)

θ_hip = atan2(y, z)                         // 髋关节: 左右摆动

L = sqrt(x² + (sqrt(y² + z²) - L_hip)²)    // 足端到肩关节的距离
φ = atan2(x, sqrt(y² + z²) - L_hip)         // 倾斜角

// 余弦定理求肩关节和膝关节角度
θ_knee = acos((L_upper² + L_lower² - L²) / (2 * L_upper * L_lower))
θ_shoulder = φ + acos((L_upper² + L² - L_lower²) / (2 * L_upper * L))
```

其中：
- `L_hip`: 髋关节到肩关节的偏移距离
- `L_upper`: 大腿长度 (本项目 100mm)
- `L_lower`: 小腿长度 (本项目 100mm)

### 2.3 机身姿态控制 (Body Pose Controller)

允许在行走的同时调整机身姿态：

```
6 维姿态控制:
  - x: 前后平移
  - y: 左右平移
  - z: 上下调整 (站立高度)
  - roll:  翻滚 (左右倾斜)
  - pitch: 俯仰 (前后倾斜)
  - yaw:   偏航 (左右转向)
```

实现方式：对足端坐标做逆变换
```
foot_adjusted = R_body_inverse × (foot_original - body_offset)
```

### 2.4 里程计 (Odometry)

通过足端运动学估计机器人位移：
- 支撑相的腿"推着地面走"
- 通过计算支撑腿的运动来估计机身移动
- 结合 IMU 数据修正漂移

### 2.5 导航 (Navigation)

集成 ROS 标准导航栈：
```
move_base → cmd_vel → CHAMP → joint_states → 舵机
                ↑
            costmap (LiDAR 建图)
```

---

## 3. CHAMP 的 ROS Topic 接口

### 订阅 (输入)

| Topic | 类型 | 说明 |
|-------|------|------|
| `/cmd_vel` | geometry_msgs/Twist | 速度指令 (vx, vy, wz) |
| `/body_pose` | geometry_msgs/Pose | 机身姿态指令 |
| `/imu/data` | sensor_msgs/Imu | IMU 数据 |

### 发布 (输出)

| Topic | 类型 | 频率 | 说明 |
|-------|------|------|------|
| `/joint_states` | sensor_msgs/JointState | 50-100Hz | 12 个关节目标角度 |
| `/odom` | nav_msgs/Odometry | 50Hz | 里程计 |
| `/foot_contacts` | champ_msgs/ContactsStamped | 50Hz | 足端触地状态 |
| `/cmd_pose` | geometry_msgs/PoseArray | 50Hz | 四个足端的目标位置 |

---

## 4. CHAMP 的配置系统

CHAMP 的核心特点是 **配置驱动**——通过 YAML 文件定义机器人参数，无需改代码：

```yaml
# champ_config.yaml
robot:
  base:
    hip_length: 0.04     # 髋关节偏移
    upper_leg: 0.10      # 大腿长度
    lower_leg: 0.10      # 小腿长度
    body_length: 0.20    # 机身长度
    body_width: 0.11     # 机身宽度

  gait:
    max_linear_velocity_x: 0.5
    max_linear_velocity_y: 0.25
    max_angular_velocity_z: 1.0
    stance_duration: 0.25
    swing_height: 0.03
    nominal_height: 0.15

  joints:
    # 每个关节的名称、方向、偏移
    front_left:
      hip: {offset: 0, direction: 1}
      upper_leg: {offset: 0, direction: 1}
      lower_leg: {offset: 0, direction: 1}
    # ... 其他腿
```

---

## 5. 本项目与 CHAMP 的对应关系

| CHAMP 组件 | 本项目对应实现 | 文件位置 |
|-----------|--------------|---------|
| Gait Generator | `TrotGait` 类 | `scripts/sim_standalone.py` |
| IK Solver | `leg_ik()` 函数 | `scripts/sim_standalone.py` |
| Body Pose Controller | 仿真中的 body_height 参数 | `scripts/sim_standalone.py` |
| Joint Publisher | `hardware/05_stand_test.py`, `06_trot_test.py` | `hardware/` |
| Navigation | 未实现 | - |
| Odometry | 未实现 | - |
| **RL 策略** (CHAMP 没有) | PPO v7 模型 | `rl/train_ppo.py` |

### 关键区别

```
CHAMP (传统方法):
  cmd_vel → 步态生成器 (固定规则) → IK → 关节角度
  - 优点: 可预测、可调试、参数明确
  - 缺点: 适应性差、难以处理复杂地形

本项目 (RL 方法):
  观测 (IMU + 关节状态) → PPO 神经网络 → 关节角度
  - 优点: 自适应、可泛化到未见过的地形
  - 缺点: 黑盒、难调试、需要大量仿真训练

混合方案 (推荐):
  1. 用 CHAMP 风格的固定步态做基础验证 (Phase 1)
  2. 用 RL 策略替换步态生成器 (Phase 2)
  3. 保留 IK + 姿态控制作为 fallback
```

---

## 6. CHAMP 的技术栈

```
┌─────────────────────────────────────────────┐
│                 应用层                       │
│  move_base / SLAM / 路径规划                  │
├─────────────────────────────────────────────┤
│                 CHAMP 层                     │
│  步态生成 / IK / 姿态控制 / 里程计             │
├─────────────────────────────────────────────┤
│                 ROS 层                       │
│  topic 通信 / tf 坐标变换 / urdf 模型          │
├─────────────────────────────────────────────┤
│                 硬件抽象层 (HAL)              │
│  ros_control / 舵机驱动 / IMU 驱动            │
├─────────────────────────────────────────────┤
│                 硬件层                       │
│  舵机 / IMU / LiDAR / 电池                   │
└─────────────────────────────────────────────┘
```

### 本项目的简化栈

```
┌─────────────────────────────────────────────┐
│                 控制层                       │
│  TrotGait (固定步态) 或 PPO (RL 策略)          │
├─────────────────────────────────────────────┤
│                 运动学层                     │
│  leg_ik() 逆运动学                           │
├─────────────────────────────────────────────┤
│                 驱动层                       │
│  PCA9685 + adafruit-servokit                │
├─────────────────────────────────────────────┤
│                 硬件层                       │
│  DS3218 舵机 / MPU6050 / 树莓派 3B           │
└─────────────────────────────────────────────┘
```

---

## 7. 如何从本项目迁移到完整 CHAMP

如果后续想接入 ROS 生态（SLAM、导航等），可以：

### Step 1: 安装 CHAMP

```bash
# ROS Noetic
cd ~/catkin_ws/src
git clone --recursive https://github.com/chvmp/champ.git
git clone https://github.com/chvmp/champ_teleop.git
cd ..
catkin_make
```

### Step 2: 配置机器人参数

```bash
rosrun champ_setup_assistant setup_assistant.py
# GUI 工具，输入 URDF 文件和关节参数
# 自动生成 champ_config.yaml
```

### Step 3: 编写硬件接口

需要一个 ROS 节点将 `/joint_states` 转发到 PCA9685：

```python
#!/usr/bin/env python3
"""将 CHAMP 输出的关节角度发送到 PCA9685 舵机。"""

import rospy
from sensor_msgs.msg import JointState
from hardware.servo_config import CHANNEL_MAP, rad_to_us, us_to_pca

def joint_callback(msg):
    for name, position in zip(msg.name, msg.position):
        if name in CHANNEL_MAP:
            ch = CHANNEL_MAP[name]
            pulse_us = rad_to_us(position, name)
            pca.channels[ch].duty_cycle = us_to_pca(pulse_us)

rospy.init_node('dino_hardware_interface')
rospy.Subscriber('/joint_states', JointState, joint_callback)
rospy.spin()
```

### Step 4: 启动

```bash
# 终端 1: CHAMP 核心
roslaunch dino_config bringup.launch

# 终端 2: 键盘遥控
roslaunch champ_teleop teleop.launch

# 终端 3 (工控机): 可视化
roslaunch dino_config rviz.launch
```

---

## 8. CHAMP 生态中的相关项目

| 项目 | 说明 | 链接 |
|------|------|------|
| **champ** | 核心运动控制框架 | github.com/chvmp/champ |
| **champ_teleop** | 键盘/手柄遥控 | github.com/chvmp/champ_teleop |
| **champ_setup_assistant** | GUI 配置工具 | 内含于 champ |
| **SpotMicroAI** | SpotMicro 社区项目 | github.com/mike4192/spotMicro |
| **spot_mini_mini** | 基于 RL 的 SpotMicro | github.com/moribots/spot_mini_mini |
| **OpenQuadruped** | 开源四足平台 | github.com/adham-elarabawy/open-quadruped |

---

## 9. 总结

CHAMP 是"四足机器人的 ROS 运动控制中间件"。本项目：
- **借鉴了 CHAMP 的架构**（步态生成 + IK + 关节控制的分层设计）
- **没有直接使用 CHAMP 代码**（用 Python 重新实现，更轻量）
- **用 RL (PPO) 扩展了 CHAMP 没有的能力**（自适应步态）
- **后续可以桥接回 CHAMP 生态**（接入 ROS 导航/SLAM）
