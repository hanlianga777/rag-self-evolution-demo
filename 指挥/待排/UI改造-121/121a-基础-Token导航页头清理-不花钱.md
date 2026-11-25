# 121a 前端基础：Token、导航分组与单击 bug、页头、清理样式来源（不花钱）

先读 `指挥/待排/UI改造-121/00-共同规范.md`，全部遵守。只改 `frontend/`。

## 要做的事

1. **tokens.css**
   - 新建 `src/ui/tokens.css`。从概览页现有样式提取颜色、字号、间距、圆角、阴影，写成 CSS 变量；变量值以概览页现状为准，规范表只给范围。
   - Tailwind 4 通过 `@theme` 或直接 `var()` 引用这些变量。
2. **样式入口收敛**
   - `main.tsx` 改成只引入一个入口，例如 `src/ui/index.css`。由它按顺序 `@import`：tokens → 基础样式 → 布局 → 组件。
   - `task024a-polish.css`、`task033b-polish.css`、`task034-polish.css`、`ui/extra.css` 逐条核对：
     - 仍然生效的规则，迁到对应的组件或页面样式里；
     - 已失效的规则删除；
     - 最后删掉这几个文件。
   - 迁移前后要对 8 个页面的首屏各做一次本机截图对比，确认没有意外变化。截图不提交。
3. **深色导航分组**
   - 按共同规范第一节分成三组，分组标题用小号浅灰字；保留图标和 active 态。
   - 移动菜单同样分组。
4. **修导航要点两次才切页的 bug**
   - `App.tsx` 的 `navigate` 同时写 `location.hash` 和调用 `setPage`，再加上 hashchange 监听、prefetch、Suspense，有竞争。
   - 先查清根因，写进报告，再修。
   - 验收：8 个页面两两互切（56 次），每次单击一次就切换成功。
   - 补一个单测：模拟点击导航，断言页面切换。
5. **页头统一**
   - `PageShell` 页头统一为三部分：标题（24px）、一句职责说明（不超过 1 行，删掉「这里……」式长句）、可选的右侧操作区。
   - 8 页都用它。页头文案在 `helpText.ts` 里改。
6. **清理第二套样式来源**
   - 删除样例库：`ui/Gallery.tsx`、`ui/PageSamples.tsx`、`ui/pages3.tsx`、`ui/gallery-main.tsx`、`frontend/ui-gallery.html`、`ui/evolution/fixture.ts`，以及只服务于它们的测试。
   - 删除前先 grep，确认生产页面没有引用。
7. **合并两套 Primitives**
   - `components/Primitives.tsx` 和 `ui/Primitives.tsx` 合并成一套，放在 `ui/Primitives.tsx`，全站改为从这里引入。
   - 组件接口不变，只改 import 路径。

## 验收

- 共同规范第五节全部满足。
- 8 页首屏与迁移前视觉一致；唯一允许的变化是导航分组和页头精简。
- `main.tsx` 只剩 1 个样式 import；仓库里不再有 `task0xx-polish.css`。
- 导航单击切页的单测通过；报告里写明根因。
- 56 次切换逐项记录「点击 → 路由 → 页面主标题」三项都正确，不能只看菜单高亮。
- 页头使用共同规范四之二第 7 条的 8 句。
