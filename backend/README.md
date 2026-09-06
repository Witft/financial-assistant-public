# Backend

财务助手后端，基于 **FastAPI**，承担三个核心职责：

- 解析支付宝 / 微信 / 建设银行账单
- 执行本地规则分类 + AI 兜底分类
- 对外提供 Web API 和 Agent/MCP 可调用的数据接口

另外，当配置 `DATABASE_URL` 时，解析结果会自动 upsert 到 PostgreSQL，供后续月度汇总和交易明细查询使用。

## 当前能力

### 面向 Web / 前端

- `POST /api/parse`：解析账单文件（CSV / XLS / XLSX）
- `POST /api/categorize`：批量 AI 分类
- `POST /api/analyze`：AI 财务诊断
- `POST /api/transactions/correct`：保存人工纠偏规则

### 面向 Agent / MCP

- `GET /api/agent/monthly-summary`：月度汇总
- `GET /api/agent/transactions`：交易明细
- `GET /api/agent/months`：已上传月份列表

### MCP 服务

- `mcp_server.py`：把 Agent 查询接口包装成 MCP 工具
- 暴露工具：`monthly_summary` / `query_transactions` / `list_months`

## 目录结构

```text
backend/
├── api_server.py         # FastAPI 主应用，当前核心业务入口
├── database.py           # PostgreSQL 持久化、月度汇总、交易查询
├── mcp_server.py         # MCP stdio server
├── tests/                # pytest 用例
├── docs/                 # 后端侧文档（以指针/补充说明为主）
├── skill/                # 供 Agent/Hermes 使用的辅助脚本与说明
├── .env.example
└── requirements.txt
```

## 环境要求

- Python 3.11+ 推荐
- 可选 PostgreSQL（启用持久化时需要）

## 安装依赖

```bash
pip install -r requirements.txt
```

## 环境变量

复制模板：

```bash
cp .env.example .env
```

关键变量：

- `DEEPSEEK_API_KEY`：启用 AI 分类 / AI 财务诊断
- `DEEPSEEK_BASE_URL`：可选，默认 `https://api.deepseek.com/v1`
- `DEEPSEEK_MODEL`：可选，默认 `deepseek-chat`
- `DATABASE_URL`：可选；配置后 `/api/parse` 会自动写入 PostgreSQL

## 启动方式

### 方式 1：直接运行

```bash
python api_server.py
```

### 方式 2：用 uvicorn

```bash
uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
```

默认地址：

```text
http://localhost:8000
```

Swagger 文档：

```text
http://localhost:8000/docs
```

## 持久化行为

如果没有配置 `DATABASE_URL`：

- `/api/parse` 仍然可以正常返回解析结果
- 但不会写入数据库
- Agent 查询接口不可用

如果配置了 `DATABASE_URL`：

- `/api/parse` 会把交易 upsert 到 PostgreSQL
- 主键不是外部账单原始 ID，而是基于稳定业务字段生成的哈希 ID
- 重复上传相同账单时可以保持幂等

这部分逻辑在 `database.py`。

## 业务规则

### 分类策略

当前分类是“两层结构”：

1. 本地规则优先：`classify_transaction()`
2. AI 兜底：`/api/categorize`

### 纠偏记忆

当用户在前端审核页改分类后，前端会调用 `/api/transactions/correct`，后端把偏好写入本地规则记忆，供后续解析直接命中。

### 金额约定

- `expense`：支出，金额通常为负
- `income`：收入，金额通常为正
- `transfer`：转账，保留原始语义

## 运行测试

```bash
pytest
```

常用：

```bash
pytest tests/test_api.py -v
pytest tests/test_parse.py -v
pytest tests/test_database_persistence.py -v
pytest tests/test_mcp_server.py -v
```

当前测试覆盖重点包括：

- 账单解析
- API 返回结构
- 数据库持久化
- 分类规则与置信度
- 交易状态与人工审核
- MCP 包装层

## MCP 开发

本地启动 MCP server：

```bash
python mcp_server.py
```

它依赖：

- `FINANCIAL_API_URL`：FastAPI 服务地址
  - 本地默认：`http://127.0.0.1:8000`
  - 部署场景下要特别确认是不是 FastAPI 端口，而不是前端端口

## 架构文档

建议按这个顺序阅读：

- `../docs/architecture-overview.md`：单一入口的整体架构总览
- `../docs/agent-first-architecture.md`：Agent-first 详细演进设计
- `docs/agent-first-architecture.md`：后端文档指针，避免重复维护

## 当前技术债

- `api_server.py` 仍然偏大，解析、分类、路由、规则记忆还耦合在单文件里。
- 前后端分类体系仍存在历史包袱，需要继续收敛。
- 目前已有测试基础，后续适合把关键回归场景逐步沉淀到仓库根目录 `evals/`。
