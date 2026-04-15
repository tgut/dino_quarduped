"""
舵机配置 - 通道映射与 PWM 参数
所有硬件脚本共用此配置。
"""

# PCA9685 I2C 地址
PCA9685_ADDR = 0x40

# PWM 频率 (Hz)
PWM_FREQ = 50

# DS3218 舵机 PWM 参数 (微秒)
SERVO_MIN_US = 500    # 0°
SERVO_MID_US = 1500   # 135° (归中)
SERVO_MAX_US = 2500   # 270°
SERVO_RANGE_DEG = 270  # 总行程角度

# PCA9685 12-bit (4096) 值换算
# pulse_us -> pca_value = (pulse_us / 20000) * 4096
SERVO_MIN_VAL = 102   # 500μs
SERVO_MID_VAL = 307   # 1500μs
SERVO_MAX_VAL = 512   # 2500μs

# 舵机通道映射 (与接线图一致)
CHANNEL_MAP = {
    # 左前腿
    "fl_hip":      0,
    "fl_shoulder": 1,
    "fl_knee":     2,
    # 右前腿
    "fr_hip":      3,
    "fr_shoulder": 4,
    "fr_knee":     5,
    # 左后腿
    "rl_hip":      6,
    "rl_shoulder": 7,
    "rl_knee":     8,
    # 右后腿
    "rr_hip":      9,
    "rr_shoulder": 10,
    "rr_knee":     11,
}

# 按腿分组
LEG_CHANNELS = {
    "fl": ["fl_hip", "fl_shoulder", "fl_knee"],
    "fr": ["fr_hip", "fr_shoulder", "fr_knee"],
    "rl": ["rl_hip", "rl_shoulder", "rl_knee"],
    "rr": ["rr_hip", "rr_shoulder", "rr_knee"],
}

# 舵机安装方向修正 (1=正向, -1=镜像)
# 右侧腿的肩/膝舵机通常需要反向
SERVO_DIRECTION = {
    "fl_hip": 1,  "fl_shoulder": 1,  "fl_knee": 1,
    "fr_hip": -1, "fr_shoulder": -1, "fr_knee": -1,
    "rl_hip": 1,  "rl_shoulder": 1,  "rl_knee": 1,
    "rr_hip": -1, "rr_shoulder": -1, "rr_knee": -1,
}

# 舵机校准偏移量 (微秒) - 组装后根据实际情况调整
# 理想情况下所有为 0，实际需要微调
SERVO_OFFSET_US = {name: 0 for name in CHANNEL_MAP}


def us_to_pca(pulse_us):
    """微秒脉宽 -> PCA9685 12-bit 值"""
    return int((pulse_us / 20000.0) * 4096)


def angle_to_us(angle_deg):
    """角度(0-270) -> 微秒脉宽"""
    return SERVO_MIN_US + (angle_deg / SERVO_RANGE_DEG) * (SERVO_MAX_US - SERVO_MIN_US)


def rad_to_us(angle_rad, joint_name):
    """
    弧度 -> 微秒脉宽 (带方向修正和偏移校准)
    仿真中 0 rad = 归中位置
    """
    import math
    direction = SERVO_DIRECTION.get(joint_name, 1)
    offset = SERVO_OFFSET_US.get(joint_name, 0)
    angle_deg = math.degrees(angle_rad) * direction
    pulse_us = SERVO_MID_US + (angle_deg / SERVO_RANGE_DEG) * (SERVO_MAX_US - SERVO_MIN_US) + offset
    return max(SERVO_MIN_US, min(SERVO_MAX_US, pulse_us))
