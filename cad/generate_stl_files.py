#!/usr/bin/env python3
"""
生成四足机器人3D打印件STL文件
用于淘宝卖家参考的简化几何体
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
    # 计算法向量
    edge1 = [v2[i] - v1[i] for i in range(3)]
    edge2 = [v3[i] - v1[i] for i in range(3)]

    normal = [
        edge1[1] * edge2[2] - edge1[2] * edge2[1],
        edge1[2] * edge2[0] - edge1[0] * edge2[2],
        edge1[0] * edge2[1] - edge1[1] * edge2[0]
    ]

    # 归一化
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
    """创建一个长方体的顶点"""
    w, d, h = width/2, depth/2, height/2
    vertices = [
        [-w, -d, -h], [w, -d, -h], [w, d, -h], [-w, d, -h],  # 底面
        [-w, -d, h],  [w, -d, h],  [w, d, h],  [-w, d, h],   # 顶面
    ]

    faces = [
        # 底面 (z = -h)
        [0, 2, 1], [0, 3, 2],
        # 顶面 (z = h)
        [4, 5, 6], [4, 6, 7],
        # 前面 (y = -d)
        [0, 1, 5], [0, 5, 4],
        # 后面 (y = d)
        [2, 3, 7], [2, 7, 6],
        # 左面 (x = -w)
        [0, 4, 7], [0, 7, 3],
        # 右面 (x = w)
        [1, 2, 6], [1, 6, 5],
    ]

    return vertices, faces

def create_cylinder(radius, height, segments=32):
    """创建一个圆柱体"""
    vertices = []

    # 底圆顶点
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        vertices.append([x, y, 0])

    # 顶圆顶点
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        vertices.append([x, y, height])

    # 中心点
    vertices.append([0, 0, 0])  # 底面中心
    vertices.append([0, 0, height])  # 顶面中心

    bottom_center = len(vertices) - 2
    top_center = len(vertices) - 1

    faces = []

    # 侧面
    for i in range(segments):
        next_i = (i + 1) % segments
        # 第一个三角形
        faces.append([i, next_i, i + segments])
        # 第二个三角形
        faces.append([next_i, next_i + segments, i + segments])

    # 底面
    for i in range(segments):
        next_i = (i + 1) % segments
        faces.append([bottom_center, next_i, i])

    # 顶面
    for i in range(segments):
        next_i = (i + 1) % segments
        faces.append([top_center, i + segments, next_i + segments])

    return vertices, faces

def create_hollow_cylinder(outer_radius, inner_radius, height, segments=32):
    """创建空心圆柱（管）"""
    vertices = []

    # 外圆底部
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = outer_radius * math.cos(angle)
        y = outer_radius * math.sin(angle)
        vertices.append([x, y, 0])

    # 内圆底部
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = inner_radius * math.cos(angle)
        y = inner_radius * math.sin(angle)
        vertices.append([x, y, 0])

    # 外圆顶部
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = outer_radius * math.cos(angle)
        y = outer_radius * math.sin(angle)
        vertices.append([x, y, height])

    # 内圆顶部
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = inner_radius * math.cos(angle)
        y = inner_radius * math.sin(angle)
        vertices.append([x, y, height])

    faces = []

    # 外侧面
    for i in range(segments):
        next_i = (i + 1) % segments
        faces.append([i, next_i, i + 2*segments])
        faces.append([next_i, next_i + 2*segments, i + 2*segments])

    # 内侧面
    for i in range(segments):
        next_i = (i + 1) % segments
        faces.append([i + segments, i + 3*segments, next_i + segments])
        faces.append([next_i + segments, i + 3*segments, next_i + 3*segments])

    # 底部环形面
    for i in range(segments):
        next_i = (i + 1) % segments
        faces.append([i, i + segments, next_i])
        faces.append([next_i, i + segments, next_i + segments])

    # 顶部环形面
    for i in range(segments):
        next_i = (i + 1) % segments
        faces.append([i + 2*segments, next_i + 2*segments, i + 3*segments])
        faces.append([next_i + 2*segments, next_i + 3*segments, i + 3*segments])

    return vertices, faces

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

def generate_hip_bracket():
    """生成髋关节支架 (简化U型)"""
    # 简化为一个带孔的盒子
    # 尺寸: 20×40×50mm
    vertices, faces = create_box(20, 40, 50)

    output_dir = os.path.dirname(__file__)
    filename = os.path.join(output_dir, "hip_bracket.stl")
    save_stl(filename, vertices, faces, "hip_bracket")

    return filename

def generate_knee_bracket():
    """生成膝关节支架 (简化U型)"""
    # 尺寸: 15×30×40mm
    vertices, faces = create_box(15, 30, 40)

    output_dir = os.path.dirname(__file__)
    filename = os.path.join(output_dir, "knee_bracket.stl")
    save_stl(filename, vertices, faces, "knee_bracket")

    return filename

def generate_upper_leg():
    """生成上腿连杆 (空心圆管 Φ10×100mm)"""
    # 外径10mm, 内径6mm, 长度100mm
    vertices, faces = create_hollow_cylinder(
        outer_radius=5.0,  # Φ10mm
        inner_radius=3.0,  # Φ6mm 内径
        height=100.0,
        segments=32
    )

    output_dir = os.path.dirname(__file__)
    filename = os.path.join(output_dir, "upper_leg.stl")
    save_stl(filename, vertices, faces, "upper_leg")

    return filename

def generate_lower_leg():
    """生成下腿连杆 (空心圆管 Φ8×100mm)"""
    # 外径8mm, 内径5mm, 长度100mm
    vertices, faces = create_hollow_cylinder(
        outer_radius=4.0,  # Φ8mm
        inner_radius=2.5,  # Φ5mm 内径
        height=100.0,
        segments=32
    )

    output_dir = os.path.dirname(__file__)
    filename = os.path.join(output_dir, "lower_leg.stl")
    save_stl(filename, vertices, faces, "lower_leg")

    return filename

def generate_horn_adapter():
    """生成舵机摇臂转接件 (Φ25×4mm圆盘)"""
    # 直径25mm, 厚度4mm
    vertices, faces = create_cylinder(
        radius=12.5,  # Φ25mm
        height=4.0,
        segments=48  # 圆盘用更多分段
    )

    output_dir = os.path.dirname(__file__)
    filename = os.path.join(output_dir, "horn_adapter.stl")
    save_stl(filename, vertices, faces, "horn_adapter")

    return filename

def main():
    print("=" * 60)
    print("  四足恐龙机器人 - 3D打印件STL生成器")
    print("=" * 60)
    print("\n生成简化几何体STL文件（用于淘宝卖家参考）\n")

    # 确保输出目录存在
    output_dir = os.path.dirname(__file__)
    if not output_dir:
        output_dir = "."

    # 生成所有STL文件
    files = []

    print("生成中...\n")

    files.append(generate_hip_bracket())
    files.append(generate_knee_bracket())
    files.append(generate_upper_leg())
    files.append(generate_lower_leg())
    files.append(generate_horn_adapter())

    print("\n" + "=" * 60)
    print("  生成完成！")
    print("=" * 60)

    print(f"\n生成文件清单:")
    for i, f in enumerate(files, 1):
        size_kb = os.path.getsize(f) / 1024
        print(f"  {i}. {os.path.basename(f)} ({size_kb:.1f} KB)")

    print(f"\n文件位置: {output_dir}/")

    print("\n⚠️  注意:")
    print("  这些是简化的几何体，仅用于给卖家参考尺寸")
    print("  实际打印需要:")
    print("  1. 添加舵机安装孔 (Φ3.2mm for M3螺丝)")
    print("  2. 添加轴承孔 (Φ10.5mm for MR105ZZ)")
    print("  3. 支架需要挖空U型槽")
    print("  4. 腿杆需要两端连接耳")
    print("\n  详细规格见: docs/3D打印件规格_淘宝定制.md")

    print("\n使用建议:")
    print("  1. 将生成的STL文件发给卖家作为几何参考")
    print("  2. 同时提供规格文档说明孔位和细节")
    print("  3. 卖家可在此基础上添加孔位和细节")

if __name__ == "__main__":
    main()
