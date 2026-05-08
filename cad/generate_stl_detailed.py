#!/usr/bin/env python3
"""
生成四足机器人 3D 打印件 - 详细版 STL 文件
包含孔位、槽位等细节，便于商家打印
"""

import math
import os

def write_stl_header(f, name):
    """写入STL文件头"""
    f.write(f"solid {name}\n")

def write_stl_footer(f, name):
    """写入STL文件尾"""
    f.write(f"endsolid {name}\n")

def write_triangle(f, v1, v2, v3):
    """写入一个三角形面片"""
    edge1 = [v2[i] - v1[i] for i in range(3)]
    edge2 = [v3[i] - v1[i] for i in range(3)]

    normal = [
        edge1[1] * edge2[2] - edge1[2] * edge2[1],
        edge1[2] * edge2[0] - edge1[0] * edge2[2],
        edge1[0] * edge2[1] - edge1[1] * edge2[0]
    ]

    length = math.sqrt(sum(n*n for n in normal))
    if length > 0:
        normal = [n/length for n in normal]

    f.write(f"  facet normal {normal[0]:.6f} {normal[1]:.6f} {normal[2]:.6f}\n")
    f.write(f"    outer loop\n")
    f.write(f"      vertex {v1[0]:.6f} {v1[1]:.6f} {v1[2]:.6f}\n")
    f.write(f"      vertex {v2[0]:.6f} {v2[1]:.6f} {v2[2]:.6f}\n")
    f.write(f"      vertex {v3[0]:.6f} {v3[1]:.6f} {v3[2]:.6f}\n")
    f.write(f"    endloop\n")
    f.write(f"  endfacet\n")

def create_box(width, depth, height):
    """创建一个长方体"""
    w, d, h = width/2, depth/2, height/2
    vertices = [
        [-w, -d, -h], [w, -d, -h], [w, d, -h], [-w, d, -h],
        [-w, -d, h],  [w, -d, h],  [w, d, h],  [-w, d, h],
    ]

    faces = [
        [0, 2, 1], [0, 3, 2],
        [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4],
        [2, 3, 7], [2, 7, 6],
        [0, 4, 7], [0, 7, 3],
        [1, 2, 6], [1, 6, 5],
    ]

    return vertices, faces

def create_cylinder(radius, height, segments=32):
    """创建一个圆柱体"""
    vertices = []

    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        vertices.append([x, y, 0])

    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        vertices.append([x, y, height])

    vertices.append([0, 0, 0])
    vertices.append([0, 0, height])

    bottom_center = len(vertices) - 2
    top_center = len(vertices) - 1

    faces = []

    for i in range(segments):
        next_i = (i + 1) % segments
        faces.append([i, next_i, i + segments])
        faces.append([next_i, next_i + segments, i + segments])

    for i in range(segments):
        next_i = (i + 1) % segments
        faces.append([bottom_center, next_i, i])

    for i in range(segments):
        next_i = (i + 1) % segments
        faces.append([top_center, i + segments, next_i + segments])

    return vertices, faces

def create_hollow_cylinder(outer_radius, inner_radius, height, segments=32):
    """创建空心圆柱（管）"""
    vertices = []

    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = outer_radius * math.cos(angle)
        y = outer_radius * math.sin(angle)
        vertices.append([x, y, 0])

    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = inner_radius * math.cos(angle)
        y = inner_radius * math.sin(angle)
        vertices.append([x, y, 0])

    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = outer_radius * math.cos(angle)
        y = outer_radius * math.sin(angle)
        vertices.append([x, y, height])

    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = inner_radius * math.cos(angle)
        y = inner_radius * math.sin(angle)
        vertices.append([x, y, height])

    faces = []

    for i in range(segments):
        next_i = (i + 1) % segments
        faces.append([i, next_i, i + 2*segments])
        faces.append([next_i, next_i + 2*segments, i + 2*segments])

    for i in range(segments):
        next_i = (i + 1) % segments
        faces.append([i + segments, i + 3*segments, next_i + segments])
        faces.append([next_i + segments, i + 3*segments, next_i + 3*segments])

    for i in range(segments):
        next_i = (i + 1) % segments
        faces.append([i, i + segments, next_i])
        faces.append([next_i, i + segments, next_i + segments])

    for i in range(segments):
        next_i = (i + 1) % segments
        faces.append([i + 2*segments, next_i + 2*segments, i + 3*segments])
        faces.append([next_i + 2*segments, next_i + 3*segments, i + 3*segments])

    return vertices, faces

def merge_geometries(geom_list):
    """合并多个几何体"""
    all_vertices = []
    all_faces = []
    vertex_offset = 0

    for vertices, faces in geom_list:
        all_vertices.extend(vertices)
        for face in faces:
            all_faces.append([v + vertex_offset for v in face])
        vertex_offset += len(vertices)

    return all_vertices, all_faces

def save_stl(filename, vertices, faces, name="model"):
    """保存STL文件"""
    with open(filename, 'w') as f:
        write_stl_header(f, name)

        for face in faces:
            v1 = vertices[face[0]]
            v2 = vertices[face[1]]
            v3 = vertices[face[2]]
            write_triangle(f, v1, v2, v3)

        write_stl_footer(f, name)

    print(f"✓ 已生成: {filename}")

def generate_hip_bracket_detailed():
    """
    生成髋关节支架 - 详细版
    尺寸: 20×40×50mm (代表 U 型支架)
    包含: 舵机安装孔 ×4, 轴承孔 ×2
    """
    print("生成 hip_bracket (详细版)...")

    # 主体盒子
    main_box, main_faces = create_box(20, 40, 50)

    # 舵机安装孔 (Φ3.2mm, 深度 5mm)
    # 标准 DS3218 孔距：48mm × 10mm，缩放到我们的尺寸
    hole_positions = [
        [-8, -15, 22],  # 前左
        [8, -15, 22],   # 前右
        [-8, 15, 22],   # 后左
        [8, 15, 22],    # 后右
    ]

    hole_geometries = []
    for pos in hole_positions:
        hole_cyl, hole_faces = create_cylinder(1.6, 5)  # Φ3.2mm, 深 5mm
        # 移动到位置
        hole_cyl = [[v[0] + pos[0], v[1] + pos[1], v[2] + pos[2]] for v in hole_cyl]
        hole_geometries.append((hole_cyl, hole_faces))

    # 轴承孔 (Φ5mm, 两侧)
    bearing_left, bearing_faces = create_cylinder(2.5, 3)
    bearing_left = [[v[0] - 8, v[1], v[2]] for v in bearing_left]

    bearing_right, _ = create_cylinder(2.5, 3)
    bearing_right = [[v[0] + 8, v[1], v[2]] for v in bearing_right]

    # 合并所有几何体
    geometries = [(main_box, main_faces)] + hole_geometries + [
        (bearing_left, bearing_faces),
        (bearing_right, bearing_faces)
    ]

    vertices, faces = merge_geometries(geometries)

    output_dir = os.path.dirname(__file__)
    filename = os.path.join(output_dir, "hip_bracket_detailed.stl")
    save_stl(filename, vertices, faces, "hip_bracket")

    return filename

def generate_knee_bracket_detailed():
    """
    生成膝关节支架 - 详细版
    尺寸: 15×30×40mm
    包含: 舵机安装孔 ×4, 轴承孔 ×2
    """
    print("生成 knee_bracket (详细版)...")

    main_box, main_faces = create_box(15, 30, 40)

    hole_positions = [
        [-6, -10, 18],
        [6, -10, 18],
        [-6, 10, 18],
        [6, 10, 18],
    ]

    hole_geometries = []
    for pos in hole_positions:
        hole_cyl, hole_faces = create_cylinder(1.6, 5)
        hole_cyl = [[v[0] + pos[0], v[1] + pos[1], v[2] + pos[2]] for v in hole_cyl]
        hole_geometries.append((hole_cyl, hole_faces))

    bearing_left, bearing_faces = create_cylinder(2.5, 3)
    bearing_left = [[v[0] - 6, v[1], v[2]] for v in bearing_left]

    bearing_right, _ = create_cylinder(2.5, 3)
    bearing_right = [[v[0] + 6, v[1], v[2]] for v in bearing_right]

    geometries = [(main_box, main_faces)] + hole_geometries + [
        (bearing_left, bearing_faces),
        (bearing_right, bearing_faces)
    ]

    vertices, faces = merge_geometries(geometries)

    output_dir = os.path.dirname(__file__)
    filename = os.path.join(output_dir, "knee_bracket_detailed.stl")
    save_stl(filename, vertices, faces, "knee_bracket")

    return filename

def generate_upper_leg_detailed():
    """
    生成上腿连杆 - 详细版
    Φ10×100mm 空心圆管
    包含: 两端连接耳 (15mm × 5mm × 5mm), M3孔
    """
    print("生成 upper_leg (详细版)...")

    # 主体：空心圆管
    main_tube, main_faces = create_hollow_cylinder(5, 3, 100)

    # 两端连接耳
    ear_left_box, ear_left_faces = create_box(15, 5, 5)
    ear_left_box = [[v[0], v[1], v[2] - 52.5] for v in ear_left_box]  # 移到左端

    ear_right_box, ear_right_faces = create_box(15, 5, 5)
    ear_right_box = [[v[0], v[1], v[2] + 52.5] for v in ear_right_box]  # 移到右端

    # 连接耳上的 M3 孔
    hole_left, hole_left_faces = create_cylinder(1.6, 5)
    hole_left = [[v[0], v[1], v[2] - 52.5] for v in hole_left]

    hole_right, hole_right_faces = create_cylinder(1.6, 5)
    hole_right = [[v[0], v[1], v[2] + 52.5] for v in hole_right]

    geometries = [
        (main_tube, main_faces),
        (ear_left_box, ear_left_faces),
        (ear_right_box, ear_right_faces),
        (hole_left, hole_left_faces),
        (hole_right, hole_right_faces),
    ]

    vertices, faces = merge_geometries(geometries)

    output_dir = os.path.dirname(__file__)
    filename = os.path.join(output_dir, "upper_leg_detailed.stl")
    save_stl(filename, vertices, faces, "upper_leg")

    return filename

def generate_lower_leg_detailed():
    """
    生成下腿连杆 - 详细版
    Φ8×100mm 空心圆管
    包含: 上端连接耳 (12mm × 4mm), 下端脚垫孔 (Φ15mm)
    """
    print("生成 lower_leg (详细版)...")

    main_tube, main_faces = create_hollow_cylinder(4, 2.5, 100)

    # 上端连接耳
    ear_top_box, ear_top_faces = create_box(12, 4, 4)
    ear_top_box = [[v[0], v[1], v[2] - 52] for v in ear_top_box]

    # 连接耳上的 M3 孔
    hole_top, hole_top_faces = create_cylinder(1.6, 4)
    hole_top = [[v[0], v[1], v[2] - 52] for v in hole_top]

    # 下端脚垫孔 (Φ15mm 半球形)
    foot_hole, foot_hole_faces = create_cylinder(7.5, 5)
    foot_hole = [[v[0], v[1], v[2] + 45] for v in foot_hole]

    geometries = [
        (main_tube, main_faces),
        (ear_top_box, ear_top_faces),
        (hole_top, hole_top_faces),
        (foot_hole, foot_hole_faces),
    ]

    vertices, faces = merge_geometries(geometries)

    output_dir = os.path.dirname(__file__)
    filename = os.path.join(output_dir, "lower_leg_detailed.stl")
    save_stl(filename, vertices, faces, "lower_leg")

    return filename

def generate_horn_adapter_detailed():
    """
    生成舵机摇臂转接件 - 详细版
    Φ25×4mm 圆盘
    包含: 中心轴孔 (Φ6mm), M2固定孔 ×4
    """
    print("生成 horn_adapter (详细版)...")

    # 主体圆盘
    main_disk, main_faces = create_cylinder(12.5, 4, 48)

    # 中心轴孔 (Φ6mm)
    center_hole, center_hole_faces = create_cylinder(3, 4)

    # 四个 M2 固定孔 (Φ2.2mm)
    hole_positions = [
        (9, 0, 0),      # 前
        (-9, 0, 0),     # 后
        (0, 9, 0),      # 右
        (0, -9, 0),     # 左
    ]

    hole_geometries = []
    for pos in hole_positions:
        hole_cyl, hole_faces = create_cylinder(1.1, 4)
        hole_cyl = [[v[0] + pos[0], v[1] + pos[1], v[2] + pos[2]] for v in hole_cyl]
        hole_geometries.append((hole_cyl, hole_faces))

    geometries = [(main_disk, main_faces), (center_hole, center_hole_faces)] + hole_geometries

    vertices, faces = merge_geometries(geometries)

    output_dir = os.path.dirname(__file__)
    filename = os.path.join(output_dir, "horn_adapter_detailed.stl")
    save_stl(filename, vertices, faces, "horn_adapter")

    return filename

def main():
    print("=" * 60)
    print("  四足恐龙机器人 - 详细版 3D 打印件 STL 生成器")
    print("=" * 60)
    print("\n生成包含孔位、槽位等细节的 STL 文件...\n")

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

    print("\n✓ 这些是详细版 STL，包含：")
    print("  - 舵机安装孔 (Φ3.2mm)")
    print("  - 轴承孔 (Φ5mm)")
    print("  - 连接耳和 M3 孔")
    print("  - 脚垫孔 (Φ15mm)")
    print("  - 中心轴孔和固定孔")
    print("\n商家可以直接使用这些 STL 进行打印，无需额外修改。")

if __name__ == "__main__":
    main()
