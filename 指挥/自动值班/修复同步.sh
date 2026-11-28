#!/bin/bash
# 一键修复「从 GitHub 拉取失败」。
# 这个报错多数不是网络问题：本机做完的提交和 GitHub 上总指挥的改动动了同一个文件
# （比如一边把任务单移到历史任务，一边把它改名），git 的 rebase 卡在半路，之后每次拉取都失败。
#
# 用法（在项目文件夹里）：bash 指挥/自动值班/修复同步.sh
# 做的事：放弃卡住的 rebase → 本机状态备份到本地分支「值班备份-时间」→ 合并 GitHub 版本
#        （冲突处以本机为准；值班记录/互审/规则总表两边都保留）→ 推送。不删除任何本机文件。

set -u
REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "请先 cd 到项目文件夹再运行"; exit 1; }
g() { git -C "$REPO" -c core.quotepath=off "$@"; }

echo "== 1/5 放弃卡住的 rebase/合并（不丢提交）"
if [ -d "$REPO/.git/rebase-merge" ] || [ -d "$REPO/.git/rebase-apply" ]; then
  g rebase --abort 2>/dev/null || g rebase --quit 2>/dev/null
  echo "   已放弃卡住的 rebase"
else
  echo "   没有卡住的 rebase"
fi
[ -f "$REPO/.git/MERGE_HEAD" ] && g merge --abort 2>/dev/null

mkdir -p "$REPO/.git/info"
for line in '指挥/值班记录.md merge=union' '指挥/互审/*.md merge=union' '指挥/规则总表.md merge=union'; do
  grep -qxF "$line" "$REPO/.git/info/attributes" 2>/dev/null || echo "$line" >> "$REPO/.git/info/attributes"
done

echo "== 2/5 备份本机状态"
stashed=0
if ! g diff --quiet || ! g diff --cached --quiet; then
  g stash push -q -m "修复同步 $(date +%m%d-%H%M)" && stashed=1 && echo "   没保存的改动已暂存"
fi
backup="值班备份-$(date +%Y%m%d-%H%M%S)"
g branch "$backup" HEAD && echo "   本机提交已备份到本地分支 $backup"
g for-each-ref --sort=-refname --format='%(refname:short)' 'refs/heads/值班备份-*' | tail -n +3 | while read -r b; do g branch -D "$b" >/dev/null 2>&1; done

echo "== 3/5 从 GitHub 取最新"
if ! g fetch origin; then
  echo "   取不下来：这次确实是网络问题，请稍后再运行本脚本"
  [ "$stashed" -eq 1 ] && g stash pop -q
  exit 1
fi
up="$(g rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || echo origin/main)"

echo "== 4/5 合并"
if g -c merge.directoryRenames=false merge --no-edit -X ours -X no-renames "$up" >/dev/null 2>&1; then
  echo "   合并成功"
else
  g status --short | grep -E '^(UU|AA|DD|AU|UA|DU|UD) ' | sed 's/^/   冲突文件：/'
  g add -A
  g reset -q -- '*.db' '*.sqlite' '*.sqlite3' '.env' '.env.*' 2>/dev/null
  if g commit -q --no-edit; then
    echo "   结构冲突（改名/移动）已按本机文件夹现状收下"
  else
    g merge --abort 2>/dev/null
    [ "$stashed" -eq 1 ] && g stash pop -q
    echo "   自动合并没成功，什么都没改。请把上面的输出截图发给总指挥"
    exit 1
  fi
fi
[ "$stashed" -eq 1 ] && { g stash pop -q 2>/dev/null || echo "   注意：暂存的改动在 git stash 里，没丢"; }

echo "== 5/5 推送"
if g push -q; then
  echo "完成：已和 GitHub 同步。现在重新启动值班脚本即可。"
else
  echo "推送失败，请把上面的输出截图发给总指挥"
  exit 1
fi
