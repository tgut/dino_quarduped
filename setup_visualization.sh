#!/bin/bash
# 恐龙四足机器人 - 可视化环境安装脚本

echo "=========================================="
echo " 安装 PyBullet 3D 可视化环境"
echo "=========================================="

# 检查是否在项目目录
if [ ! -f "urdf/dino_quadruped.urdf" ]; then
    echo "❌ 错误：请在项目根目录运行此脚本"
    echo "   cd /Users/tgut/Documents/code/dino_quadruped"
    exit 1
fi

# 创建虚拟环境
echo "→ 创建 Python 虚拟环境..."
python3 -m venv venv_viz

# 激活虚拟环境
echo "→ 激活虚拟环境..."
source venv_viz/bin/activate

# 升级 pip
echo "→ 升级 pip..."
pip install --upgrade pip

# 安装依赖
echo "→ 安装 PyBullet..."
pip install pybullet

echo "→ 安装 matplotlib（备用）..."
pip install matplotlib

echo "→ 安装 numpy..."
pip install numpy

echo ""
echo "=========================================="
echo " ✅ 安装完成！"
echo "=========================================="
echo ""
echo "使用方法："
echo ""
echo "1. 激活虚拟环境："
echo "   source venv_viz/bin/activate"
echo ""
echo "2. 运行 PyBullet 可视化："
echo "   python3 cad/visualize_assembly.py"
echo ""
echo "3. 运行 Matplotlib 可视化："
echo "   python3 cad/visualize_real_components.py"
echo ""
echo "4. 退出虚拟环境："
echo "   deactivate"
echo ""
echo "=========================================="
