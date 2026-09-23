# V1.0.1 Implementation Deviations

## Rerank mode

当前运行时使用的是“轻量二阶段重排”：归一化 Hybrid Score 与词法覆盖度结合后排序。它不是独立 Cross-Encoder Reranker Model。

本轮未引入或下载新的重型模型服务，以保持本地 Demo 启动稳定、无新增依赖。正式 UI 与版本快照将其标记为“轻量二阶段重排”，不得表述为独立 Rerank Model。
