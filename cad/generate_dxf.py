#!/usr/bin/env python3
"""
恐龙四足机器人 - 机身板 DXF 生成脚本

根据 docs/机械结构设计.md 中的尺寸参数生成激光切割用 DXF 文件。
板材: 3mm 亚克力, 尺寸 200mm × 110mm

生成文件:
  - body_top.dxf    顶部机身板（树莓派/PCA9685/MPU6050/电池安装位）
  - body_bottom.dxf  底部机身板（舵机安装孔/走线槽）
"""

import ezdxf
from ezdxf import units
import math
import os

# ── 全局参数 ──────────────────────────────────────────────
BOARD_W = 200.0  # mm, X 方向
BOARD_H = 110.0  # mm, Y 方向
CORNER_R = 3.0   # 板材圆角半径

# M3 孔径 (激光切割通常预留 0.1mm)
M3_HOLE = 3.2
M2_5_HOLE = 2.7

# 铜柱孔位 (8 个, 距边 10mm 的矩阵)
STANDOFF_INSET = 10.0
STANDOFF_POSITIONS = [
    (STANDOFF_INSET, STANDOFF_INSET),
    (STANDOFF_INSET, BOARD_H / 2),
    (STANDOFF_INSET, BOARD_H - STANDOFF_INSET),
    (BOARD_W / 2, STANDOFF_INSET),
    (BOARD_W / 2, BOARD_H - STANDOFF_INSET),
    (BOARD_W - STANDOFF_INSET, STANDOFF_INSET),
    (BOARD_W - STANDOFF_INSET, BOARD_H / 2),
    (BOARD_W - STANDOFF_INSET, BOARD_H - STANDOFF_INSET),
]

# DS3218 舵机安装尺寸 (底板用)
# 舵机底座安装孔间距约 50mm × 20mm, M3 螺丝
SERVO_MOUNT_DX = 50.0
SERVO_MOUNT_DY = 20.0
# 四角舵机中心位置 (距角落偏移)
SERVO_OFFSET_X = 30.0
SERVO_OFFSET_Y = 25.0
SERVO_CENTERS = [
    (SERVO_OFFSET_X, SERVO_OFFSET_Y),                        # 左前
    (BOARD_W - SERVO_OFFSET_X, SERVO_OFFSET_Y),              # 右前
    (SERVO_OFFSET_X, BOARD_H - SERVO_OFFSET_Y),              # 左后
    (BOARD_W - SERVO_OFFSET_X, BOARD_H - SERVO_OFFSET_Y),    # 右后
]


def add_rounded_rect(msp, x, y, w, h, r, layer="OUTLINE"):
    """绘制圆角矩形轮廓"""
    # 四段直线 + 四段圆弧
    pts = [
        # 底边 (左→右)
        ((x + r, y), (x + w - r, y)),
        # 右边 (下→上)
        ((x + w, y + r), (x + w, y + h - r)),
        # 顶边 (右→左)
        ((x + w - r, y + h), (x + r, y + h)),
        # 左边 (上→下)
        ((x, y + h - r), (x, y + r)),
    ]
    for p1, p2 in pts:
        msp.add_line(p1, p2, dxfattribs={"layer": layer})

    # 圆弧: (center, radius, start_angle, end_angle)
    arcs = [
        ((x + r, y + r), 180, 270),          # 左下
        ((x + w - r, y + r), 270, 360),       # 右下
        ((x + w - r, y + h - r), 0, 90),      # 右上
        ((x + r, y + h - r), 90, 180),         # 左上
    ]
    for center, sa, ea in arcs:
        msp.add_arc(center, r, sa, ea, dxfattribs={"layer": layer})


def add_circle(msp, cx, cy, d, layer="HOLES"):
    """添加一个圆孔 (d=直径)"""
    msp.add_circle((cx, cy), d / 2.0, dxfattribs={"layer": layer})


def add_rect_slot(msp, x, y, w, h, layer="SLOTS"):
    """添加矩形槽/开口"""
    msp.add_lwpolyline(
        [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)],
        dxfattribs={"layer": layer},
    )


def add_mounting_holes_rect(msp, cx, cy, dx, dy, hole_d, layer="HOLES"):
    """在中心 (cx,cy) 周围添加 4 个矩形分布的安装孔"""
    for sx in (-1, 1):
        for sy in (-1, 1):
            add_circle(msp, cx + sx * dx / 2, cy + sy * dy / 2, hole_d, layer)


def generate_body_top(output_path):
    """生成顶板 DXF"""
    doc = ezdxf.new("R2010")
    doc.units = units.MM
    msp = doc.modelspace()

    # 定义图层
    doc.layers.add("OUTLINE", color=7)   # 白色 - 外轮廓切割线
    doc.layers.add("HOLES", color=1)     # 红色 - 圆孔
    doc.layers.add("SLOTS", color=3)     # 绿色 - 槽/开口
    doc.layers.add("ENGRAVE", color=5)   # 蓝色 - 标注/雕刻线

    # 1. 外轮廓
    add_rounded_rect(msp, 0, 0, BOARD_W, BOARD_H, CORNER_R, "OUTLINE")

    # 2. 铜柱孔 (M3)
    for px, py in STANDOFF_POSITIONS:
        add_circle(msp, px, py, M3_HOLE, "HOLES")

    # 3. 树莓派 3B 安装位 (4 × M2.5 孔, 58mm × 49mm)
    RPI_CX = 60.0
    RPI_CY = 65.0
    RPI_DX = 58.0
    RPI_DY = 49.0
    add_mounting_holes_rect(msp, RPI_CX, RPI_CY, RPI_DX, RPI_DY, M2_5_HOLE, "HOLES")
    # 标注框
    add_rect_slot(msp, RPI_CX - 42, RPI_CY - 28, 85, 56, "ENGRAVE")
    msp.add_text("RPi 3B", dxfattribs={
        "layer": "ENGRAVE", "height": 4,
    }).set_placement((RPI_CX, RPI_CY - 2))

    # 4. PCA9685 安装位 (孔距待实测, 暂不开孔)
    PCA_CX = 60.0
    PCA_CY = 28.0
    # TODO: 收到 PCA9685 后实测安装孔间距，取消注释并修改 dx/dy
    # PCA_DX = 20.0   # 待实测
    # PCA_DY = 50.0   # 待实测 (当前值导致孔距板边仅 1.65mm, 疑似有误)
    # add_mounting_holes_rect(msp, PCA_CX, PCA_CY, PCA_DX, PCA_DY, M2_5_HOLE, "HOLES")
    add_rect_slot(msp, PCA_CX - 13, max(0, PCA_CY - 25), 26, 50, "ENGRAVE")
    msp.add_text("PCA9685", dxfattribs={
        "layer": "ENGRAVE", "height": 3.5,
    }).set_placement((PCA_CX - 11, PCA_CY - 2))

    # 5. MPU6050 安装位 (GY-521 模块 15×20mm, 无安装孔, 仅排针)
    #    固定方式: 排针座插接(焊在万能板上) + 双面胶粘贴 + 扎带辅助固定
    #    两侧各 1 个 2mm 扎带孔, 穿细扎带压住模块
    MPU_CX = 105.0
    MPU_CY = 45.0
    MPU_W = 15.0   # 模块实际宽度
    MPU_H = 20.0   # 模块实际高度
    STRAP_D = 2.0   # 扎带孔直径
    # 扎带孔: 模块长边两侧各 1 个 (沿 Y 轴方向, 距模块边缘 3mm)
    add_circle(msp, MPU_CX - MPU_W / 2 - 3, MPU_CY, STRAP_D, "HOLES")
    add_circle(msp, MPU_CX + MPU_W / 2 + 3, MPU_CY, STRAP_D, "HOLES")
    # 标注框 (实际模块尺寸 15×20mm)
    add_rect_slot(msp, MPU_CX - MPU_W / 2, MPU_CY - MPU_H / 2, MPU_W, MPU_H, "ENGRAVE")
    msp.add_text("MPU6050", dxfattribs={
        "layer": "ENGRAVE", "height": 3,
    }).set_placement((MPU_CX - 10, MPU_CY - 2))

    # 6. 电池固定位 (顶板右侧, 魔术贴 + M3 扎带孔防脱落)
    #    电池尺寸约 105×35×25mm (2S 5000mAh)
    #    四角各一个 3.5mm 扎带孔, 用于穿扎带/魔术贴带 固定电池
    BAT_X = 125.0
    BAT_Y = 38.0
    BAT_W = 55.0
    BAT_H = 30.0   # 缩小以避免上边扎带孔与 LM2596#2 安装孔过近 (原45→30)
    STRAP_HOLE = 3.5  # 扎带孔直径
    STRAP_INSET = 5.0  # 距标注框边缘
    add_rect_slot(msp, BAT_X, BAT_Y, BAT_W, BAT_H, "ENGRAVE")
    # 四角扎带孔 (穿尼龙扎带或魔术贴带固定电池)
    for sx in (BAT_X + STRAP_INSET, BAT_X + BAT_W - STRAP_INSET):
        for sy in (BAT_Y + STRAP_INSET, BAT_Y + BAT_H - STRAP_INSET):
            add_circle(msp, sx, sy, STRAP_HOLE, "HOLES")
    # 额外: 电池中部两个扎带槽 (长条孔, 穿宽魔术贴带)
    BELT_SLOT_W = 15.0
    BELT_SLOT_H = 3.0
    for belt_y in (BAT_Y + 10, BAT_Y + BAT_H - 10):
        add_rect_slot(msp, BAT_X + BAT_W / 2 - BELT_SLOT_W / 2,
                      belt_y - BELT_SLOT_H / 2,
                      BELT_SLOT_W, BELT_SLOT_H, "SLOTS")
    msp.add_text("BATTERY", dxfattribs={
        "layer": "ENGRAVE", "height": 4,
    }).set_placement((BAT_X + 10, BAT_Y + 18))

    # 7. LM2596 降压模块 ×2 安装位
    #    LM2596 模块尺寸约 43×21mm, 安装孔间距约 37×15mm, M3
    LM_DX = 37.0  # 安装孔 X 间距
    LM_DY = 15.0  # 安装孔 Y 间距

    # LM2596 #1 (5V, 靠近树莓派)
    LM1_CX = 150.0
    LM1_CY = 90.0
    add_mounting_holes_rect(msp, LM1_CX, LM1_CY, LM_DX, LM_DY, M3_HOLE, "HOLES")
    add_rect_slot(msp, LM1_CX - 22, LM1_CY - 12, 44, 24, "ENGRAVE")
    msp.add_text("LM2596#1", dxfattribs={
        "layer": "ENGRAVE", "height": 3,
    }).set_placement((LM1_CX - 14, LM1_CY - 2))
    msp.add_text("5V", dxfattribs={
        "layer": "ENGRAVE", "height": 2.5,
    }).set_placement((LM1_CX - 4, LM1_CY - 8))

    # LM2596 #2 (6V, 靠近 PCA9685)
    LM2_CX = 150.0
    LM2_CY = 63.0
    add_mounting_holes_rect(msp, LM2_CX, LM2_CY, LM_DX, LM_DY, M3_HOLE, "HOLES")
    add_rect_slot(msp, LM2_CX - 22, LM2_CY - 12, 44, 24, "ENGRAVE")
    msp.add_text("LM2596#2", dxfattribs={
        "layer": "ENGRAVE", "height": 3,
    }).set_placement((LM2_CX - 14, LM2_CY - 2))
    msp.add_text("6V", dxfattribs={
        "layer": "ENGRAVE", "height": 2.5,
    }).set_placement((LM2_CX - 4, LM2_CY - 8))

    # 8. 电源开关安装孔 (后边缘偏右, 避开中央铜柱)
    #    实际订单: 16mm 金属钮子开关 (带灯, 12-24V, 10A)
    #    铜柱位于 (100, 10)，需要避开; 开关半径 8.25mm 需离板边 ≥9mm
    SWITCH_CX = 130.0  # 偏右，避开 x=100 铜柱和 x=70 PCA9685 孔
    SWITCH_CY = 10.0   # 距底边 10mm，确保不超出板材 (半径 8.25 < 10)
    SWITCH_HOLE = 16.5  # 16mm 开关 + 0.5mm 余量
    add_circle(msp, SWITCH_CX, SWITCH_CY, SWITCH_HOLE, "SLOTS")
    msp.add_text("SW", dxfattribs={
        "layer": "ENGRAVE", "height": 3,
    }).set_placement((SWITCH_CX + 10, SWITCH_CY - 1.5))

    # 9. USB 接口开口 (左侧边缘, 方便树莓派 USB 口插拔)
    USB_SLOT_X = 0  # 左边缘
    USB_SLOT_Y = 58.0
    USB_SLOT_W = 3.5  # 板厚方向贯穿
    USB_SLOT_H = 18.0  # 覆盖两个 USB 口高度
    # 边缘 U 型开口: x 起点 = 0 (板边), 激光从边缘切入
    add_rect_slot(msp, USB_SLOT_X, USB_SLOT_Y, USB_SLOT_W, USB_SLOT_H, "SLOTS")

    doc.saveas(output_path)
    print(f"  ✓ {output_path}")


def generate_body_bottom(output_path):
    """生成底板 DXF"""
    doc = ezdxf.new("R2010")
    doc.units = units.MM
    msp = doc.modelspace()

    doc.layers.add("OUTLINE", color=7)
    doc.layers.add("HOLES", color=1)
    doc.layers.add("SLOTS", color=3)
    doc.layers.add("ENGRAVE", color=5)

    # 1. 外轮廓
    add_rounded_rect(msp, 0, 0, BOARD_W, BOARD_H, CORNER_R, "OUTLINE")

    # 2. 铜柱孔 (M3) - 和顶板完全对应
    for px, py in STANDOFF_POSITIONS:
        add_circle(msp, px, py, M3_HOLE, "HOLES")

    # 3. 四角舵机安装孔 (每个舵机 4 × M3)
    for scx, scy in SERVO_CENTERS:
        # DS3218 安装孔分布
        add_mounting_holes_rect(
            msp, scx, scy,
            SERVO_MOUNT_DX, SERVO_MOUNT_DY,
            M3_HOLE, "HOLES"
        )
        # 舵机输出轴开口 (20mm × 12mm 矩形槽, 供舵机轴穿过)
        add_rect_slot(
            msp, scx - 10, scy - 6, 20, 12, "SLOTS"
        )

    # 4. 中央走线槽 (长条形开口, 方便线缆穿过)
    SLOT_X = 55.0
    SLOT_Y = BOARD_H / 2 - 5
    SLOT_W = 90.0
    SLOT_H = 10.0
    add_rect_slot(msp, SLOT_X, SLOT_Y, SLOT_W, SLOT_H, "SLOTS")

    # 5. 额外走线孔 (圆形, 在舵机区域之间)
    for wy in [30, BOARD_H - 30]:
        add_circle(msp, BOARD_W / 2, wy, 8.0, "SLOTS")

    # 6. 标注文字
    msp.add_text("BOTTOM", dxfattribs={
        "layer": "ENGRAVE", "height": 5,
    }).set_placement((BOARD_W / 2 - 12, BOARD_H / 2 + 15))
    msp.add_text("200x110 3mm ACRYLIC", dxfattribs={
        "layer": "ENGRAVE", "height": 3,
    }).set_placement((BOARD_W / 2 - 30, BOARD_H / 2 - 20))

    doc.saveas(output_path)
    print(f"  ✓ {output_path}")


if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    print("生成恐龙四足机器人机身板 DXF...")
    generate_body_top(os.path.join(out_dir, "body_top.dxf"))
    generate_body_bottom(os.path.join(out_dir, "body_bottom.dxf"))
    print("完成！文件保存在 cad/ 目录下。")
