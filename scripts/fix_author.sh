#!/bin/bash
# 修复所有提交的作者信息为 tgut <lzhchen.free@gmail.com>
cd /mnt/data/tgut/code/dino_quadruped
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --env-filter '
export GIT_AUTHOR_NAME="tgut"
export GIT_AUTHOR_EMAIL="lzhchen.free@gmail.com"
export GIT_COMMITTER_NAME="tgut"
export GIT_COMMITTER_EMAIL="lzhchen.free@gmail.com"
' --tag-name-filter cat -- --all
echo "Done! Verifying:"
git log --format="%h %an <%ae> %s" --all
