# Dino Quadruped - Wiring Diagram

## Complete Wiring Schematic

```
═══════════════════════════════════════════════════════════════════
                         POWER SECTION
═══════════════════════════════════════════════════════════════════

  ┌──────────────┐    ┌──────────┐
  │  2S LiPo     │    │  10A     │
  │  7.4V 5Ah    ├──►─┤  Power   ├──►─┬───────────────────────┐
  │  XT60 plug   │    │  Switch  │    │                       │
  └──────────────┘    └──────────┘    │ 7.4V Main Rail        │
                                       │                       │
                              ┌────────┴──────┐    ┌──────────┴──────┐
                              │   LM2596 #1   │    │   LM2596 #2    │
                              │  IN: 7.4V     │    │  IN: 7.4V      │
                              │  OUT: 5.0V    │    │  OUT: 6.0V     │
                              │  (adj. trimpot)│    │  (adj. trimpot) │
                              └───────┬───────┘    └───────┬────────┘
                                      │ 5V Rail            │ 6V Servo Rail
                                      │                    │
                              ┌───────┴───────┐    ┌───────┴────────┐
                              │ To Pi + Logic │    │ To PCA9685 V+  │
                              └───────────────┘    └────────────────┘


═══════════════════════════════════════════════════════════════════
                     I2C BUS WIRING
═══════════════════════════════════════════════════════════════════

  Raspberry Pi 3B GPIO Header
  ┌─────────────────────────────────────┐
  │  Pin 1 (3.3V)  ──────► MPU6050 VCC │
  │  Pin 2 (5V)    ──────► PCA9685 VCC │
  │  Pin 3 (SDA/GPIO2) ─┬► PCA9685 SDA│
  │                      └► MPU6050 SDA│
  │  Pin 5 (SCL/GPIO3) ─┬► PCA9685 SCL│
  │                      └► MPU6050 SCL│
  │  Pin 6 (GND)   ──┬──► PCA9685 GND │
  │                   ├──► MPU6050 GND │
  │                   └──► LM2596 GND  │
  │  Pin 9 (GND)   ──────► (spare GND)│
  └─────────────────────────────────────┘

  Note: I2C bus needs 4.7kΩ pull-ups on SDA & SCL
        (PCA9685 breakout usually has them onboard)


═══════════════════════════════════════════════════════════════════
                     PCA9685 CONNECTIONS
═══════════════════════════════════════════════════════════════════

  PCA9685 Board
  ┌────────────────────────────────────────────────────────┐
  │                                                        │
  │  Power Input:                                          │
  │    VCC ◄── 5V (from LM2596 #1, logic power)           │
  │    GND ◄── Common GND                                  │
  │    V+  ◄── 6V (from LM2596 #2, servo power)           │
  │                                                        │
  │  I2C:                                                  │
  │    SDA ◄── Pi GPIO2 (Pin 3)                            │
  │    SCL ◄── Pi GPIO3 (Pin 5)                            │
  │                                                        │
  │  Servo Outputs (3-pin: GND/V+/PWM):                   │
  │  ┌─────────────────────────────────────────────┐       │
  │  │ CH0  ──► FL Hip Servo      (orange=signal)  │       │
  │  │ CH1  ──► FL Shoulder Servo                   │       │
  │  │ CH2  ──► FL Knee Servo                       │       │
  │  │ CH3  ──► FR Hip Servo                        │       │
  │  │ CH4  ──► FR Shoulder Servo                   │       │
  │  │ CH5  ──► FR Knee Servo                       │       │
  │  │ CH6  ──► RL Hip Servo                        │       │
  │  │ CH7  ──► RL Shoulder Servo                   │       │
  │  │ CH8  ──► RL Knee Servo                       │       │
  │  │ CH9  ──► RR Hip Servo                        │       │
  │  │ CH10 ──► RR Shoulder Servo                   │       │
  │  │ CH11 ──► RR Knee Servo                       │       │
  │  │ CH12 ──► (Reserved: Tail)                    │       │
  │  │ CH13 ──► (Reserved: Head tilt)               │       │
  │  │ CH14 ──► (Reserved: Head pan)                │       │
  │  │ CH15 ──► (Reserved: Jaw)                     │       │
  │  └─────────────────────────────────────────────┘       │
  └────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════
                     MPU6050 CONNECTIONS
═══════════════════════════════════════════════════════════════════

  MPU6050 (GY-521 Breakout)
  ┌────────────────────────────────────┐
  │  VCC  ◄── 3.3V (Pi Pin 1)         │
  │  GND  ◄── GND  (Pi Pin 6)         │
  │  SDA  ◄── SDA  (Pi Pin 3/GPIO2)   │
  │  SCL  ◄── SCL  (Pi Pin 5/GPIO3)   │
  │  AD0  ──► GND (address = 0x68)    │
  │  INT  ──► (optional: Pi GPIO17)   │
  │  XDA  ──► NC                       │
  │  XCL  ──► NC                       │
  └────────────────────────────────────┘

  Mounting orientation on robot body:
  ┌─────────────────────┐
  │      MPU6050         │  X-axis → Robot Forward
  │   ┌──────────┐      │  Y-axis → Robot Left
  │   │  X →     │      │  Z-axis → Robot Up
  │   │  Y ↑     │      │
  │   │  Z ⊙ (up)│      │  Mount flat on body plate,
  │   └──────────┘      │  chip side up, header toward rear
  └─────────────────────┘


═══════════════════════════════════════════════════════════════════
                     SERVO WIRING (DS3218)
═══════════════════════════════════════════════════════════════════

  Each DS3218 Servo has 3 wires:
  ┌──────────────────────────────────┐
  │  Brown  (GND)  ──► PCA9685 GND  │  (from V+ 6V rail)
  │  Red    (VCC)  ──► PCA9685 V+   │  (6V servo power)
  │  Orange (Signal)──► PCA9685 PWM │  (channel 0-11)
  └──────────────────────────────────┘

  PWM Parameters:
  - Frequency: 50Hz (20ms period)
  - Pulse range: 500μs ~ 2500μs (DS3218 for 270°)
  - Center: 1500μs = 135° (neutral)
  - Resolution: 12-bit (4096 steps)

  Angle Mapping:
  ┌──────────────────────────────────────────┐
  │  500μs  → 0°     (PCA9685 value: ~102)   │
  │  1500μs → 135°   (PCA9685 value: ~307)   │
  │  2500μs → 270°   (PCA9685 value: ~512)   │
  │                                           │
  │  Radians: angle_rad = (pwm_μs - 500)      │
  │           × (270°/2000μs) × (π/180°)      │
  └──────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════
                     PHYSICAL LAYOUT (Top View)
═══════════════════════════════════════════════════════════════════

                        FRONT (head)
                          ▲
           FL             │              FR
     ┌──S0──S1──S2──┐    │    ┌──S3──S4──S5──┐
     │  hip  shl knee│    │    │  hip  shl knee│
     └───────────────┘    │    └───────────────┘
                          │
    ┌─────────────────────┼─────────────────────┐
    │                     │                     │
    │  ┌─────┐  ┌───────┐│  ┌──────┐           │
    │  │ Pi  │  │PCA9685││  │MPU6050│          │
    │  │ 3B  │  │       ││  └──────┘           │
    │  └─────┘  └───────┘│                     │
    │                     │  ┌───────────┐      │
    │  ┌────────┐        │  │  Battery   │      │
    │  │LM2596×2│        │  │  2S LiPo   │      │
    │  └────────┘        │  └───────────┘      │
    │                     │        ┌──┐         │
    │                     │        │SW│ (switch) │
    └─────────────────────┼─────────────────────┘
                          │
     ┌──S6──S7──S8──┐    │    ┌──S9──S10─S11─┐
     │  hip  shl knee│    │    │  hip  shl knee│
     └───────────────┘    │    └───────────────┘
           RL             │              RR
                          ▼
                        REAR (tail)

  Component Placement Notes:
  - Pi 3B: center-left, USB ports facing left for access
  - PCA9685: center, close to all servo extension cables
  - MPU6050: center of body (center of mass), flat mount
  - Battery: center-right (heaviest, keep near CoM)
  - LM2596 modules: stacked or side-by-side near battery
  - Power switch: rear edge, easy access

  Weight Distribution Target:
  - Body + electronics: ~300g (center)
  - Battery: ~280g (center-right)
  - 12 servos × 60g: ~720g (distributed at legs)
  - Total: ~1.5kg (matches URDF mass=1.5)


═══════════════════════════════════════════════════════════════════
                     WIRE ROUTING
═══════════════════════════════════════════════════════════════════

  Servo Extension Cables (30cm each):
  - Route along body underside in cable channels
  - Bundle per leg (3 wires × 4 legs = 12 cables)
  - Use zip ties every 3cm to prevent snagging

  Power Cables (14AWG silicone):
  - Battery → Switch: 10cm, red+black
  - Switch → LM2596 #1: 8cm
  - Switch → LM2596 #2: 8cm
  - LM2596 #2 → PCA9685 V+: 5cm (keep short for current)

  I2C Cables (dupont wires):
  - Pi → PCA9685: 8cm (4 wires: VCC/GND/SDA/SCL)
  - Pi → MPU6050: 6cm (4 wires: VCC/GND/SDA/SCL)
  - Keep I2C wires away from servo power lines (EMI)
