#!/usr/bin/env python3
"""
快速查看 URDF 模型 - 带支架显示
使用 PyBullet GUI 查看更新后的机器人模型（包括新增的舵机支架）
"""

import pybullet as p
import pybullet_data
import time
import os

URDF_PATH = os.path.join(os.path.dirname(__file__), "..", "urdf", "dino_quadruped.urdf")

def main():
    print("=" * 60)
    print("  恐龙四足机器人 - URDF 快速查看")
    print("=" * 60)

    # 连接 GUI
    pc = p.connect(p.GUI)
    p.configureDebugVisualizer(p.COV_ENABLE_GUI, 1)
    p.setGravity(0, 0, -9.81)
    p.setAdditionalSearchPath(pybullet_data.getDataPath())

    # 加载地面
    plane = p.loadURDF("plane.urdf")

    # 加载机器人
    print(f"\n加载 URDF: {URDF_PATH}")
    robot = p.loadURDF(
        URDF_PATH,
        basePosition=[0, 0, 0.25],
        baseOrientation=p.getQuaternionFromEuler([0, 0, 0]),
        useFixedBase=False,
        physicsClientId=pc,
    )

    # 统计信息
    num_joints = p.getNumJoints(robot)
    print(f"✓ 加载成功，关节数: {num_joints}")

    # 显示支架信息
    brackets = []
    for i in range(num_joints):
        info = p.getJointInfo(robot, i)
        link_name = info[12].decode('utf-8')
        if 'bracket' in link_name:
            brackets.append(link_name)

    print(f"✓ 支架 links: {len(brackets)} 个")
    for b in sorted(brackets):
        print(f"  - {b}")

    # 设置相机视角（俯视45度角）
    p.resetDebugVisualizerCamera(
        cameraDistance=0.8,
        cameraYaw=45,
        cameraPitch=-30,
        cameraTargetPosition=[0, 0, 0.15]
    )

    # 添加关节滑动条（用于调试关节运动）
    joint_names = [
        "fl_hip_joint", "fl_shoulder_joint", "fl_knee_joint",
        "fr_hip_joint", "fr_shoulder_joint", "fr_knee_joint",
        "rl_hip_joint", "rl_shoulder_joint", "rl_knee_joint",
        "rr_hip_joint", "rr_shoulder_joint", "rr_knee_joint",
    ]

    joint_sliders = {}
    joint_indices = {}

    for i in range(num_joints):
        info = p.getJointInfo(robot, i)
        joint_name = info[1].decode('utf-8')

        if joint_name in joint_names:
            joint_type = info[2]
            if joint_type == p.JOINT_REVOLUTE:
                lower_limit = info[8]
                upper_limit = info[9]

                # 创建滑动条
                slider = p.addUserDebugParameter(
                    joint_name,
                    lower_limit,
                    upper_limit,
                    (lower_limit + upper_limit) / 2.0
                )
                joint_sliders[joint_name] = slider
                joint_indices[joint_name] = i

    print(f"\n✓ 创建了 {len(joint_sliders)} 个关节控制滑条")
    print("\n📌 操作指南:")
    print("  - 鼠标左键拖动: 旋转视角")
    print("  - 鼠标滚轮: 缩放")
    print("  - 右侧滑条: 调节各关节角度")
    print("  - Ctrl+C: 退出")
    print("\n窗口保持打开，按 Ctrl+C 关闭...")

    # 主循环
    try:
        while True:
            # 读取滑动条并应用到关节
            for joint_name, slider_id in joint_sliders.items():
                target_angle = p.readUserDebugParameter(slider_id)
                joint_idx = joint_indices[joint_name]

                p.setJointMotorControl2(
                    robot,
                    joint_idx,
                    p.POSITION_CONTROL,
                    targetPosition=target_angle,
                    force=10
                )

            p.stepSimulation()
            time.sleep(1./240.)

    except KeyboardInterrupt:
        print("\n\n✓ 已关闭查看器")

    p.disconnect()

if __name__ == "__main__":
    main()
