#!/bin/bash
# 盯梢脚本：给 Claude（总指挥）用，在 Claude 自己的云端环境里后台运行，不在用户 Mac 上跑。
# 每隔 2 分钟看一眼 GitHub 上的 指挥/值班记录.md 和 指挥/队列/，
# 出现需要总指挥处理的情况就退出（退出 = 叫醒总指挥）：
#   1. 队列空了，并且有任务刚做完 → 该验收、排下一张了
#   2. 值班停了 / 结束了 / 连续没做完 / 手动停止 → 要看原因
# 「额度用完……自动接着做」不叫醒（值班脚本自己会等）。
#
# 用法：bash 指挥/自动值班/盯梢.sh [--每完成一张就叫醒]
# 总指挥用后台方式运行它（最长 2 小时），2 小时内没动静也会退出，退出后重新启动即可。

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
BR="$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"
EVERY="${WATCH_EVERY:-120}"
LIMIT_MIN=115
WAKE_EACH=0
[ "${1:-}" = "--每完成一张就叫醒" ] && WAKE_EACH=1

g() { git -C "$REPO" -c core.quotepath=off "$@"; }
rec() { g show "origin/$BR:指挥/值班记录.md" 2>/dev/null; }
queue_left() { g ls-tree --name-only "origin/$BR" "指挥/队列/" 2>/dev/null | grep -E '\.md$' | grep -v '/_' ; }

g fetch -q origin 2>/dev/null
start_lines=$(rec | wc -l)
start_ts=$(date +%s)
echo "盯梢开始：$(date '+%m-%d %H:%M')，值班记录现有 $start_lines 行，队列：$(queue_left | xargs -n1 basename 2>/dev/null | tr '\n' ' ')"

while :; do
  sleep "$EVERY"
  g fetch -q origin 2>/dev/null || continue
  new="$(rec | tail -n +$((start_lines + 1)))"
  if [ -n "$new" ]; then
    if echo "$new" | grep -Eq '值班结束|值班停止|手动停止|连续两次|试跑没做完|晚于今天收工'; then
      echo "【叫醒原因】值班停了或结束了"; echo "$new"; exit 0
    fi
    if echo "$new" | grep -q '完成：'; then
      if [ "$WAKE_EACH" -eq 1 ] || [ -z "$(queue_left)" ]; then
        echo "【叫醒原因】有任务做完了，队列剩余：$(queue_left | xargs -n1 basename 2>/dev/null | tr '\n' ' ')"
        echo "$new"; exit 0
      fi
    fi
  fi
  if [ $(( ( $(date +%s) - start_ts ) / 60 )) -ge "$LIMIT_MIN" ]; then
    echo "【叫醒原因】2 小时到了（例行查看）"; [ -n "$new" ] && echo "$new"; exit 0
  fi
done
