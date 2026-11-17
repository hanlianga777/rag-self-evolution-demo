#!/usr/bin/env bash
# 总指挥发任务单前的自检：同一台机器上，对比"基准提交"和"当前工作区"的后端测试失败清单，只报新增失败。
# 不依赖环境里装没装全依赖：两边在同一环境跑，环境造成的失败两边都有，会互相抵消。
# 用法：bash scripts/preflight_tests.sh [基准提交，默认 HEAD]
# 退出码：0 = 没有新增失败；1 = 有新增失败（清单打印在最后）。
set -uo pipefail
BASE="${1:-HEAD}"
ROOT="$(git rev-parse --show-toplevel)"
WORK="$(mktemp -d)"
trap 'git -C "$ROOT" worktree remove --force "$WORK/base" >/dev/null 2>&1; rm -rf "$WORK"' EXIT

run_suite () {  # $1 = 代码目录, $2 = 输出文件
  ( cd "$1" && PYTHONPATH="backend:$ROOT/scripts" timeout 900 python3 -m pytest -q backend/tests -p no:cacheprovider -p preflight_clock \
      --continue-on-collection-errors -o faulthandler_timeout=60 -rfE 2>&1 ) \
    | grep -E '^(FAILED|ERROR) ' | sed -E 's/ - .*$//' | sort -u > "$2"
}

git -C "$ROOT" worktree add --detach "$WORK/base" "$BASE" >/dev/null 2>&1 || { echo "无法检出基准 $BASE"; exit 2; }
echo "基准 $BASE 运行中…"; run_suite "$WORK/base" "$WORK/base.txt"
echo "当前工作区运行中…";   run_suite "$ROOT" "$WORK/now.txt"
NEW="$(comm -13 "$WORK/base.txt" "$WORK/now.txt")"
FIXED="$(comm -23 "$WORK/base.txt" "$WORK/now.txt")"
echo "基准失败 $(wc -l < "$WORK/base.txt") 项，当前失败 $(wc -l < "$WORK/now.txt") 项。"
[ -n "$FIXED" ] && { echo "本次修好："; echo "$FIXED"; }
if [ -n "$NEW" ]; then echo "新增失败（必须先处理，不得发任务单）："; echo "$NEW"; exit 1; fi
echo "没有新增失败。"
