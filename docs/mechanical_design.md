# Dino Quadruped - Mechanical Structure Design

## Overall Dimensions

```
                 ┌─── 200mm ───┐
                 │              │
            ┌────┼──────────────┼────┐
            │    │              │    │  ── 110mm ──
            │    │   Body Plate │    │
            └────┼──────────────┼────┘
                 │              │
                 └──────────────┘

  Side View:
                  ┌──────────────────┐  ← Body plate (60mm tall)
                  │    Electronics   │
                  └──┬──────────┬───┘
                     │          │
              ┌──────┤          ├──────┐  ← Shoulder joints
              │Upper │          │Upper │
              │ Leg  │          │ Leg  │  100mm
              │100mm │          │100mm │
              ├──────┤          ├──────┤  ← Knee joints
              │Lower │          │Lower │
              │ Leg  │          │ Leg  │  100mm
              │100mm │          │100mm │
              ◙──────┘          └──────◙  ← Feet (15mm rubber)
         ─────────────────────────────────── Ground
              │◄── 190mm stance ──►│
              │                    │
              Standing height: ~150mm (from URDF simulation)
```

## Frame Structure

### Body Frame (Acrylic Laser Cut)

Two acrylic plates (3mm thick) sandwiched with standoffs:

```
  Top Plate (3mm acrylic):
  ┌────────────────────────────────────────┐
  │  ○          ○           ○          ○   │  ← M3 standoff holes
  │     ┌──────────┐   ┌──────────┐        │
  │     │ Pi 3B    │   │ Battery  │        │
  │     │ mount    │   │ velcro   │        │
  │     └──────────┘   └──────────┘        │
  │  ○    ┌────────┐                   ○   │
  │       │PCA9685 │   ┌──────┐            │
  │       │ mount  │   │MPU6050│           │
  │       └────────┘   └──────┘            │
  │  ○          ○           ○          ○   │
  └────────────────────────────────────────┘
      200mm × 110mm

  Bottom Plate (3mm acrylic):
  ┌────────────────────────────────────────┐
  │  ◎          ◎           ◎          ◎   │  ← Servo mount holes
  │                                        │  (4 corners for hip servos)
  │  ○          ○           ○          ○   │  ← Standoff holes
  │                                        │
  │        ████████████████████            │  ← Wire channel slots
  │                                        │
  │  ○          ○           ○          ○   │
  │                                        │
  │  ◎          ◎           ◎          ◎   │
  └────────────────────────────────────────┘
      200mm × 110mm

  Standoff spacing: 30mm height (M3 × 30mm brass standoffs)
  Total body height: 3 + 30 + 3 = 36mm
```

### Leg Assembly (Per Leg)

```
  Exploded View (single leg):

  ┌─────────────────────┐
  │  Hip Servo (DS3218)  │  ← Mounted to body bottom plate
  │  Rotation: X-axis    │     with aluminum U-bracket
  └─────────┬───────────┘
            │ servo horn
  ┌─────────┴───────────┐
  │  Hip Bracket         │  ← 3D printed PLA or aluminum U-bracket
  │  (40mm offset)       │     provides lateral offset
  └─────────┬───────────┘
            │
  ┌─────────┴───────────┐
  │  Shoulder Servo      │  ← Mounted sideways in U-bracket
  │  Rotation: Y-axis    │
  └─────────┬───────────┘
            │ servo horn
  ┌─────────┴───────────┐
  │  Upper Leg Link      │  ← Aluminum bracket or 3D printed
  │  Length: 100mm       │     DS3218 mounting holes included
  │  (2× M3 holes each) │
  └─────────┬───────────┘
            │
  ┌─────────┴───────────┐
  │  Knee Servo          │  ← Mounted at upper/lower leg joint
  │  Rotation: Y-axis    │
  └─────────┬───────────┘
            │ servo horn
  ┌─────────┴───────────┐
  │  Lower Leg Link      │  ← Aluminum or 3D printed
  │  Length: 100mm       │
  └─────────┬───────────┘
            │
         ┌──┴──┐
         │Foot │  ← Silicone hemisphere 15mm
         │ Pad │     press-fit or glued
         └─────┘
```

### Joint Detail (Shoulder/Knee)

```
  Cross-section of shoulder joint:

        Upper bracket
       ┌────────────┐
       │  ┌──────┐  │
       │  │Servo │  │
       │  │DS3218│  │  ← Servo body in U-bracket
       │  │      │  │     secured with 4× M3 screws
       │  └──┬───┘  │
       └─────┼──────┘
             │
        ┌────┴────┐
        │ Bearing │  ← MR105ZZ (5×10×4mm)
        │ 5×10×4  │     on opposite side of servo
        └────┬────┘     for dual-support
             │
        ┌────┴────────────────────┐
        │    Upper Leg Link       │
        │    (100mm aluminum)     │
        └─────────────────────────┘
```

## Bill of Structural Materials

### Laser Cut Parts (Acrylic 3mm)

| Part              | Qty | Material       | DXF File       |
|-------------------|-----|----------------|----------------|
| Top body plate    | 1   | Acrylic 3mm    | body_top.dxf   |
| Bottom body plate | 1   | Acrylic 3mm    | body_bottom.dxf|

### 3D Printed Parts (PLA)

| Part              | Qty | Material   | STL File           |
|-------------------|-----|------------|--------------------|
| Hip bracket       | 4   | PLA        | hip_bracket.stl    |
| Upper leg link    | 4   | PLA/Alu    | upper_leg.stl      |
| Lower leg link    | 4   | PLA/Alu    | lower_leg.stl      |
| Servo horn adapter| 12  | PLA        | horn_adapter.stl   |

Note: STL files to be generated from SpotMicro community designs,
modified to match our URDF dimensions. See `cad/` directory (TODO).

### Standard Hardware

| Part                | Spec              | Qty  |
|---------------------|-------------------|------|
| M3×8 socket cap     | Stainless steel   | 60   |
| M3×12 socket cap    | Stainless steel   | 24   |
| M3×30 standoff      | Brass, M/F        | 8    |
| M3 nut              | Stainless steel   | 40   |
| M3 washer           | Stainless steel   | 40   |
| M2×8 self-tapping   | For servo horn    | 24   |
| MR105ZZ bearing     | 5×10×4mm          | 16   |
| Servo U-bracket     | Aluminum, for DS3218 | 12 |
| Silicone foot pad   | Hemisphere 15mm   | 4    |
| Zip ties 100mm      | Nylon             | 50   |
| Velcro strap 20mm   | For battery mount | 2    |

## Assembly Order

```
Phase 1: Body Frame
  1. Laser cut top + bottom acrylic plates
  2. Install 8× M3 standoffs on bottom plate
  3. Mount 4× hip servos to bottom plate corners
  4. Attach top plate

Phase 2: Leg Assembly (×4)
  1. Install shoulder servo in hip bracket
  2. Attach hip bracket to hip servo horn
  3. Attach upper leg link to shoulder servo horn
  4. Install knee servo at upper/lower leg junction
  5. Attach lower leg link to knee servo horn
  6. Press-fit foot pad at bottom

Phase 3: Electronics
  1. Mount PCA9685 on top plate (M2.5 standoffs)
  2. Mount MPU6050 at body center (double-sided tape)
  3. Mount Pi 3B (M2.5 standoffs)
  4. Wire I2C bus (PCA9685 + MPU6050)
  5. Connect all 12 servo cables to PCA9685
  6. Mount LM2596 modules
  7. Wire power (battery → switch → buck converters)
  8. Velcro-strap battery to top plate

Phase 4: Calibration
  1. Power on, verify I2C devices (i2cdetect)
  2. Center all servos (1500μs)
  3. Assemble legs at neutral standing position
  4. Adjust servo horn alignment (0° = straight down)
  5. Run stand test → verify height ~150mm
  6. Run trot test → verify stable forward motion
```

## Center of Mass Analysis

```
  Target CoM: center of body plate, height ~30mm above plate

  Component        Mass(g)  X(mm)  Y(mm)  Z(mm)
  ─────────────────────────────────────────────────
  Body frame       120      0      0      15
  Pi 3B            45       -30    -25    40
  PCA9685          15       -30    10     40
  MPU6050          5        0      0      40
  Battery          280      20     0      30
  LM2596 ×2        30       -40    25     25
  Hip servos ×4    240      ±80    ±55    -5
  Shoulder svos ×4 240      ±80    ±95    -25
  Knee servos ×4   240      ±80    ±95    -125
  Foot pads ×4     20       ±80    ±95    -215
  Wiring/misc      65       0      0      20
  ─────────────────────────────────────────────────
  Total:           ~1300g

  Battery placement is critical for CoM balance.
  Shift battery forward/back to tune pitch stability.
  URDF model uses 1500g total (with future head/tail).
```

## Thermal Considerations

- DS3218 servos: max operating temp 55°C
  - Continuous motion generates heat at joints
  - Aluminum U-brackets act as heatsinks
  - Avoid continuous stall for >5s
- LM2596 #2 (servo rail): 7.4V→6V at 5A = 7W dissipation
  - Must add aluminum heatsink (included on most breakouts)
  - Or upgrade to XL4016 module with better thermal design
- Raspberry Pi 3B: passive heatsink recommended on SoC
