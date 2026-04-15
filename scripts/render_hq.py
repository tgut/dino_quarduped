#!/usr/bin/env python3
"""
High-quality render of Dino Quadruped using PyBullet.
- 1920x1080 resolution
- Enhanced lighting & shadows
- Multiple cinematic views
- Color-enhanced body parts
"""

import pybullet as p
import pybullet_data
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import sys
import math

sys.path.insert(0, os.path.dirname(__file__))
from sim_standalone import leg_ik, LEG_JOINTS, JOINT_MAP, TrotGait

URDF_PATH = os.path.join(os.path.dirname(__file__), "..", "urdf", "dino_quadruped.urdf")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "hq_renders")

WIDTH, HEIGHT = 1920, 1080


def render_camera(robot, cam_distance, cam_yaw, cam_pitch, cam_target,
                  width=WIDTH, height=HEIGHT, fov=45,
                  light_direction=None, light_color=None):
    """Render with enhanced settings."""
    view_matrix = p.computeViewMatrixFromYawPitchRoll(
        cameraTargetPosition=cam_target,
        distance=cam_distance,
        yaw=cam_yaw,
        pitch=cam_pitch,
        roll=0,
        upAxisIndex=2,
    )
    proj_matrix = p.computeProjectionMatrixFOV(
        fov=fov, aspect=width / height, nearVal=0.01, farVal=10.0
    )

    render_kwargs = dict(
        width=width, height=height,
        viewMatrix=view_matrix,
        projectionMatrix=proj_matrix,
        renderer=p.ER_TINY_RENDERER,
    )
    if light_direction is not None:
        render_kwargs["lightDirection"] = light_direction
    if light_color is not None:
        render_kwargs["lightColor"] = light_color

    _, _, rgb, depth, seg = p.getCameraImage(**render_kwargs)
    rgb_array = np.array(rgb, dtype=np.uint8).reshape(height, width, 4)
    return rgb_array[:, :, :3]


def apply_color_to_links(robot):
    """Apply richer colors to robot parts for better visual."""
    for i in range(p.getNumJoints(robot)):
        info = p.getJointInfo(robot, i)
        name = info[12].decode("utf-8")  # link name
        if "upper_leg" in name:
            # Metallic green for upper legs
            p.changeVisualShape(robot, i, rgbaColor=[0.15, 0.55, 0.15, 1])
        elif "lower_leg" in name:
            # Dark carbon gray for lower legs
            p.changeVisualShape(robot, i, rgbaColor=[0.25, 0.25, 0.28, 1])
        elif "hip" in name:
            # Gunmetal for hip joints
            p.changeVisualShape(robot, i, rgbaColor=[0.35, 0.35, 0.38, 1])
        elif "foot" in name:
            # Warm orange rubber feet
            p.changeVisualShape(robot, i, rgbaColor=[0.95, 0.55, 0.1, 1])

    # Body: rich forest green
    p.changeVisualShape(robot, -1, rgbaColor=[0.12, 0.50, 0.18, 1])


def setup_sim():
    """Initialize simulation with enhanced visuals."""
    physics_client = p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(1.0 / 240)
    p.setAdditionalSearchPath(pybullet_data.getDataPath())

    # Ground plane with checker texture
    plane = p.loadURDF("plane.urdf")
    # Make ground a nice light gray
    p.changeVisualShape(plane, -1, rgbaColor=[0.85, 0.88, 0.90, 1])

    # Robot
    robot = p.loadURDF(
        URDF_PATH,
        basePosition=[0, 0, 0.25],
        baseOrientation=p.getQuaternionFromEuler([0, 0, 0]),
        useFixedBase=False,
    )

    # Build joint map
    JOINT_MAP.clear()
    for i in range(p.getNumJoints(robot)):
        info = p.getJointInfo(robot, i)
        JOINT_MAP[info[1].decode("utf-8")] = i

    apply_color_to_links(robot)

    return physics_client, robot


def set_leg_angles(robot, leg_name, angles):
    """Apply joint angles to a leg."""
    hip_a, shoulder_a, knee_a = angles
    joint_names = LEG_JOINTS[leg_name]
    for jname, angle in zip(joint_names, [hip_a, shoulder_a, knee_a]):
        if jname in JOINT_MAP:
            p.setJointMotorControl2(
                robot, JOINT_MAP[jname],
                controlMode=p.POSITION_CONTROL,
                targetPosition=angle,
                force=5.0, maxVelocity=10.0,
            )


def set_standing_pose(robot, body_height=0.15):
    """Set all legs to standing pose."""
    for leg_name in LEG_JOINTS:
        side = "left" if leg_name.endswith("l") else "right"
        angles = leg_ik(0.0, 0.0, -body_height, side=side)
        set_leg_angles(robot, leg_name, angles)


def set_trot_pose(robot, t=0.125):
    """Set trot gait mid-stride pose."""
    gait = TrotGait(step_length=0.04, step_height=0.03, body_height=0.15, period=0.5)
    foot_positions = gait.get_foot_positions(t)
    for leg_name, (fx, fy, fz) in foot_positions.items():
        side = "left" if leg_name.endswith("l") else "right"
        angles = leg_ik(fx, fy, fz, side=side)
        set_leg_angles(robot, leg_name, angles)


def settle(steps=480):
    """Let physics settle."""
    for _ in range(steps):
        p.stepSimulation()


def add_watermark(img_array, text):
    """Add subtle text label to image."""
    img = Image.fromarray(img_array)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except (IOError, OSError):
        font = ImageFont.load_default()

    # Semi-transparent overlay
    x, y = 30, HEIGHT - 50
    draw.text((x + 1, y + 1), text, fill=(0, 0, 0), font=font)  # shadow
    draw.text((x, y), text, fill=(240, 240, 240), font=font)
    return np.array(img)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    physics_client, robot = setup_sim()

    # --- Standing Pose Renders ---
    set_standing_pose(robot)
    settle(480)

    pos, _ = p.getBasePositionAndOrientation(robot)
    target = list(pos)
    print(f"Robot standing at: {pos}")

    # Warm key light from upper-left-front
    key_light = [1.0, 0.5, 1.5]
    warm_color = [1.0, 0.95, 0.85]

    standing_views = [
        ("hero_front_34", 0.40, 35, -22, 45, key_light, warm_color,
         "Dino Quadruped — Front 3/4 View"),
        ("hero_side", 0.40, 90, -18, 45, key_light, warm_color,
         "Dino Quadruped — Side Profile"),
        ("hero_rear_34", 0.42, 215, -22, 45, key_light, warm_color,
         "Dino Quadruped — Rear 3/4 View"),
        ("low_angle_front", 0.35, 15, -8, 40, [0.5, 0.3, 2.0], warm_color,
         "Dino Quadruped — Low Angle"),
        ("top_overview", 0.55, 30, -70, 50, [0, 0, 3.0], [1.0, 1.0, 1.0],
         "Dino Quadruped — Top Overview"),
    ]

    saved = []
    for name, dist, yaw, pitch, fov, light_dir, light_col, label in standing_views:
        img = render_camera(robot, dist, yaw, pitch, target,
                            fov=fov, light_direction=light_dir, light_color=light_col)
        img = add_watermark(img, label)
        filepath = os.path.join(OUTPUT_DIR, f"{name}.png")
        Image.fromarray(img).save(filepath, quality=95)
        saved.append(filepath)
        print(f"  [Standing] {filepath}")

    # --- Trot Pose Renders ---
    set_trot_pose(robot, t=0.125)
    settle(120)

    pos2, _ = p.getBasePositionAndOrientation(robot)
    target2 = list(pos2)

    trot_views = [
        ("trot_hero", 0.40, 40, -20, 45, key_light, warm_color,
         "Dino Quadruped — Trot Gait"),
        ("trot_front", 0.38, 5, -15, 45, key_light, warm_color,
         "Dino Quadruped — Trot Front View"),
    ]

    for name, dist, yaw, pitch, fov, light_dir, light_col, label in trot_views:
        img = render_camera(robot, dist, yaw, pitch, target2,
                            fov=fov, light_direction=light_dir, light_color=light_col)
        img = add_watermark(img, label)
        filepath = os.path.join(OUTPUT_DIR, f"{name}.png")
        Image.fromarray(img).save(filepath, quality=95)
        saved.append(filepath)
        print(f"  [Trot] {filepath}")

    # --- Composite poster (2x2 grid of best views) ---
    print("\nCreating composite poster...")
    poster_names = ["hero_front_34", "hero_side", "trot_hero", "hero_rear_34"]
    grid_w, grid_h = WIDTH, HEIGHT
    poster = Image.new("RGB", (grid_w * 2, grid_h * 2), (40, 40, 45))

    for idx, pname in enumerate(poster_names):
        fpath = os.path.join(OUTPUT_DIR, f"{pname}.png")
        tile = Image.open(fpath)
        col, row = idx % 2, idx // 2
        poster.paste(tile, (col * grid_w, row * grid_h))

    poster_path = os.path.join(OUTPUT_DIR, "composite_poster.png")
    poster.save(poster_path, quality=95)
    saved.append(poster_path)
    print(f"  [Poster] {poster_path}")

    p.disconnect()
    print(f"\nDone! {len(saved)} images saved to {OUTPUT_DIR}")
    return saved


if __name__ == "__main__":
    main()
