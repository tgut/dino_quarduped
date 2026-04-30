# Dino Quadruped — 四足机器恐龙

基于 SpotMicro 硬件平台 + CHAMP 软件框架的四足机器恐龙项目，使用强化学习 (PPO) 训练行走策略。

## 项目结构

```
dino_quadruped/
├── urdf/                    # 机器人 URDF 模型
│   └── dino_quadruped.urdf  # 12-DOF SpotMicro 模型
├── rl/                      # 强化学习核心代码
│   ├── dino_env.py          # Gymnasium + PyBullet 仿真环境
│   ├── train_ppo.py         # PPO 训练脚本 (Stable-Baselines3)
│   └── record_eval_video.py # 评估视频录制
├── scripts/                 # 工具脚本
│   ├── benchmark.py         # 性能基准测试
│   ├── sim_standalone.py    # 独立仿真测试
│   └── ...                  # 诊断、可视化等脚本
├── docs/                    # 项目文档
│   ├── rl_v6_training_summary.md  # v6 训练总结报告
│   ├── hardware_architecture.md   # 硬件架构
│   ├── mechanical_design.md       # 机械结构设计
│   └── wiring_diagram.md         # 接线图
├── eval_output/             # 评估产出
│   ├── rl_v6_policy.mp4    # v6 策略行走视频
│   ├── baseline_v6.mp4     # baseline 对比视频
│   ├── training_curves_v6.png # 训练曲线
│   └── eval_v6_summary.json   # 评估指标
├── rl_logs/                 # 训练日志
│   ├── models/              # 模型 checkpoints
│   ├── tensorboard/         # TensorBoard 日志
│   └── training_log.json    # 训练过程记录
├── eval_v6.py               # v6 完整评估流水线
└── README.md
```

## 机器人参数

| 参数 | 值 |
|------|-----|
| 自由度 | 12 DOF (4腿 × 3关节) |
| 体重 | 1.5 kg |
| 体尺寸 | 200×110×60 mm |
| 腿长 | 上腿 100mm + 下腿 100mm |
| 仿真引擎 | PyBullet |

## 快速开始

### 环境安装

```bash
pip install stable-baselines3 gymnasium pybullet numpy
```

### 训练

```bash
# 默认 5M 步，8 并行环境
python rl/train_ppo.py

# 自定义参数
python rl/train_ppo.py --timesteps 2000000 --num-envs 4

# 从 checkpoint 恢复训练
python rl/train_ppo.py --resume
```

### 评估

```bash
# 运行评估 (10 episodes)
python rl/train_ppo.py --eval

# 录制评估视频
python rl/record_eval_video.py

# 完整 v6 评估流水线
python eval_v6.py
```

### TensorBoard 监控

```bash
tensorboard --logdir rl_logs/tensorboard
```

## RL 训练版本演进

| 版本 | 行为 | 核心问题 | 状态 |
|------|------|----------|------|
| v1 | 双腿蹦跳 | 步态理解错误 | 已废弃 |
| v2 | 趴在地上 | reward hacking | 已废弃 |
| v3/v4 | 冲刺摔倒 | 速度奖励过大 | 已废弃 |
| v5 | 站着不走 | alive bonus 压制速度奖励 | 已废弃 |
| v6 | 稳定行走 | 腿部抖动 | 基线版本 |
| **v7** | **平滑行走 (开发中)** | 控制频率+平滑惩罚优化 | **当前** |

### v6 成果 (里程碑版本)

- 100% 存活率 (10/10 episodes 跑满 1000 步)
- 前进速度 0.23 m/s (baseline 的 50 倍)
- 行走距离 4.45m (baseline 的 222 倍)

### v7 改进方向 (anti-tremor)

针对 v6 腿部抖动问题的优化：
- 控制频率提升：60Hz → 120Hz (action_repeat 4→2)
- 动作平滑性惩罚加强：-0.015 → -0.04
- 新增关节加速度惩罚：-0.002 × Σ(Δjoint_vel²)
- 足底接触奖励增大：0.15 → 0.25/foot
- 步态相位奖励增大：0.5 → 0.7
- 训练步数延长至 5M

## 技术栈

- **仿真**: PyBullet + Gymnasium
- **算法**: PPO (Stable-Baselines3)
- **并行化**: SubprocVecEnv (8 envs)
- **归一化**: VecNormalize (obs + reward)
- **硬件参考**: SpotMicro + CHAMP

## 项目路线

```
仿真先行 → 硬件点亮 → RL + 特色功能 → 展示
   ✅          ⬜           🔄              ⬜
```

## 可视化工具

### URDF 模型查看

```bash
# 快速 3D 查看（带关节控制）
python3 scripts/quick_view_urdf.py

# 或使用在线 URDF Viewer（无需安装）
# 访问: https://gkjohnson.github.io/urdf-loaders/javascript/example/bundle/
# 拖拽: urdf/dino_quadruped.urdf
```

### DXF 激光切割图查看

```bash
# 在线查看（推荐）
# 访问: https://sharecad.org/
# 上传: cad/body_top.dxf 或 cad/body_bottom.dxf

# 或本地查看
brew install --cask librecad  # macOS
librecad cad/body_bottom.dxf
```

### Three.js 交互式组装图

```bash
# 浏览器打开
open cad/assembly_3d_threejs.html
open cad/assembly_3d_view.html
```

**详细指南**: [可视化工具使用指南](docs/可视化工具使用指南.md)

---

## 📚 文档导航（完整目录）

### 🔧 硬件设计与采购
- [机械结构设计](docs/机械结构设计.md) — 结构尺寸、材料清单、组装步骤
- [硬件架构](docs/硬件架构.md) — 电子元件配置、供电方案
- [硬件对比与升级路线](docs/硬件对比.md) — 版本演进、配置差异
- [四足恐龙采购清单](docs/四足恐龙_淘宝加购清单.html) — 完整购物清单、配件尺寸

### 🦵 腿部结构与3D打印
- [腿部结构详细说明](docs/腿部结构详细说明.md) — 关节配置、舵机位置、轴承支持
- [3D打印件规格](docs/3D打印件规格_淘宝定制.md) — 打印参数、孔位、质量标准
- [STL文件使用说明](cad/STL文件使用说明.md) — 供应商指南、修改说明

### 🚀 软件与部署
- [可视化工具指南](docs/可视化工具使用指南.md) — URDF/DXF/Three.js 查看方法
- [RL v6 训练总结](docs/rl_v6_training_summary.md) — 训练结果、性能基准
- [CHAMP 框架说明](docs/CHAMP框架.md) — 软件架构、环境配置
- [接线图](docs/接线图.md) — 电路连接示意、信号定义
- [硬件验证与集成](docs/硬件验证流程.md) — 点亮、校准、测试流程

### 🎨 可视化
- [Three.js 交互式组装图](cad/assembly_3d_threejs.html) — 实时交互预览，可控制舵机演示动画
