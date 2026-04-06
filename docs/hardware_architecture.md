# Dino Quadruped - Hardware Architecture

## System Block Diagram

```
                    ┌─────────────────────────────────────────────┐
                    │              2S 7.4V LiPo                   │
                    │           5000mAh 30C XT60                  │
                    └──────────┬──────────────┬───────────────────┘
                               │              │
                          ┌────┴────┐    ┌────┴────┐
                          │ LM2596  │    │ LM2596  │
                          │ Buck #1 │    │ Buck #2 │
                          │ → 5V 3A │    │ → 6V 5A │
                          └────┬────┘    └────┬────┘
                               │              │
                    ┌──────────┴──┐     ┌─────┴──────────────┐
                    │             │     │                     │
               ┌────┴────┐       │  ┌──┴──────────────┐     │
               │  RPi 3B │       │  │   PCA9685        │     │
               │         │◄─I2C─┤  │  16-ch PWM       │     │
               │  GPIO    │      │  │  Servo Driver    │     │
               │  I2C     │      │  └──┬──┬──┬──┬──┬──┘     │
               │  UART    │      │     │  │  │  │  │         │
               └────┬────┘      │     │  │  │  │  │    6V───┘
                    │           │     │  │  │  │  │
               ┌────┴────┐     │  ┌──┴──┴──┴──┴──┴──────────┐
               │ MPU6050 │     │  │   12× DS3218 Servos      │
               │  IMU    │◄I2C─┘  │   20kg·cm 270°           │
               │ GY-521  │        │                           │
               └─────────┘        │  FL: hip/shoulder/knee    │
                                  │  FR: hip/shoulder/knee    │
                                  │  RL: hip/shoulder/knee    │
                                  │  RR: hip/shoulder/knee    │
                                  └───────────────────────────┘
```

## Power Architecture

```
 Battery 7.4V
     │
     ├──► 10A Power Switch
     │
     ├──► LM2596 #1 ──► 5V 3A ──► Raspberry Pi 3B (via GPIO 5V/GND)
     │                         ├──► PCA9685 VCC (logic, 3.3~5V)
     │                         └──► MPU6050 VCC (3.3~5V)
     │
     └──► LM2596 #2 ──► 6V 5A ──► PCA9685 V+ (servo power rail)
                                └──► 12× DS3218 Servos
```

### Power Budget

| Consumer        | Voltage | Current (typ) | Current (peak) | Notes              |
|-----------------|---------|---------------|----------------|--------------------|
| RPi 3B          | 5V      | 0.7A          | 1.2A           | WiFi + GPIO active |
| PCA9685 logic   | 5V      | 0.01A         | 0.02A          | I2C logic only     |
| MPU6050         | 3.3V    | 0.004A        | 0.004A         | From Pi 3.3V rail  |
| DS3218 ×12 idle | 6V      | 0.6A total    | -              | 50mA each idle     |
| DS3218 ×12 load | 6V      | 3.6A total    | 12A            | 300mA typ, 1A peak |
| **Total**       | -       | **~5A**       | **~13A**       |                    |

- Battery: 5000mAh @ 7.4V → ~37Wh
- Runtime estimate: 37Wh / (6V × 5A) ≈ **60~90 min** (mixed walking)
- Peak current: 12A (all servos stall) — 30C battery = 150A capacity, safe

### Safety Notes

- XT60 connectors rated 60A continuous
- LM2596 #2 (servo rail): 5A continuous, ok for typical load; add heatsink
- Consider upgrade to XL4016 (8A) if servos stall frequently
- Battery low-voltage alarm recommended (2S buzzer, ¥5)

## Communication Bus

### I2C Bus (400kHz)

```
RPi 3B (SDA=GPIO2, SCL=GPIO3)
    │
    ├──► PCA9685   Address: 0x40 (default)
    │    - 16-channel, 12-bit PWM
    │    - 50Hz for servo control
    │    - Channels 0-11 used (12 servos)
    │
    └──► MPU6050   Address: 0x68 (default)
         - 6-axis IMU (accel + gyro)
         - 1kHz internal sample rate
         - Read at 100~200Hz in control loop
```

### Servo Channel Mapping (PCA9685)

| Channel | Joint              | URDF Joint Name      | Servo ID |
|---------|--------------------|----------------------|----------|
| 0       | Front-Left Hip     | fl_hip_joint         | S0       |
| 1       | Front-Left Shoulder| fl_shoulder_joint    | S1       |
| 2       | Front-Left Knee    | fl_knee_joint        | S2       |
| 3       | Front-Right Hip    | fr_hip_joint         | S3       |
| 4       | Front-Right Shoulder| fr_shoulder_joint   | S4       |
| 5       | Front-Right Knee   | fr_knee_joint        | S5       |
| 6       | Rear-Left Hip      | rl_hip_joint         | S6       |
| 7       | Rear-Left Shoulder | rl_shoulder_joint    | S7       |
| 8       | Rear-Left Knee     | rl_knee_joint        | S8       |
| 9       | Rear-Right Hip     | rr_hip_joint         | S9       |
| 10      | Rear-Right Shoulder| rr_shoulder_joint    | S10      |
| 11      | Rear-Right Knee    | rr_knee_joint        | S11      |
| 12-15   | Reserved           | (tail/head future)   | -        |

## Control Loop Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Raspberry Pi 3B                      │
│                                                       │
│  ┌─────────────┐   ┌──────────────┐   ┌───────────┐ │
│  │   Gait      │──►│     IK       │──►│ PCA9685   │─┤──► Servos
│  │  Generator  │   │   Solver     │   │  Driver   │ │
│  │  (Python)   │   │  (Analytical)│   │  (I2C)    │ │
│  └──────┬──────┘   └──────────────┘   └───────────┘ │
│         │                                             │
│  ┌──────┴──────┐                                      │
│  │  IMU Reader │◄─────────────────────────────────────┤──► MPU6050
│  │  + PID      │                                      │
│  │ (Yaw/Pitch) │                                      │
│  └─────────────┘                                      │
│                                                       │
│  Target: 50Hz control loop (20ms per cycle)           │
└──────────────────────────────────────────────────────┘
```

### Software Stack on Pi

```
Layer 3: Gait Planner     (stand/trot/crawl, RL policy future)
Layer 2: IK + PID         (analytical IK, yaw/pitch/roll PID)
Layer 1: HAL Drivers      (PCA9685 PWM, MPU6050 IMU, GPIO)
Layer 0: Linux (Raspbian)  + Python 3.9+
```
