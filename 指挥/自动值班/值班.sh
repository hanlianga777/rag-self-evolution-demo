#!/bin/bash
# 自动值班脚本：每隔 5 分钟看一眼 GitHub 上的「指挥/队列/」，
# 有任务单就叫 Codex 命令行版去做，做完由本脚本保存（commit）并推回 GitHub。
#
# 用法（先 cd 到项目文件夹）：
#   bash 指挥/自动值班/值班.sh               正常值班，17:30 后不再开新任务，18:30 强制收工
#   bash 指挥/自动值班/值班.sh --once        只做一张任务单就结束（试跑用）
#   bash 指挥/自动值班/值班.sh --until 2300  改成 23:00 后不再开新任务
#
# 运行期间 Mac 不会自动休眠（需要插着电、不要合上盖子）。
# 想提前结束：在这个终端窗口按 Ctrl + C（会先保存已做的部分再退出）。
#
# 说明：Codex 命令行版在 workspace-write 模式下 .git 是只读的，自己无法 commit，
# 所以 git 操作（拉取、保存、推送）全部由本脚本负责，Codex 只改文件。

set -u

# ---------- 可调的设置 ----------
STOP_NEW="1730"          # 这个时间以后不再开始新任务单（时分，四位数）
HARD_STOP_AFTER=60       # 超过上面时间多少分钟，强制停掉正在做的任务
CHECK_EVERY=300          # 队列为空时，每隔多少秒看一次（300 = 5 分钟）
TASK_MAX_MIN=180         # 一张任务单最多做多少分钟
BIG_FILE=10485760        # 超过这个大小（10MB）的文件不上传
# Codex 的权限：能改项目文件夹、能联网（调用接口、启动本机 demo 需要）
CODEX_ARGS=(--sandbox workspace-write -c sandbox_workspace_write.network_access=true)
# --------------------------------

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
QUEUE="指挥/队列"
DONE_DIR="指挥/历史任务"
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

# 把 Codex 改过的文件保存成一次提交。数据库、.env、超过 10MB 的文件一律不放进去。
# 返回 0 = 有内容保存了；1 = 没有改动。
save_work() {
  local msg="$1" f skipped=""
  g add -A >/dev/null 2>&1
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    case "$(basename "$f")" in
      .env|.env.local|.env.*.local|*.db|*.sqlite|*.sqlite3|*.pem|*.key)
        g reset -q -- "$f" >/dev/null 2>&1; skipped="$skipped $f"; continue ;;
    esac
    if [ -f "$REPO/$f" ] && [ "$(wc -c < "$REPO/$f" | tr -d ' ')" -gt "$BIG_FILE" ]; then
      g reset -q -- "$f" >/dev/null 2>&1; skipped="$skipped $f"
    fi
  done < <(g diff --cached --name-only --diff-filter=AM)
  if [ -n "$skipped" ]; then
    say "这些文件不上传（数据/密钥/大文件），只留在本机：$skipped"
    # 记进本机忽略名单（.git/info/exclude，不会上传），以后不再当成"没保存的改动"
    for f in $skipped; do
      grep -qxF "/$f" "$REPO/.git/info/exclude" 2>/dev/null || echo "/$f" >> "$REPO/.git/info/exclude"
    done
  fi
  if g diff --cached --quiet; then return 1; fi
  g commit -q -m "$msg (No SPEC Change)" >/dev/null 2>&1
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
CODEX_PID=""
CUR_TASK=""
stop_codex() {
  [ -n "$CODEX_PID" ] || return 0
  pkill -TERM -P "$CODEX_PID" 2>/dev/null; kill -TERM "$CODEX_PID" 2>/dev/null
  sleep 10
  pkill -KILL -P "$CODEX_PID" 2>/dev/null; kill -KILL "$CODEX_PID" 2>/dev/null
  CODEX_PID=""
}

run_task() {
  local task="$1" name start elapsed prompt
  name="$(basename "$task" .md)"
  RUN_LOG="$LOGDIR/$(date +%Y%m%d-%H%M)-$name.log"
  prompt="这是无人值守的自动运行，没有人会回答你的问题，不要停下来等人确认。
1. 先读仓库根目录的 AGENTS.md 和 指挥/README.md，再读任务单 $task，严格按任务单执行。
2. 如果这张任务单之前做过一半（有半成品或写了一半的报告），先检查已有成果，从断点接着做，不要从头重来。
3. 遇到不清楚的地方：按任务单写明的默认做法处理，并在报告里注明「我是这样理解的」；实在没法做的那一项跳过，写进报告的「待回答问题」一节，其余照常做完。
4. 不要运行任何 git 命令去修改仓库（git add / commit / mv / push / pull / checkout / reset / stash 都不要用；.git 在你的环境里是只读的）。保存和推送由值班脚本负责。查看用的 git log / git diff / git status 可以用。
5. 全部完成后：报告写进 指挥/报告/，然后用普通的 mv 命令把这张任务单移到 指挥/历史任务/（例如 mv \"$task\" 指挥/历史任务/）。任务单被移走，就表示这张做完了。
6. 如果中途确实无法继续：把已完成的部分和原因写进报告，但不要移动任务单。"

  ( cd "$REPO" && exec codex exec "${CODEX_ARGS[@]}" "$prompt" </dev/null >"$RUN_LOG" 2>&1 ) &
  CODEX_PID=$!
  start=$(date +%s)
  while kill -0 "$CODEX_PID" 2>/dev/null; do
    sleep 30
    elapsed=$(( ( $(date +%s) - start ) / 60 ))
    if [ "$elapsed" -ge "$TASK_MAX_MIN" ] || { [ "$ONCE" -eq 0 ] && [ "$(now_min)" -ge "$HARD_STOP_MIN" ]; }; then
      stop_codex
      echo "[值班脚本] 超时，已强制停止（已做 ${elapsed} 分钟）" >> "$RUN_LOG"
      break
    fi
  done
  [ -n "$CODEX_PID" ] && wait "$CODEX_PID" 2>/dev/null
  CODEX_PID=""
}

# 按 Ctrl+C 或关窗口时：停掉 Codex，把已做的部分保存并推送，再退出
on_stop() {
  trap - HUP INT TERM
  echo
  if [ -n "$CUR_TASK" ]; then
    say "收到停止指令，正在停下 Codex 并保存已做的部分……"
    stop_codex
    save_work "值班中断：$CUR_TASK 已做部分" && push_now
    record "手动停止：$CUR_TASK 没做完，已做的部分已保存。下次值班会接着做"
  else
    record "手动停止值班"
  fi
  exit 130
}

# ---------- 开始 ----------
mkdir -p "$LOGDIR"
LOCK="$LOGDIR/.值班中.pid"
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  say "已经有一个值班窗口在运行了，这个窗口不再重复启动。"
  exit 1
fi

if ! command -v codex >/dev/null 2>&1; then
  say "找不到 Codex 命令行版（codex），请先完成安装。"
  exit 1
fi

# 开工前检查：项目里如果有没保存的改动（通常是桌面版做了一半的任务），先不开工，免得混在一起
if [ -n "$(g status --porcelain)" ]; then
  say "项目里有还没保存的改动（可能是 Codex 桌面版做了一半的任务），值班先不开始："
  g status --short | head -20
  say "请先让桌面版把那个任务做完并推送，再启动值班。"
  exit 1
fi

if [ "$ONCE" -eq 0 ] && [ "$(now_min)" -ge "$STOP_NEW_MIN" ]; then
  say "现在已经过了 ${STOP_NEW:0:2}:${STOP_NEW:2:2}，不开始值班。需要的话用 --until 改时间。"
  exit 0
fi

echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT
trap on_stop HUP INT TERM

if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -is -w $$ >/dev/null 2>&1 &
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
  CUR_TASK="$task"
  run_task "$task"
  name="$(basename "$task" .md)"

  if [ ! -e "$REPO/$task" ]; then
    # 任务单被移走 = 做完了
    save_work "任务 $name：自动值班完成"
    push_now
    CUR_TASK=""
    fails=0
    record "完成：$task"
    [ "$ONCE" -eq 1 ] && break
  else
    # 没做完：已做的部分先保存推送（下次从断点接着做）
    save_work "任务 $name：自动值班进行中（未完成，已做部分）" && push_now
    CUR_TASK=""
    if tail -n 80 "$RUN_LOG" | grep -Eiq 'usage limit|hit your limit|quota exceeded|exceeded your'; then
      record "额度用完，值班暂停：$task 没做完（已做部分已保存）。换号或用重置卡后，重新启动值班即可接着做"
      break
    fi
    fails=$((fails + 1))
    if [ "$fails" -ge 2 ]; then
      record "连续两次没做完，值班停止：$task（本机日志：$RUN_LOG）"
      break
    fi
    [ "$ONCE" -eq 1 ] && { record "试跑没做完：$task（本机日志：$RUN_LOG）"; break; }
    record "没做完，5 分钟后重试一次：$task"
    sleep "$CHECK_EVERY"
  fi
done

say "值班已结束，可以关掉这个窗口。"
