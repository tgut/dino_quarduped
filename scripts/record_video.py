#!/usr/bin/env python3
"""
Record simulation videos of the Dino Quadruped (headless).
Outputs MP4 files using imageio + ffmpeg.
"""

import pybullet as p
import pybullet_data
import numpy as np
import imageio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from sim_standalone import leg_ik, LEG_JOINTS, JOINT_MAP, TrotGait, StandPose

URDF_PATH = os.path.join(os.path.dirname(__file__), "..", "urdf", "dino_quadruped.urdf")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")

# Video settings
WIDTH, HEIGHT = 640, 480
FPS = 30
SIM_DT = 1.0 / 240  # physics timestep
FRAMES_PER_VIDEO_FRAME = int(1.0 / (FPS * SIM_DT))  # sim steps per video frame


def setup_sim():
    """Initialize simulation."""
    physics_client = p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(SIM_DT)
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.loadURDF("plane.urdf")

    robot = p.loadURDF(
        URDF_PATH,
        basePosition=[0, 0, 0.25],
        baseOrientation=p.getQuaternionFromEuler([0, 0, 0]),
        useFixedBase=False,
    )

    JOINT_MAP.clear()
    for i in range(p.getNumJoints(robot)):
        info = p.getJointInfo(robot, i)
        JOINT_MAP[info[1].decode("utf-8")] = i

    return physics_client, robot


def set_leg_angles(robot, leg_name, angles):
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


def render_frame(cam_target, cam_distance=0.45, cam_yaw=30, cam_pitch=-25):
    """Render a single frame."""
    view_matrix = p.computeViewMatrixFromYawPitchRoll(
        cameraTargetPosition=cam_target,
        distance=cam_distance,
        yaw=cam_yaw,
        pitch=cam_pitch,
        roll=0,
        upAxisIndex=2,
    )
    proj_matrix = p.computeProjectionMatrixFOV(
        fov=60, aspect=WIDTH / HEIGHT, nearVal=0.01, farVal=10.0
    )
    _, _, rgb, _, _ = p.getCameraImage(
        WIDTH, HEIGHT, view_matrix, proj_matrix,
        renderer=p.ER_TINY_RENDERER,
    )
    return np.array(rgb, dtype=np.uint8).reshape(HEIGHT, WIDTH, 4)[:, :, :3]


def record_stand_video(duration=3.0):
    """Record standing pose with orbiting camera."""
    print(f"Recording STAND video ({duration}s)...")
    physics_client, robot = setup_sim()

    gait = StandPose(body_height=0.15)
    frames = []
    total_frames = int(duration * FPS)

    # Apply standing pose and settle
    for leg_name in LEG_JOINTS:
        side = "left" if leg_name.endswith("l") else "right"
        angles = leg_ik(0.0, 0.0, -0.15, side=side)
        set_leg_angles(robot, leg_name, angles)

    for _ in range(480):  # 2s settle
        p.stepSimulation()

    pos, _ = p.getBasePositionAndOrientation(robot)
    cam_target = list(pos)

    for frame_idx in range(total_frames):
        # Orbit camera around robot
        yaw = (frame_idx / total_frames) * 360
        frame = render_frame(cam_target, cam_distance=0.45, cam_yaw=yaw, cam_pitch=-25)
        frames.append(frame)

        # Step sim
        for _ in range(FRAMES_PER_VIDEO_FRAME):
            foot_pos = gait.get_foot_positions(0)
            for leg_name, (fx, fy, fz) in foot_pos.items():
                side = "left" if leg_name.endswith("l") else "right"
                angles = leg_ik(fx, fy, fz, side=side)
                set_leg_angles(robot, leg_name, angles)
            p.stepSimulation()

        if frame_idx % FPS == 0:
            print(f"  Frame {frame_idx}/{total_frames}")

    p.disconnect()

    # Write video
    output_path = os.path.join(OUTPUT_DIR, "dino_stand.mp4")
    writer = imageio.get_writer(output_path, fps=FPS, codec='libx264',
                                 output_params=['-pix_fmt', 'yuv420p'])
    for f in frames:
        writer.append_data(f)
    writer.close()
    print(f"  Saved: {output_path} ({len(frames)} frames)")
    return output_path


def record_trot_video(duration=5.0):
    """Record trot gait with tracking camera."""
    print(f"\nRecording TROT video ({duration}s)...")
    physics_client, robot = setup_sim()

    gait = TrotGait(step_length=0.04, step_height=0.03, body_height=0.15, period=0.5)
    frames = []
    total_frames = int(duration * FPS)

    # Settle in standing first
    for leg_name in LEG_JOINTS:
        side = "left" if leg_name.endswith("l") else "right"
        angles = leg_ik(0.0, 0.0, -0.15, side=side)
        set_leg_angles(robot, leg_name, angles)

    for _ in range(480):
        p.stepSimulation()

    # Yaw PID controller state
    yaw_prev = 0.0
    yaw_integral = 0.0
    YAW_KP, YAW_KI, YAW_KD = 0.15, 0.08, 0.02
    MAX_HIP_OFFSET = 0.30
    MAX_INTEGRAL = 3.0

    t = 0.0
    for frame_idx in range(total_frames):
        # Camera tracks robot position
        pos, orn = p.getBasePositionAndOrientation(robot)
        cam_target = list(pos)

        frame = render_frame(cam_target, cam_distance=0.45, cam_yaw=45, cam_pitch=-25)
        frames.append(frame)

        # Step sim with trot gait + yaw correction
        for _ in range(FRAMES_PER_VIDEO_FRAME):
            # Yaw feedback
            _, orn = p.getBasePositionAndOrientation(robot)
            euler = p.getEulerFromQuaternion(orn)
            yaw_error = euler[2]

            yaw_rate = (yaw_error - yaw_prev) / SIM_DT
            yaw_integral = np.clip(yaw_integral + yaw_error * SIM_DT,
                                   -MAX_INTEGRAL, MAX_INTEGRAL)
            yaw_prev = yaw_error
            hip_offset = np.clip(
                YAW_KP * yaw_error + YAW_KI * yaw_integral + YAW_KD * yaw_rate,
                -MAX_HIP_OFFSET, MAX_HIP_OFFSET)
            foot_dx = np.clip(hip_offset * 0.05, -0.015, 0.015)

            foot_pos = gait.get_foot_positions(t)
            for leg_name, (fx, fy, fz) in foot_pos.items():
                side = "left" if leg_name.endswith("l") else "right"
                if leg_name.startswith("f"):
                    fx += foot_dx
                else:
                    fx -= foot_dx
                try:
                    hip_a, shoulder_a, knee_a = leg_ik(fx, fy, fz, side=side)
                    if side == "left":
                        hip_a += hip_offset
                    else:
                        hip_a -= hip_offset
                    set_leg_angles(robot, leg_name, (hip_a, shoulder_a, knee_a))
                except:
                    pass
            p.stepSimulation()
            t += SIM_DT

        if frame_idx % FPS == 0:
            yaw_deg = np.degrees(euler[2])
            print(f"  Frame {frame_idx}/{total_frames} | t={t:.1f}s | pos=({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f}) | yaw={yaw_deg:+.1f}")

    p.disconnect()

    output_path = os.path.join(OUTPUT_DIR, "dino_trot.mp4")
    writer = imageio.get_writer(output_path, fps=FPS, codec='libx264',
                                 output_params=['-pix_fmt', 'yuv420p'])
    for f in frames:
        writer.append_data(f)
    writer.close()
    print(f"  Saved: {output_path} ({len(frames)} frames)")
    return output_path


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stand_path = record_stand_video(duration=4.0)
    trot_path = record_trot_video(duration=15.0)
    print(f"\nAll done!")
    print(f"  Stand: {stand_path}")
    print(f"  Trot:  {trot_path}")
