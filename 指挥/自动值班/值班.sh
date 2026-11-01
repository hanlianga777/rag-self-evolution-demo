#!/bin/bash
# 自动值班脚本：每隔 5 分钟看一眼 GitHub 上的「指挥/队列/」，
# 有任务单就叫 Codex 命令行版去做，做完把结果推回 GitHub。
#
# 用法（先 cd 到项目文件夹）：
#   bash 指挥/自动值班/值班.sh               正常值班，17:30 后不再开新任务
#   bash 指挥/自动值班/值班.sh --once        只做一张任务单就结束（试跑用）
#   bash 指挥/自动值班/值班.sh --until 2300  改成 23:00 后不再开新任务
#
# 运行期间 Mac 不会自动休眠（需要插着电、不要合上盖子）。
# 想提前结束：在这个终端窗口按 Ctrl + C，或直接关掉窗口。

set -u

# ---------- 可调的设置 ----------
STOP_NEW="1730"          # 这个时间以后不再开始新任务单（时分，四位数）
HARD_STOP_AFTER=60       # 超过上面时间多少分钟，强制停掉正在做的任务
CHECK_EVERY=300          # 队列为空时，每隔多少秒看一次（300 = 5 分钟）
TASK_MAX_MIN=180         # 一张任务单最多做多少分钟
# Codex 的权限：能改项目文件夹、能联网（调用接口、启动本机 demo 需要）
CODEX_ARGS=(--sandbox workspace-write -c sandbox_workspace_write.network_access=true)
# --------------------------------

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
QUEUE="指挥/队列"
RECORD="指挥/值班记录.md"
PAUSE_FILE="指挥/暂停"
LOGDIR="$HOME/RAG归档/值班日志"
ONCE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --once) ONCE=1 ;;
    --until) shift; STOP_NEW="${1:-$STOP_NEW}" ;;
  esac
  shift
done

to_min() { echo $(( 10#${1:0:2} * 60 + 10#${1:2:2} )); }
now_min() { to_min "$(date +%H%M)"; }
STOP_NEW_MIN=$(to_min "$STOP_NEW")
HARD_STOP_MIN=$(( STOP_NEW_MIN + HARD_STOP_AFTER ))

say() { echo "[$(date '+%m-%d %H:%M')] $*"; }
g() { git -C "$REPO" -c core.quotepath=off "$@"; }

push_now() {
  local i
  for i in 1 2 3; do
    if g push -q >/dev/null 2>&1; then return 0; fi
    g pull --rebase --autostash -q >/dev/null 2>&1
    sleep 5
  done
  say "推送到 GitHub 失败（可能是网络问题），下一轮再试"
  return 1
}

# 写一行记录到 指挥/值班记录.md 并推送，总指挥在 GitHub 上就能看到
record() {
  local msg="$1"
  say "$msg"
  g pull --rebase --autostash -q >/dev/null 2>&1
  if [ ! -f "$REPO/$RECORD" ]; then
    printf '# 自动值班记录\n\n由 值班.sh 自动写入，最新的在最下面。\n\n' > "$REPO/$RECORD"
  fi
  echo "- $(date '+%Y-%m-%d %H:%M') $msg" >> "$REPO/$RECORD"
  g add "$RECORD" >/dev/null 2>&1
  g commit -q -m "值班记录：$msg (No SPEC Change)" -- "$RECORD" >/dev/null 2>&1
  push_now
}

# 队列里按文件名排第一的任务单；以 _ 开头的是草稿，跳过
next_task() {
  local f
  for f in "$REPO/$QUEUE"/*.md; do
    [ -e "$f" ] || return 1
    case "$(basename "$f")" in _*) continue ;; esac
    echo "${f#$REPO/}"
    return 0
  done
  return 1
}

RUN_LOG=""
run_task() {
  local task="$1" name pid start elapsed prompt
  name="$(basename "$task" .md)"
  RUN_LOG="$LOGDIR/$(date +%Y%m%d-%H%M)-$name.log"
  prompt="这是无人值守的自动运行，没有人会回答你的问题，不要停下来等人确认。
1. 先读仓库根目录的 AGENTS.md 和 指挥/README.md，再读任务单 $task，严格按任务单执行。
2. 如果这张任务单之前做过一半（有半成品或写了一半的报告），先检查已有成果，从断点接着做，不要从头重来。
3. 遇到不清楚的地方：按任务单写明的默认做法处理，并在报告里注明「我是这样理解的」；实在没法做的那一项跳过，写进报告的「待回答问题」一节，其余照常做完。
4. 全部完成后：报告写进 指挥/报告/，用 git mv 把这张任务单移到 指挥/历史任务/，然后 git add 相关文件并 git commit。不需要推送，值班脚本会负责推送。
5. 如果中途确实无法继续：把已完成的部分和原因写进报告并 git commit，但不要移动任务单。"

  ( cd "$REPO" && exec codex exec "${CODEX_ARGS[@]}" "$prompt" </dev/null >"$RUN_LOG" 2>&1 ) &
  pid=$!
  start=$(date +%s)
  while kill -0 "$pid" 2>/dev/null; do
    sleep 30
    elapsed=$(( ( $(date +%s) - start ) / 60 ))
    if [ "$elapsed" -ge "$TASK_MAX_MIN" ] || { [ "$ONCE" -eq 0 ] && [ "$(now_min)" -ge "$HARD_STOP_MIN" ]; }; then
      pkill -TERM -P "$pid" 2>/dev/null; kill -TERM "$pid" 2>/dev/null
      sleep 10
      pkill -KILL -P "$pid" 2>/dev/null; kill -KILL "$pid" 2>/dev/null
      echo "[值班脚本] 超时，已强制停止（已做 ${elapsed} 分钟）" >> "$RUN_LOG"
      break
    fi
  done
  wait "$pid" 2>/dev/null
}

# ---------- 开始 ----------
mkdir -p "$LOGDIR"
LOCK="$LOGDIR/.值班中.pid"
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  say "已经有一个值班窗口在运行了，这个窗口不再重复启动。"
  exit 1
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT
trap 'exit 130' HUP INT TERM

if ! command -v codex >/dev/null 2>&1; then
  say "找不到 Codex 命令行版（codex），请先完成安装。"
  exit 1
fi
if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -is -w $$ >/dev/null 2>&1 &
fi

if [ "$ONCE" -eq 0 ] && [ "$(now_min)" -ge "$STOP_NEW_MIN" ]; then
  say "现在已经过了 ${STOP_NEW:0:2}:${STOP_NEW:2:2}，不开始值班。需要的话用 --until 改时间。"
  exit 0
fi

if [ "$ONCE" -eq 1 ]; then
  record "值班开始（试跑，只做一张）"
else
  record "值班开始（${STOP_NEW:0:2}:${STOP_NEW:2:2} 后不再开新任务）"
fi

fails=0
while :; do
  if [ "$ONCE" -eq 0 ] && [ "$(now_min)" -ge "$STOP_NEW_MIN" ]; then
    record "到点，值班结束"
    break
  fi
  if ! g pull --rebase --autostash -q >/dev/null 2>&1; then
    say "从 GitHub 拉取失败（可能是网络问题），稍后再试"
    sleep "$CHECK_EVERY"; continue
  fi
  if [ -e "$REPO/$PAUSE_FILE" ]; then
    say "总指挥要求暂停，等待中"
    [ "$ONCE" -eq 1 ] && break
    sleep "$CHECK_EVERY"; continue
  fi
  if ! task="$(next_task)"; then
    say "队列是空的，等待新任务单"
    [ "$ONCE" -eq 1 ] && break
    sleep "$CHECK_EVERY"; continue
  fi

  record "开始：$task"
  run_task "$task"
  push_now

  if [ ! -e "$REPO/$task" ]; then
    fails=0
    record "完成：$task"
    [ "$ONCE" -eq 1 ] && break
  else
    if tail -n 80 "$RUN_LOG" | grep -Eiq 'usage limit|rate.?limit|quota|hit your limit|429'; then
      record "额度用完，值班暂停：$task 没做完。换号或用重置卡后，重新启动值班即可接着做"
      break
    fi
    fails=$((fails + 1))
    if [ "$fails" -ge 2 ]; then
      record "连续两次没做完，值班停止：$task（本机日志：$RUN_LOG）"
      break
    fi
    record "没做完，5 分钟后重试一次：$task"
    sleep "$CHECK_EVERY"
  fi
done

say "值班已结束，可以关掉这个窗口。"
