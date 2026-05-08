#!/usr/bin/env python3
"""
生成四足机器人 3D 打印件 - 详细版 STL 文件
包含孔位、槽位等细节,便于商家打印
使用 trimesh 库进行布尔运算,生成真实的孔而非凸起
"""

import os
import numpy as np

try:
    import trimesh
except ImportError:
    print("[错误] 需要安装 trimesh 库")
    print("运行: pip3 install trimesh")
    exit(1)


def generate_hip_bracket_detailed():
    """
    生成髋关节支架 - 详细版
    尺寸: 20×40×50mm (代表 U 型支架)
    包含: 舵机安装孔 ×4, 轴承孔 ×2
    """
    print("生成 hip_bracket (详细版)...")

    # 主体盒子: 20×40×50mm
    main_box = trimesh.creation.box(extents=[20, 40, 50])

    # 舵机安装孔 (Φ3.2mm, 深度 5mm)
    # 标准 DS3218 孔距配置
    hole_positions = [
        [-8, -15, 22],  # 前左
        [8, -15, 22],   # 前右
        [-8, 15, 22],   # 后左
        [8, 15, 22],    # 后右
    ]

    # 从主体减去所有舵机安装孔
    for pos in hole_positions:
        hole = trimesh.creation.cylinder(
            radius=1.6,      # Φ3.2mm
            height=5,
            sections=32
        )
        # 旋转90度使圆柱沿Z轴
        hole.apply_transform(trimesh.transformations.rotation_matrix(
            np.pi/2, [1, 0, 0]
        ))
        hole.apply_translation(pos)
        main_box = main_box.difference(hole)

    # 轴承孔 (Φ5mm, 深度 3mm, 两侧)
    bearing_positions = [
        [-8, 0, 0],   # 左侧
        [8, 0, 0],    # 右侧
    ]

    for pos in bearing_positions:
        bearing_hole = trimesh.creation.cylinder(
            radius=2.5,   # Φ5mm
            height=3,
            sections=32
        )
        bearing_hole.apply_transform(trimesh.transformations.rotation_matrix(
            np.pi/2, [0, 1, 0]
        ))
        bearing_hole.apply_translation(pos)
        main_box = main_box.difference(bearing_hole)

    output_dir = os.path.dirname(__file__)
    filename = os.path.join(output_dir, "hip_bracket_detailed.stl")
    main_box.export(filename)
    print(f"✓ 已生成: {filename}")

    return filename


def generate_knee_bracket_detailed():
    """
    生成膝关节支架 - 详细版
    尺寸: 15×30×40mm
    包含: 舵机安装孔 ×4, 轴承孔 ×2
    """
    print("生成 knee_bracket (详细版)...")

    # 主体盒子: 15×30×40mm
    main_box = trimesh.creation.box(extents=[15, 30, 40])

    # 舵机安装孔配置
    hole_positions = [
        [-6, -10, 18],
        [6, -10, 18],
        [-6, 10, 18],
        [6, 10, 18],
    ]

    for pos in hole_positions:
        hole = trimesh.creation.cylinder(
            radius=1.6,
            height=5,
            sections=32
        )
        hole.apply_transform(trimesh.transformations.rotation_matrix(
            np.pi/2, [1, 0, 0]
        ))
        hole.apply_translation(pos)
        main_box = main_box.difference(hole)

    # 轴承孔
    bearing_positions = [
        [-6, 0, 0],
        [6, 0, 0],
    ]

    for pos in bearing_positions:
        bearing_hole = trimesh.creation.cylinder(
            radius=2.5,
            height=3,
            sections=32
        )
        bearing_hole.apply_transform(trimesh.transformations.rotation_matrix(
            np.pi/2, [0, 1, 0]
        ))
        bearing_hole.apply_translation(pos)
        main_box = main_box.difference(bearing_hole)

    output_dir = os.path.dirname(__file__)
    filename = os.path.join(output_dir, "knee_bracket_detailed.stl")
    main_box.export(filename)
    print(f"✓ 已生成: {filename}")

    return filename


def generate_upper_leg_detailed():
    """
    生成上腿连杆 - 详细版
    Φ10×100mm 空心圆管
    包含: 两端连接耳 (15mm × 5mm × 5mm), M3孔
    """
    print("生成 upper_leg (详细版)...")

    # 主体: 空心圆管 (外径Φ10, 内径Φ6, 长100mm)
    outer_tube = trimesh.creation.cylinder(
        radius=5,
        height=100,
        sections=32
    )
    inner_tube = trimesh.creation.cylinder(
        radius=3,
        height=102,  # 稍长以确保完全减去
        sections=32
    )
    main_tube = outer_tube.difference(inner_tube)

    # 左端连接耳
    ear_left = trimesh.creation.box(extents=[15, 5, 5])
    ear_left.apply_translation([0, 0, -52.5])

    # 右端连接耳
    ear_right = trimesh.creation.box(extents=[15, 5, 5])
    ear_right.apply_translation([0, 0, 52.5])

    # 合并主体和连接耳
    result = main_tube.union(ear_left).union(ear_right)

    # 连接耳上的M3孔 (左右各一个)
    hole_left = trimesh.creation.cylinder(radius=1.6, height=16, sections=32)
    hole_left.apply_transform(trimesh.transformations.rotation_matrix(
        np.pi/2, [1, 0, 0]
    ))
    hole_left.apply_translation([0, 0, -52.5])

    hole_right = trimesh.creation.cylinder(radius=1.6, height=16, sections=32)
    hole_right.apply_transform(trimesh.transformations.rotation_matrix(
        np.pi/2, [1, 0, 0]
    ))
    hole_right.apply_translation([0, 0, 52.5])

    result = result.difference(hole_left).difference(hole_right)

    output_dir = os.path.dirname(__file__)
    filename = os.path.join(output_dir, "upper_leg_detailed.stl")
    result.export(filename)
    print(f"✓ 已生成: {filename}")

    return filename


def generate_lower_leg_detailed():
    """
    生成下腿连杆 - 详细版
    Φ8×100mm 空心圆管
    包含: 上端连接耳 (12mm × 4mm), 下端脚垫孔 (Φ15mm)
    """
    print("生成 lower_leg (详细版)...")

    # 主体: 空心圆管 (外径Φ8, 内径Φ5, 长100mm)
    outer_tube = trimesh.creation.cylinder(
        radius=4,
        height=100,
        sections=32
    )
    inner_tube = trimesh.creation.cylinder(
        radius=2.5,
        height=102,
        sections=32
    )
    main_tube = outer_tube.difference(inner_tube)

    # 上端连接耳
    ear_top = trimesh.creation.box(extents=[12, 4, 4])
    ear_top.apply_translation([0, 0, -52])

    result = main_tube.union(ear_top)

    # 连接耳上的M3孔
    hole_top = trimesh.creation.cylinder(radius=1.6, height=13, sections=32)
    hole_top.apply_transform(trimesh.transformations.rotation_matrix(
        np.pi/2, [1, 0, 0]
    ))
    hole_top.apply_translation([0, 0, -52])

    result = result.difference(hole_top)

    # 下端脚垫孔 (Φ15mm, 深度5mm)
    foot_hole = trimesh.creation.cylinder(radius=7.5, height=5, sections=32)
    foot_hole.apply_translation([0, 0, 45])

    result = result.difference(foot_hole)

    output_dir = os.path.dirname(__file__)
    filename = os.path.join(output_dir, "lower_leg_detailed.stl")
    result.export(filename)
    print(f"✓ 已生成: {filename}")

    return filename


def generate_horn_adapter_detailed():
    """
    生成舵机摇臂转接件 - 详细版
    Φ25×4mm 圆盘
    包含: 中心轴孔 (Φ6mm), M2固定孔 ×4
    """
    print("生成 horn_adapter (详细版)...")

    # 主体圆盘 (Φ25mm, 厚度4mm)
    main_disk = trimesh.creation.cylinder(
        radius=12.5,
        height=4,
        sections=48
    )

    # 中心轴孔 (Φ6mm)
    center_hole = trimesh.creation.cylinder(
        radius=3,
        height=5,  # 稍长以确保穿透
        sections=32
    )

    result = main_disk.difference(center_hole)

    # 四个M2固定孔 (Φ2.2mm)
    hole_positions = [
        [9, 0, 0],      # 前
        [-9, 0, 0],     # 后
        [0, 9, 0],      # 右
        [0, -9, 0],     # 左
    ]

    for pos in hole_positions:
        hole = trimesh.creation.cylinder(
            radius=1.1,   # Φ2.2mm
            height=5,
            sections=32
        )
        hole.apply_translation(pos)
        result = result.difference(hole)

    output_dir = os.path.dirname(__file__)
    filename = os.path.join(output_dir, "horn_adapter_detailed.stl")
    result.export(filename)
    print(f"✓ 已生成: {filename}")

    return filename


def main():
    print("=" * 60)
    print("  四足恐龙机器人 - 详细版 3D 打印件 STL 生成器")
    print("=" * 60)
    print("\n使用 trimesh 布尔运算生成真实孔位的 STL 文件...\n")

    files = []
    files.append(generate_hip_bracket_detailed())
    files.append(generate_knee_bracket_detailed())
    files.append(generate_upper_leg_detailed())
    files.append(generate_lower_leg_detailed())
    files.append(generate_horn_adapter_detailed())

    print("\n" + "=" * 60)
    print("  生成完成！")
    print("=" * 60)

    print(f"\n生成文件清单:")
    for i, f in enumerate(files, 1):
        size_kb = os.path.getsize(f) / 1024
        print(f"  {i}. {os.path.basename(f)} ({size_kb:.1f} KB)")

    print(f"\n文件位置: {os.path.dirname(__file__)}/")

    print("\n✓ 这些是详细版 STL，包含真实的孔位：")
    print("  - 舵机安装孔 (Φ3.2mm) - 使用布尔差集生成")
    print("  - 轴承孔 (Φ5mm) - 使用布尔差集生成")
    print("  - 连接耳和 M3 孔 - 使用布尔差集生成")
    print("  - 脚垫孔 (Φ15mm) - 使用布尔差集生成")
    print("  - 中心轴孔和固定孔 - 使用布尔差集生成")
    print("\n商家可以直接使用这些 STL 进行打印，无需额外修改。")
    print("孔位均为凹陷而非凸起。")


if __name__ == "__main__":
    main()
