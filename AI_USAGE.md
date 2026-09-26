# AI_USAGE

## 使用的工具

本次实现使用 Codex 作为代码协作工具，主要用于：

- 快速阅读 FastAPI 路由、数据工具、Trace 结构和评测说明；
- 生成原生 HTML/CSS/JavaScript 看板初稿；
- 根据实际接口字段修正前端请求和展示逻辑；
- 起服务、调用接口、跑测试并检查浏览器呈现。

同时使用 Claude Code（Anthropic，Claude Opus 模型）作为终端内的辅助编码工具，主要用于：

- 阅读和解释仓库代码，定位问答链路与评测中的问题；
- 协助修改代码、补充测试并整理文档；
- 在本地运行测试与脚本，核对输出结果。

真实任务提示示例：

> 阅读 starter/kbqa 的接口和数据字段，设计一个零构建依赖的现代运营看板，必须包含日期/门店筛选、营业额趋势、Top 10 商品、数据质量、问答对话框和 Trace 调试抽屉；优先复用现有后端，不引入新依赖。

## 如何验证 AI 的输出

没有直接接受生成的接口假设。先阅读 `tools.py`、`server.py` 和 `trace.py`，确认 `top_products`、清洗报告、Trace steps 的真实字段后，才确定前端数据结构；同时保留后端接口校验，日期参数仍由 FastAPI 验证。

验证方式包括：

1. `python -m pytest starter/tests -q` 回归现有接口和问答测试。
2. 启动服务后请求 `/api/meta`、`/api/metrics/top-products`、`/api/data_quality` 和 `/api/chat`。
3. 在浏览器打开 `/`，切换日期/门店，发送问题并打开 Trace，检查真实数据是否刷新。

## 自己做的判断

- 选择原生 HTML/CSS/JS，而不是 React/Vite：仓库没有前端构建链，运营看板只需要一个可直接由 FastAPI 提供的页面；这样评审按三步即可启动。
- 选择 SVG 趋势图：当前只需折线、坐标和 hover 提示，不需要新增图表依赖。
- 将 Trace 放在抽屉式模态层：不打断看板主流程，且可在问答完成后直接查看本轮 `trace_id`。
- 新增 `/api/meta` 和 `/api/metrics/top-products`：前端不能硬编码门店和商品，也不应通过浏览器直接访问 SQLite。
