# 独立问答试验预览设计

## 目标

让基线与候选方案在问答试验页独立发起、独立计时、独立完成与逐字展示；页面在不刷新浏览器的前提下跨导航保留本轮状态。

## 边界

- 不改真实 PDF 语料、检索、模型配置、Citation 格式或已有 `/api/preview` 的响应契约。
- 不引入 SSE、轮询、新依赖或浏览器刷新后的持久化。
- 每个 Pipeline 仅展示自身接口返回的实际 `latency_ms`；不得用统一等待时间或前端延时伪造结果。

## API

新增两个与现有 preview 一样受可信 Origin 保护的接口，均使用现有 `PreviewRequest` 校验：

- `POST /api/preview/baseline`：返回 `pipeline`、`question`、`version`、`answer`、`latency_ms`。基线展示不进行独立检索或模型生成，其耗时是该接口实际处理耗时。
- `POST /api/preview/candidate`：返回 `pipeline`、`question`、`version`、`answer`、`mode`、`model`、`latency_ms`、`fallback_reason`、`sources` 与 `evidence`。复用当前候选检索、LIVE 与 Mock 回退逻辑。

`POST /api/preview` 保持现有兼容响应：它复用相同的基线与候选构造逻辑，再组合为当前的 `baseline` / `candidate_b` 结构，供 AI 问答等既有调用继续使用。

## 前端状态与交互

问答试验页对同一问题并发调用两个新接口。每一列维护独立的 `idle`、`thinking`、`complete`、`error` 状态与开始时间：

- `thinking`：显示本列浏览器已等待的时间与省略号。
- `complete`：立即显示接口返回的真实耗时，并从该列回答的第一个字符开始逐字输出；不等待另一列。
- `error`：仅在对应列显示可读错误，另一列照常保留或完成。

初始态始终渲染回答卡和独立参数卡，参数值明确标为等待提问或未运行，不伪造模型或检索结果。

`App` 持续挂载 `ExperimentPage`，通过 `hidden` 切换可见性。因此同一未刷新的浏览器会话可跨导航保留问题、独立请求状态、回答、Citation 与参数；浏览器刷新后恢复初始态。

## 视觉收敛

- AI 问答输入占位色与问答试验统一。
- Pipeline 原生下拉使用加粗小字号。
- 引用链接按内容宽度呈现下划线，不填充整行。
- 参数卡为回答列约三分之二宽，紧凑排列；回答区仍是主视觉。

## 验证

- 后端 API 测试：两个新接口的输入校验、可信 Origin、独立真实耗时与兼容 `/api/preview`。
- 前端测试：并发请求、一列先完成时立即逐字显示、另一列仍显示思考、错误隔离，以及跨导航保留状态。
- 运行后端全量测试、前端全量测试、生产构建与浏览器桌面复核。
