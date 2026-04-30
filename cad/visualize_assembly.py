#!/usr/bin/env python3
"""
Dino Quadruped 3D Assembly Viewer
使用 PyBullet 可视化完整组装后的机器人

运行方式：
    python3 cad/visualize_assembly.py

控制：
    - 鼠标左键拖动：旋转视角
    - 鼠标滚轮：缩放
    - 按 Q 键：退出
    - 按 R 键：重置视角
    - 按 S 键：显示站立姿态
"""

import pybullet as p
import pybullet_data
import time
import math
import os
import sys

class DinoAssemblyViewer:
    def __init__(self):
        # 连接 PyBullet GUI
        self.physics_client = p.connect(p.GUI)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())

        # 设置重力和环境
        p.setGravity(0, 0, -9.81)

        # 加载地面
        self.plane_id = p.loadURDF("plane.urdf")

        # 获取 URDF 路径
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(script_dir)
        urdf_path = os.path.join(project_dir, "urdf", "dino_quadruped.urdf")

        if not os.path.exists(urdf_path):
            print(f"❌ URDF 文件未找到: {urdf_path}")
            sys.exit(1)

        # 加载机器人（站立在地面上）
        start_pos = [0, 0, 0.25]  # 初始高度
        start_orientation = p.getQuaternionFromEuler([0, 0, 0])
        self.robot_id = p.loadURDF(urdf_path, start_pos, start_orientation, useFixedBase=False)

        print("✓ 恐龙四足机器人 URDF 已加载")

        # 获取关节信息
        self.num_joints = p.getNumJoints(self.robot_id)
        self.joint_info = {}

        for i in range(self.num_joints):
            info = p.getJointInfo(self.robot_id, i)
            joint_name = info[1].decode('utf-8')
            if 'hip' in joint_name or 'shoulder' in joint_name or 'knee' in joint_name:
                self.joint_info[joint_name] = i

        print(f"✓ 关节数量: {len(self.joint_info)}")
        for name, idx in sorted(self.joint_info.items()):
            print(f"  - {name}: 索引 {idx}")

        # 设置默认姿态（站立）
        self.set_standing_pose()

        # 配置相机视角
        self.reset_camera()

        # 添加调试信息
        self.add_debug_info()

    def reset_camera(self):
        """重置相机视角到合适的观察位置"""
        p.resetDebugVisualizerCamera(
            cameraDistance=0.8,      # 距离机器人 0.8m
            cameraYaw=45,            # 水平旋转 45°
            cameraPitch=-30,         # 俯视 30°
            cameraTargetPosition=[0, 0, 0.15]  # 看向机器人中心
        )

    def set_standing_pose(self):
        """设置站立姿态（参考 RL 训练中的默认姿态）"""
        # 站立姿态的关节角度（弧度）
        standing_angles = {
            # 髋关节（hip）：基本不转
            'fl_hip_joint': 0.0,
            'fr_hip_joint': 0.0,
            'rl_hip_joint': 0.0,
            'rr_hip_joint': 0.0,

            # 肩关节（shoulder）：向外展开约 45°
            'fl_shoulder_joint': 0.8,
            'fr_shoulder_joint': 0.8,
            'rl_shoulder_joint': 0.8,
            'rr_shoulder_joint': 0.8,

            # 膝关节（knee）：弯曲约 -120°（向后折叠）
            'fl_knee_joint': -2.0,
            'fr_knee_joint': -2.0,
            'rl_knee_joint': -2.0,
            'rr_knee_joint': -2.0,
        }

        for joint_name, angle in standing_angles.items():
            if joint_name in self.joint_info:
                joint_idx = self.joint_info[joint_name]
                p.resetJointState(self.robot_id, joint_idx, angle)

        print("✓ 已设置站立姿态")

    def add_debug_info(self):
        """在场景中添加坐标轴和标注"""
        # 添加世界坐标轴
        p.addUserDebugLine([0, 0, 0], [0.2, 0, 0], [1, 0, 0], lineWidth=3)  # X 轴（红色）
        p.addUserDebugLine([0, 0, 0], [0, 0.2, 0], [0, 1, 0], lineWidth=3)  # Y 轴（绿色）
        p.addUserDebugLine([0, 0, 0], [0, 0, 0.2], [0, 0, 1], lineWidth=3)  # Z 轴（蓝色）

        # 添加文字标注
        p.addUserDebugText("X (前)", [0.2, 0, 0], [1, 0, 0], textSize=1.5)
        p.addUserDebugText("Y (左)", [0, 0.2, 0], [0, 1, 0], textSize=1.5)
        p.addUserDebugText("Z (上)", [0, 0, 0.2], [0, 0, 1], textSize=1.5)

        # 添加机器人尺寸标注
        p.addUserDebugText("Dino Quadruped", [0, 0, 0.35], [0.2, 0.6, 0.2], textSize=2)
        p.addUserDebugText("200x110x60mm 机身", [0, 0, 0.32], [0.5, 0.5, 0.5], textSize=1)
        p.addUserDebugText("12 DOF (4腿x3关节)", [0, 0, 0.29], [0.5, 0.5, 0.5], textSize=1)

    def run(self):
        """主循环"""
        print("\n========== 控制说明 ==========")
        print("  鼠标左键拖动: 旋转视角")
        print("  鼠标滚轮:     缩放")
        print("  按 Q 键:      退出")
        print("  按 R 键:      重置视角")
        print("  按 S 键:      显示站立姿态")
        print("================================\n")

        last_time = time.time()

        try:
            while True:
                # 检查键盘输入
                keys = p.getKeyboardEvents()

                if ord('q') in keys and keys[ord('q')] & p.KEY_WAS_TRIGGERED:
                    print("退出查看器")
                    break

                if ord('r') in keys and keys[ord('r')] & p.KEY_WAS_TRIGGERED:
                    self.reset_camera()
                    print("视角已重置")

                if ord('s') in keys and keys[ord('s')] & p.KEY_WAS_TRIGGERED:
                    self.set_standing_pose()

                # 物理仿真步进
                p.stepSimulation()

                # 控制帧率
                current_time = time.time()
                elapsed = current_time - last_time
                if elapsed < 1.0/240.0:  # 240 Hz
                    time.sleep(1.0/240.0 - elapsed)
                last_time = current_time

        except KeyboardInterrupt:
            print("\n用户中断")

        finally:
            p.disconnect()
            print("✓ PyBullet 已断开")


def main():
    print("=" * 60)
    print("  Dino Quadruped 3D 组装查看器")
    print("=" * 60)

    viewer = DinoAssemblyViewer()
    viewer.run()


if __name__ == "__main__":
    main()
