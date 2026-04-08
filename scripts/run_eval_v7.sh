#!/bin/bash
cd /mnt/data/tgut/code/dino_quadruped
python rl/record_eval_video.py
echo "Done! Video at: eval_output/rl_v7_policy.mp4"
