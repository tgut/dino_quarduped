#!/bin/bash
# v7 继续训练（从 checkpoint 恢复）
cd /mnt/data/tgut/code/dino_quadruped
echo "Resuming v7 training from checkpoint..."
echo "Target: 5M steps | 8 parallel envs"
echo "Log: logs/v7_train_resume.log"
nohup python rl/train_ppo.py --timesteps 5000000 --num-envs 8 --resume \
    > logs/v7_train_resume.log 2>&1 &
echo ""
echo "Training started! PID: $!"
echo "Monitor: tail -f /mnt/data/tgut/code/dino_quadruped/logs/v7_train_resume.log"
