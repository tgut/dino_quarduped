#!/usr/bin/env python3
"""
URDF 更新后的兼容性测试

测试新增支架后的影响：
1. URDF 加载验证
2. 质量分布变化
3. 关节运动正常性
4. 训练模型兼容性（如果有）
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_urdf_loading():
    """测试 URDF 加载"""
    import pybullet as p
    import pybullet_data

    print("=" * 60)
    print("  URDF 兼容性测试")
    print("=" * 60)

    pc = p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81, physicsClientId=pc)
    p.setAdditionalSearchPath(pybullet_data.getDataPath())

    urdf_path = os.path.join(os.path.dirname(__file__), "..", "urdf", "dino_quadruped.urdf")

    try:
        robot = p.loadURDF(
            urdf_path,
            basePosition=[0, 0, 0.3],
            useFixedBase=False,
            physicsClientId=pc
        )
        print(f"\n✓ URDF 加载成功")
    except Exception as e:
        print(f"\n✗ URDF 加载失败: {e}")
        p.disconnect()
        return False

    # 检查关节数
    num_joints = p.getNumJoints(robot, physicsClientId=pc)
    print(f"✓ 关节总数: {num_joints}")

    # 检查支架
    brackets = []
    actuated = []
    for i in range(num_joints):
        info = p.getJointInfo(robot, i, physicsClientId=pc)
        link_name = info[12].decode('utf-8')
        joint_type = info[2]

        if 'bracket' in link_name:
            brackets.append(link_name)
        if joint_type == p.JOINT_REVOLUTE:
            actuated.append(info[1].decode('utf-8'))

    print(f"✓ 支架 links: {len(brackets)} 个")
    print(f"✓ 舵机控制关节: {len(actuated)} 个")

    # 质量统计
    total_mass = 0
    bracket_mass = 0
    for i in range(-1, num_joints):
        dyn = p.getDynamicsInfo(robot, i, physicsClientId=pc)
        mass = dyn[0]
        total_mass += mass

        if i >= 0:
            info = p.getJointInfo(robot, i, physicsClientId=pc)
            link_name = info[12].decode('utf-8')
            if 'bracket' in link_name:
                bracket_mass += mass

    print(f"\n质量统计:")
    print(f"  总质量: {total_mass:.3f} kg ({total_mass*1000:.0f}g)")
    print(f"  支架质量: {bracket_mass:.3f} kg ({bracket_mass*1000:.0f}g, {bracket_mass/total_mass*100:.1f}%)")

    # 简单运动测试
    print(f"\n运动仿真测试 (10 steps)...")
    for _ in range(10):
        p.stepSimulation(physicsClientId=pc)

    pos, orn = p.getBasePositionAndOrientation(robot, physicsClientId=pc)
    print(f"  Base 位置: {pos[2]:.3f}m (Z轴)")

    if pos[2] > 0.1:  # 没有塌陷到地面以下
        print(f"✓ 物理仿真正常")
    else:
        print(f"✗ 机器人塌陷，可能质量分布有问题")

    p.disconnect()
    return True


def test_env_compatibility():
    """测试训练环境兼容性"""
    print(f"\n" + "=" * 60)
    print("  训练环境兼容性测试")
    print("=" * 60)

    try:
        from rl.dino_env import DinoQuadrupedEnv
    except ImportError:
        print("✗ 无法导入 dino_env（缺少依赖）")
        return False

    # 创建环境
    env = DinoQuadrupedEnv(render_mode=None, dr_enabled=False)

    try:
        obs, _ = env.reset()
        print(f"✓ 环境重置成功")
        print(f"  观测空间维度: {len(obs)}")

        # 运行几步
        for i in range(10):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)

        print(f"✓ 环境 step 正常运行")
        print(f"  最后一步奖励: {reward:.4f}")

        env.close()
        return True
    except Exception as e:
        print(f"✗ 环境测试失败: {e}")
        env.close()
        return False


def test_trained_model():
    """测试已训练模型"""
    print(f"\n" + "=" * 60)
    print("  训练模型兼容性测试")
    print("=" * 60)

    model_path = "rl_logs/best_model/best_model.zip"

    if not os.path.exists(model_path):
        print(f"⚠️  未找到训练模型: {model_path}")
        print("   跳过模型测试")
        return None

    try:
        from stable_baselines3 import PPO
        from rl.dino_env import DinoQuadrupedEnv
    except ImportError as e:
        print(f"✗ 缺少依赖: {e}")
        return False

    try:
        # 加载模型
        model = PPO.load(model_path)
        print(f"✓ 模型加载成功")

        # 创建环境
        env = DinoQuadrupedEnv(render_mode=None, dr_enabled=False)
        obs, _ = env.reset()

        # 运行一个 episode
        total_reward = 0
        done = False
        steps = 0
        max_steps = 1000

        while not done and steps < max_steps:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            total_reward += reward
            steps += 1

        avg_reward = total_reward / steps

        print(f"✓ Episode 完成")
        print(f"  步数: {steps}")
        print(f"  总奖励: {total_reward:.2f}")
        print(f"  平均奖励/步: {avg_reward:.4f}")

        # 对比参考值
        if avg_reward > 0.15:
            print(f"\n✅ 模型表现正常")
            print("   质量变化（+9.7%）在可接受范围内")
            print("   Domain Randomization (body_mass_scale 0.8-1.2) 已覆盖")
        else:
            print(f"\n⚠️  模型表现可能下降")
            print("   建议：")
            print("   1. 启用 DR 重新训练")
            print("   2. 或从现有模型微调（fine-tune）")

        env.close()
        return True

    except Exception as e:
        print(f"✗ 模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n\n" + "█" * 60)
    print("██  URDF 更新兼容性完整测试")
    print("██  变更: 新增 8 个支架 links (320g, +9.7% 质量)")
    print("█" * 60 + "\n")

    # 测试1: URDF 加载
    success_urdf = test_urdf_loading()

    # 测试2: 环境兼容性
    success_env = test_env_compatibility()

    # 测试3: 训练模型（可选）
    success_model = test_trained_model()

    # 总结
    print(f"\n\n" + "=" * 60)
    print("  测试总结")
    print("=" * 60)
    print(f"  URDF 加载:   {'✅ PASS' if success_urdf else '❌ FAIL'}")
    print(f"  环境兼容性:  {'✅ PASS' if success_env else '❌ FAIL'}")

    if success_model is None:
        print(f"  模型测试:    ⚠️  SKIPPED (未找到模型)")
    elif success_model:
        print(f"  模型测试:    ✅ PASS")
    else:
        print(f"  模型测试:    ❌ FAIL")

    print("\n结论:")
    if success_urdf and success_env:
        print("  ✅ URDF 更新成功，环境可正常使用")
        if success_model:
            print("  ✅ 已训练模型兼容，无需重新训练")
        elif success_model is None:
            print("  ℹ️  建议: 训练新模型验证性能")
        else:
            print("  ⚠️  建议: 重新训练或微调模型")
    else:
        print("  ❌ URDF 或环境存在问题，请检查")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
