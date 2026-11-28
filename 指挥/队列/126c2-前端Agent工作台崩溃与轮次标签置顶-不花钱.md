# 126c2：修复前端 Agent 工作台崩溃，轮次标签置顶（不花钱，插队；不影响 E8 运行）

- **依据**：用户 11-27 20:42 截图。
  1. Agent 工作台「进化路线」报「页面加载异常 Minified React error #31（object with keys {problem, fix}）」。
  2. 「第 1 轮 / 第 2 轮 / 第 3 轮 / Candidate D」这排标签被上方的「Agent 决策」区块挤到了下面。标签应该紧贴在 tab 下面，并固定在顶部。
- **总指挥已改好代码**，在本单所在的提交里：
  - `frontend/src/components/Strategy126cRound.tsx`：增加 `text()` 函数，后端返回的 `{problem, fix}` 等对象统一转成文字。
  - `frontend/src/ui/evolution/EvolutionTimeline.tsx`：新增 `roundHeader` 参数。
  - `frontend/src/pages/EvolutionPage.tsx`：「Agent 决策」区块改为放在轮次标签下面、每一轮的内容里面。

  轮次标签栏 `.route-round-switch` 原本就是 sticky，所以不用改 CSS。

## 要做的事

1. **不要停 E8，不要重启后端。** E8 由后端编排在跑。
2. `git pull` 后在 `frontend` 目录运行 `npm run build`。如果 tsc 报错，就地修到通过，不能改变上面三处修改的意图。相关的 vitest 测试也要跑一遍。
3. 让 5174 端口的 preview 读到新的构建产物。preview 读的是 dist，构建完刷新页面即可；如果需要重启前端进程，只重启前端。
4. 用只读浏览器核对四件事：
   - Agent 工作台的「概览」「进化路线」「回归与推荐」三个 tab 都能正常打开，没有报错；
   - 「进化路线」的轮次标签在最上面；
   - 页面往下滚动时，标签固定在顶部；
   - 每一轮的「Agent 决策」区块出现在标签下面。
5. 提交并推送。然后**继续执行 126d**，接着原来的断点续跑。

## 报告

- 文件：`指挥/报告/126c2.md`
- 首行格式：`126c2：React #31 已修=是；轮次标签置顶固定=是；build=通过；E8 未受影响=是；费用 $0`
