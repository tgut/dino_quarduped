#!/usr/bin/env python3
"""
Dino Quadruped 真实器件 3D 组装可视化
基于实际采购的器件尺寸绘制 3D 组装效果图

运行方式：
    python3 cad/visualize_real_components.py

需要：matplotlib (通常已安装)
"""

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

class RealComponentVisualizer:
    """真实器件 3D 可视化器"""

    def __init__(self):
        self.fig = plt.figure(figsize=(16, 12))
        self.ax = self.fig.add_subplot(111, projection='3d')

        # 设置坐标轴
        self.ax.set_xlabel('X (mm) - 前后', fontsize=12)
        self.ax.set_ylabel('Y (mm) - 左右', fontsize=12)
        self.ax.set_zlabel('Z (mm) - 高度', fontsize=12)

        # 设置视角
        self.ax.view_init(elev=20, azim=45)

    def draw_box(self, center, size, color, alpha=0.7, label=None):
        """绘制长方体"""
        x, y, z = center
        dx, dy, dz = size

        # 定义 8 个顶点
        vertices = np.array([
            [x-dx/2, y-dy/2, z-dz/2],
            [x+dx/2, y-dy/2, z-dz/2],
            [x+dx/2, y+dy/2, z-dz/2],
            [x-dx/2, y+dy/2, z-dz/2],
            [x-dx/2, y-dy/2, z+dz/2],
            [x+dx/2, y-dy/2, z+dz/2],
            [x+dx/2, y+dy/2, z+dz/2],
            [x-dx/2, y+dy/2, z+dz/2],
        ])

        # 定义 6 个面
        faces = [
            [vertices[0], vertices[1], vertices[5], vertices[4]],  # 前
            [vertices[2], vertices[3], vertices[7], vertices[6]],  # 后
            [vertices[0], vertices[3], vertices[7], vertices[4]],  # 左
            [vertices[1], vertices[2], vertices[6], vertices[5]],  # 右
            [vertices[0], vertices[1], vertices[2], vertices[3]],  # 下
            [vertices[4], vertices[5], vertices[6], vertices[7]],  # 上
        ]

        poly = Poly3DCollection(faces, alpha=alpha, facecolor=color, edgecolor='black', linewidth=0.5)
        self.ax.add_collection3d(poly)

        # 添加标签
        if label:
            self.ax.text(x, y, z+dz/2+5, label, fontsize=9, ha='center',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

    def draw_cylinder(self, center, radius, height, color, alpha=0.7, label=None):
        """绘制圆柱体（用于舵机）"""
        x, y, z = center

        # 生成圆柱面
        theta = np.linspace(0, 2*np.pi, 20)
        z_line = np.linspace(z-height/2, z+height/2, 2)

        X = x + radius * np.outer(np.cos(theta), np.ones(len(z_line)))
        Y = y + radius * np.outer(np.sin(theta), np.ones(len(z_line)))
        Z = np.outer(np.ones(len(theta)), z_line)

        self.ax.plot_surface(X, Y, Z, color=color, alpha=alpha)

        # 顶部和底部圆
        for z_cap in [z-height/2, z+height/2]:
            x_cap = x + radius * np.cos(theta)
            y_cap = y + radius * np.sin(theta)
            z_cap_arr = np.full_like(theta, z_cap)

            verts = [list(zip(x_cap, y_cap, z_cap_arr))]
            poly = Poly3DCollection(verts, alpha=alpha, facecolor=color, edgecolor='black', linewidth=0.5)
            self.ax.add_collection3d(poly)

        if label:
            self.ax.text(x, y, z+height/2+3, label, fontsize=7, ha='center')

    def draw_servo(self, position, rotation_axis='z', label=''):
        """绘制 DS3218 舵机（真实尺寸）"""
        x, y, z = position

        # DS3218 尺寸: 40.7 × 20.2 × 36.2 mm
        servo_length = 40.7
        servo_width = 20.2
        servo_height = 36.2

        if rotation_axis == 'x':
            size = (servo_height, servo_width, servo_length)
        elif rotation_axis == 'y':
            size = (servo_length, servo_height, servo_width)
        else:  # z
            size = (servo_length, servo_width, servo_height)

        self.draw_box((x, y, z), size, color='#2C3E50', alpha=0.8, label=label)

        # 舵机轴（小圆柱）
        if rotation_axis == 'z':
            self.draw_cylinder((x, y, z+servo_height/2+3), 3, 6, color='white', alpha=1.0)

    def draw_u_bracket(self, position, label=''):
        """绘制 U 型支架"""
        x, y, z = position

        # U 型支架简化为框架
        bracket_width = 42  # 内宽
        bracket_height = 50
        bracket_thickness = 3

        # 左侧板
        self.draw_box((x-bracket_width/2, y, z),
                     (bracket_thickness, 20, bracket_height),
                     color='silver', alpha=0.6)

        # 右侧板
        self.draw_box((x+bracket_width/2, y, z),
                     (bracket_thickness, 20, bracket_height),
                     color='silver', alpha=0.6)

        if label:
            self.ax.text(x, y, z+bracket_height/2+3, label, fontsize=7, ha='center', color='gray')

    def visualize_assembly(self):
        """绘制完整组装图"""

        # ==================== 机身板 ====================
        body_length = 200
        body_width = 110
        body_height = 3  # 亚克力板厚度

        # 底板
        self.draw_box((0, 0, 0), (body_length, body_width, body_height),
                     color='lightblue', alpha=0.3, label='底板 (200×110×3mm)')

        # 顶板（通过铜柱抬高 30mm）
        top_plate_z = 30
        self.draw_box((0, 0, top_plate_z), (body_length, body_width, body_height),
                     color='lightblue', alpha=0.3, label='顶板')

        # 铜柱（8 个 M3×30）
        standoff_positions = [
            (-90, -45, 15), (-90, 0, 15), (-90, 45, 15),
            (0, -45, 15),
            (80, -45, 15), (80, 0, 15), (80, 45, 15),
            (0, 45, 15),
        ]
        for i, pos in enumerate(standoff_positions):
            self.draw_cylinder(pos, 3, 30, color='gold', alpha=0.9)

        # ==================== 顶板元件 ====================
        component_z = top_plate_z + body_height + 2

        # 1. 树莓派 3B (85.6 × 56 × 17 mm)
        rpi_x = -40
        rpi_y = 10
        self.draw_box((rpi_x, rpi_y, component_z + 8.5),
                     (85.6, 56, 17),
                     color='green', alpha=0.8, label='树莓派 3B\n85.6×56mm')

        # 2. PCA9685 (25 × 61 × 8 mm)
        pca_x = -40
        pca_y = -30
        self.draw_box((pca_x, pca_y, component_z + 4),
                     (61, 25, 8),
                     color='blue', alpha=0.8, label='PCA9685\n舵机驱动板')

        # 3. MPU6050 (GY-521, 15 × 20 × 3 mm)
        mpu_x = 5
        mpu_y = 0
        self.draw_box((mpu_x, mpu_y, component_z + 1.5),
                     (20, 15, 3),
                     color='purple', alpha=0.8, label='MPU6050\nIMU')

        # 4. LM2596 降压模块 ×2 (37 × 15 × 14 mm)
        lm1_x = 50
        lm1_y = 35
        self.draw_box((lm1_x, lm1_y, component_z + 7),
                     (37, 15, 14),
                     color='red', alpha=0.8, label='LM2596 #1\n(5V)')

        lm2_x = 50
        lm2_y = 8
        self.draw_box((lm2_x, lm2_y, component_z + 7),
                     (37, 15, 14),
                     color='red', alpha=0.8, label='LM2596 #2\n(6V)')

        # 5. 电池 (150 × 50 × 30 mm)
        battery_x = 50
        battery_y = -25
        self.draw_box((battery_x, battery_y, component_z + 15),
                     (70, 50, 30),
                     color='orange', alpha=0.7, label='2S 锂电池\n7.4V 5Ah')

        # 6. 电源开关（圆形，简化为小圆柱）
        switch_x = 30
        switch_y = -45
        self.draw_cylinder((switch_x, switch_y, component_z), 8, 10,
                          color='red', alpha=1.0, label='电源开关')

        # ==================== 髋关节舵机（底板固定）====================
        hip_servo_z = body_height + 18  # 舵机中心高度

        # 左前髋
        self.draw_servo((70, 45, hip_servo_z), rotation_axis='x',
                       label='左前髋\nCH0')

        # 右前髋
        self.draw_servo((70, -45, hip_servo_z), rotation_axis='x',
                       label='右前髋\nCH3')

        # 左后髋
        self.draw_servo((-70, 45, hip_servo_z), rotation_axis='x',
                       label='左后髋\nCH6')

        # 右后髋
        self.draw_servo((-70, -45, hip_servo_z), rotation_axis='x',
                       label='右后髋\nCH9')

        # ==================== 腿部结构（以左前腿为例）====================
        leg_start_z = hip_servo_z - 18

        # 左前腿
        fl_x, fl_y = 70, 45

        # U型支架 #1（肩关节）
        shoulder_z = leg_start_z - 25
        self.draw_u_bracket((fl_x, fl_y + 30, shoulder_z), label='U型支架')

        # 肩关节舵机
        self.draw_servo((fl_x, fl_y + 30, shoulder_z), rotation_axis='y',
                       label='左前肩\nCH1')

        # 上腿杆（100mm，简化为长方体）
        upper_leg_z = shoulder_z - 50
        self.draw_box((fl_x, fl_y + 30, upper_leg_z),
                     (10, 10, 100),
                     color='lightgreen', alpha=0.6, label='上腿杆\n100mm')

        # U型支架 #2（膝关节）
        knee_z = shoulder_z - 100
        self.draw_u_bracket((fl_x, fl_y + 30, knee_z), label='U型支架')

        # 膝关节舵机
        self.draw_servo((fl_x, fl_y + 30, knee_z), rotation_axis='y',
                       label='左前膝\nCH2')

        # 下腿杆（100mm）
        lower_leg_z = knee_z - 50
        self.draw_box((fl_x, fl_y + 30, lower_leg_z),
                     (8, 8, 100),
                     color='darkgreen', alpha=0.6, label='下腿杆\n100mm')

        # 足端球体
        foot_z = knee_z - 100
        self.draw_cylinder((fl_x, fl_y + 30, foot_z), 7, 14,
                          color='orange', alpha=1.0, label='足端')

        # ==================== 其他三条腿（简化绘制）====================
        # 右前腿
        fr_x, fr_y = 70, -45
        self.draw_u_bracket((fr_x, fr_y - 30, shoulder_z), label='')
        self.draw_servo((fr_x, fr_y - 30, shoulder_z), rotation_axis='y', label='右前肩\nCH4')
        self.draw_box((fr_x, fr_y - 30, upper_leg_z), (10, 10, 100), color='lightgreen', alpha=0.4)
        self.draw_u_bracket((fr_x, fr_y - 30, knee_z), label='')
        self.draw_servo((fr_x, fr_y - 30, knee_z), rotation_axis='y', label='右前膝\nCH5')
        self.draw_box((fr_x, fr_y - 30, lower_leg_z), (8, 8, 100), color='darkgreen', alpha=0.4)
        self.draw_cylinder((fr_x, fr_y - 30, foot_z), 7, 14, color='orange', alpha=1.0)

        # 左后腿
        rl_x, rl_y = -70, 45
        self.draw_u_bracket((rl_x, rl_y + 30, shoulder_z), label='')
        self.draw_servo((rl_x, rl_y + 30, shoulder_z), rotation_axis='y', label='左后肩\nCH7')
        self.draw_box((rl_x, rl_y + 30, upper_leg_z), (10, 10, 100), color='lightgreen', alpha=0.4)
        self.draw_u_bracket((rl_x, rl_y + 30, knee_z), label='')
        self.draw_servo((rl_x, rl_y + 30, knee_z), rotation_axis='y', label='左后膝\nCH8')
        self.draw_box((rl_x, rl_y + 30, lower_leg_z), (8, 8, 100), color='darkgreen', alpha=0.4)
        self.draw_cylinder((rl_x, rl_y + 30, foot_z), 7, 14, color='orange', alpha=1.0)

        # 右后腿
        rr_x, rr_y = -70, -45
        self.draw_u_bracket((rr_x, rr_y - 30, shoulder_z), label='')
        self.draw_servo((rr_x, rr_y - 30, shoulder_z), rotation_axis='y', label='右后肩\nCH10')
        self.draw_box((rr_x, rr_y - 30, upper_leg_z), (10, 10, 100), color='lightgreen', alpha=0.4)
        self.draw_u_bracket((rr_x, rr_y - 30, knee_z), label='')
        self.draw_servo((rr_x, rr_y - 30, knee_z), rotation_axis='y', label='右后膝\nCH11')
        self.draw_box((rr_x, rr_y - 30, lower_leg_z), (8, 8, 100), color='darkgreen', alpha=0.4)
        self.draw_cylinder((rr_x, rr_y - 30, foot_z), 7, 14, color='orange', alpha=1.0)

        # ==================== 地面参考线 ====================
        ground_z = foot_z - 10
        xx, yy = np.meshgrid(np.linspace(-120, 120, 2), np.linspace(-80, 80, 2))
        zz = np.full_like(xx, ground_z)
        self.ax.plot_surface(xx, yy, zz, alpha=0.1, color='gray')

        # ==================== 设置显示范围 ====================
        self.ax.set_xlim([-120, 120])
        self.ax.set_ylim([-80, 80])
        self.ax.set_zlim([ground_z, component_z + 60])

        # 添加标题
        self.ax.set_title('恐龙四足机器人 - 真实器件 3D 组装图\n' +
                         '基于实际采购的 DS3218 舵机和电子元件',
                         fontsize=14, fontweight='bold', pad=20)

        # 添加图例
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='lightblue', alpha=0.3, label='机身板 (亚克力 3mm)'),
            Patch(facecolor='#2C3E50', alpha=0.8, label='DS3218 舵机 (12个)'),
            Patch(facecolor='silver', alpha=0.6, label='U型支架 (8个)'),
            Patch(facecolor='green', alpha=0.8, label='树莓派 3B'),
            Patch(facecolor='blue', alpha=0.8, label='PCA9685 驱动板'),
            Patch(facecolor='orange', alpha=0.7, label='2S 锂电池'),
            Patch(facecolor='lightgreen', alpha=0.6, label='腿部连杆'),
        ]
        self.ax.legend(handles=legend_elements, loc='upper left', fontsize=10)

        # 添加信息文本
        info_text = (
            '总重: ~1.5kg\n'
            '机身: 200×110×60mm\n'
            '舵机: DS3218 × 12\n'
            'U型支架: 8个\n'
            '站立高度: ~250mm'
        )
        self.ax.text2D(0.02, 0.98, info_text, transform=self.ax.transAxes,
                      fontsize=10, verticalalignment='top',
                      bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        # 网格
        self.ax.grid(True, alpha=0.3)

    def show(self):
        """显示图形"""
        plt.tight_layout()

        # 添加交互提示
        print("\n" + "="*60)
        print("  恐龙四足机器人 - 真实器件 3D 可视化")
        print("="*60)
        print("\n交互操作:")
        print("  - 鼠标左键拖动: 旋转视角")
        print("  - 鼠标右键拖动: 平移")
        print("  - 鼠标滚轮: 缩放")
        print("  - 工具栏保存按钮: 保存为图片")
        print("\n关闭窗口退出")
        print("="*60 + "\n")

        plt.show()


def main():
    """主函数"""
    visualizer = RealComponentVisualizer()
    visualizer.visualize_assembly()
    visualizer.show()


if __name__ == '__main__':
    main()
