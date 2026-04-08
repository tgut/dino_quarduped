#!/bin/bash
# v7 anti-tremor training launcher
cd /mnt/data/tgut/code/dino_quadruped
nohup python rl/train_ppo.py --timesteps 5000000 --num-envs 8 \
    > logs/v7_train.log 2>&1 &
echo "v7 Training started! PID: $!"
echo "Monitor: tail -f /mnt/data/tgut/code/dino_quadruped/logs/v7_train.log"
