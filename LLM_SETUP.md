# LLM 接入说明

## 1. 用了什么

问答服务使用 OpenAI 兼容的 Chat Completions 协议，默认目标是 DeepSeek `deepseek-flash`。HTTP 客户端为 `httpx`（见 `starter/requirements.txt`），没有使用厂商 SDK。请求只发送到 `{LLM_BASE_URL}/chat/completions`，不会自行补 `/v1`。

## 2. 配置从哪里读

| 配置项 | `.env` 示例值 | 作用 |
| --- | --- | --- |
| `LLM_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容服务地址，不含 `/chat/completions` |
| `LLM_API_KEY` | 空 | Bearer API Key |
| `LLM_MODEL` | `deepseek-flash` | 模型名 |
| `LLM_TIMEOUT` | `120` | 单次模型调用超时秒数 |
| `CHAT_BUDGET` | `150` | 单轮问答总预算秒数 |

配置由 `starter/kbqa/config.py` 启动时从 `starter/.env` 读取；同名环境变量优先，便于评测代理临时覆盖。`starter/.env` 已被 Git 忽略，可提交的模板是 `starter/.env.example`。服务不会在启动时校验 Key 或请求模型列表。

## 3. 怎么换成你们的

编辑本机 `starter/.env`，填入评审 Key：

```dotenv
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=替换成评审 Key
LLM_MODEL=deepseek-flash
```

然后重启服务：

```powershell
cd starter
python -m uvicorn kbqa.server:app --host 127.0.0.1 --port 8000
```

只改 `.env` 并重启服务即可，不需要重新清洗数据或重建知识库索引。也可用同名环境变量覆盖 `.env` 切换厂商、Key 和模型。只有替换 `data/` 或 `knowledge_base/` 时才执行 `python -m kbqa.rebuild`（或 `make rebuild`）。

## 4. 怎么看到发给模型的请求

推荐使用评测网关记录原始流量：

```bash
python eval/llm_gateway.py proxy --upstream https://api.deepseek.com --log llm_traffic.jsonl
```

把命令输出的代理地址放入 `LLM_BASE_URL`。另外，`/api/trace/{trace_id}` 会保存模型 endpoint、model、消息摘要、工具数量、最终提示词摘要、原始回答和 reasoning 摘要。示例（已脱敏）：

```json
{"endpoint":"http://127.0.0.1:.../chat/completions","model":"deepseek-flash","messages":4,"tools":8}
```

## 5. 没有 Key 时会怎样

没有同时配置三个 LLM 变量时，`llm_mode` 为 `mock`。服务仍可启动，`/api/health`、`/api/metrics/summary`、`/api/metrics/daily`、`/api/retrieve` 正常返回；`/api/chat` 使用本地 planner + answerer 从数据库和知识库作答，不调用外部模型。若 Live 调用超时、返回错误码或空回答，`/api/chat` 保持 HTTP 200，返回结构化 `refusal`，真实原因写入 Trace。

## 6. 依赖与安装

只需要 Python 3.12 和 `fastapi`、`uvicorn`、`httpx`、`python-dotenv`、`pytest`。模型不下载，首次启动耗时主要是清洗 SQLite 数据和建立轻量文本索引；无 Key 模式不需要网络。

## 7. 自测结果

预检命令：

```bash
python eval/llm_gateway.py preflight --service-url http://localhost:8000
```

提交时使用无 Key Mock 模式完成公开题库回归：55 / 55 题通过，详见 `EVAL_REPORT.md`。Live 模式的错误处理覆盖空内容、异常 `finish_reason`、工具参数 JSON 解析失败、HTTP 400/401/402/422/429/500/503、超时和重试；这些错误均不会让 `/api/chat` 返回 500。

## 8. 已知限制

- Trace 当前保存在进程内，服务重启后历史 Trace 不可查询。
- 前端图表使用内置 SVG，适合运营概览，不提供导出图片或钻取到订单明细。
- 评测网关预检需要评审环境提供自己的 Key；仓库没有真实 Key。
