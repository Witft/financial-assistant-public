# Architecture Overview（历史架构概览）

> 本文是保留的架构说明，用于解释来源版本的设计意图；其中的“当前”“主要”和目录职责不应被读取为当前实现、测试通过或发布状态。公开候选版的范围和限制以根目录 README、排除说明及最终载荷审查为准。

> 这份文档曾作为 **financial-assistant 的架构总览入口**。
> 
> - 想理解当时的项目边界、运行链路、目录职责：可先看这里。
> - 想看当时的 Agent-first 演进思路与细节：再看 `agent-first-architecture.md`。
> - 关于子目录副本的维护方式是历史去重建议，不构成当前文件状态的断言。

## 1. 历史项目定位

financial-assistant 是一个面向 **个人财务分析 + Agent 协作** 的 monorepo。

它不是单纯的“上传 CSV 看图表”工具，而是逐步演进成：

- **后端财务内核**：解析账单、分类、聚合、持久化
- **Agent 可调用接口层**：为 Hermes / MCP / 其他 Agent 提供结构化查询能力
- **人工协同前端**：上传账单、查看总览、处理待审核分类

## 2. 历史 Monorepo 结构

```text
financial-assistant/
├── backend/              # FastAPI + PostgreSQL + MCP wrapper
├── frontend/             # Vue + Vite dashboard/review console
├── docs/                 # 项目级架构/设计文档（推荐作为单一文档入口）
├── evals/                # 评测与回归资产（当时规划）
├── scripts/              # 构建/打包脚本
└── README.md             # 仓库级入口说明
```

## 3. 历史三层架构

### 3.1 Core Engine（后端财务内核）

位于 `backend/`，主要负责：

- 解析支付宝 / 微信 / 建行账单
- 统一交易字段与金额方向
- 执行本地分类规则与 AI 兜底分类
- 把交易写入 PostgreSQL（可选）
- 提供月度汇总与交易查询接口

当时将 `backend/api_server.py` 视为主要入口，并记录为“可用但待拆分”的形态。

### 3.2 Agent-Facing API / MCP 层

后端除了服务前端，也直接服务 Agent。

两个入口：

1. **HTTP Agent API**
   - `GET /api/agent/monthly-summary`
   - `GET /api/agent/transactions`
   - `GET /api/agent/months`

2. **MCP Server**
   - `backend/mcp_server.py`
   - 把上面的 HTTP 能力包装成 MCP 工具

这一层的目标是：**让 Agent 直接消费结构化财务数据，而不是从 UI 文本里反向提取。**

### 3.3 Human UI（人工协同前端）

位于 `frontend/`，主要负责：

- 上传账单
- 展示财务 Dashboard
- 展示待审核分类
- 允许人工修正分类，并把偏好同步回后端

前端不是系统唯一入口，而是“人工审核台 + 可视化视图”。

## 4. 历史运行链路

### 4.1 Web 用户链路

```text
用户上传账单
  -> frontend 调用 POST /api/parse
  -> backend 解析并分类
  -> 可选写入 PostgreSQL
  -> frontend store 持有交易数据
  -> dashboard/review 页面展示
  -> 人工修正分类后调用 POST /api/transactions/correct
```

### 4.2 Agent 查询链路

```text
Hermes / MCP Client
  -> MCP tool 或 HTTP Agent API
  -> backend/database.py 查询 PostgreSQL
  -> 返回结构化 JSON
  -> Agent 继续做总结、问答、提醒或自动化分析
```

## 5. 历史数据边界

### 无数据库模式

如果 `DATABASE_URL` 未配置：

- 前端上传解析仍可用
- `/api/parse` 返回交易结果
- Agent 查询接口不可用或无数据支撑

### 有数据库模式

如果 `DATABASE_URL` 已配置：

- 解析结果自动 upsert 到 PostgreSQL
- 上传账单变成“导入 + 落库”
- Agent 可以基于历史月份做持续查询与汇总

## 6. 历史关键设计决策

### 6.1 交易幂等 ID 由业务字段哈希生成

因为外部账单数据不一定有稳定主键，所以后端采用：

- `source`
- `date`
- `description`
- `amount`
- `type`

组合后生成稳定哈希 ID，用于重复导入时 upsert。

### 6.2 分类不确定时进入人工审核

系统不是追求“100% 自动化”，而是追求：

- 自动分类尽量准
- 不确定时显式进入 `pending review`
- 人工纠偏后形成可复用规则

### 6.3 UI 与 Agent 双通道并存

同一份财务数据，需要同时服务：

- **人类**：图表、列表、审核页
- **Agent**：结构化 JSON、稳定 schema、可脚本调用接口

## 7. 当时记录的主要技术债

1. `backend/api_server.py` 文件过大，解析/分类/路由/规则记忆耦合在一起。
2. 前后端历史分类体系仍未完全统一。
3. 项目已有测试，但缺少专门面向“能力回归”的 `evals/` 资产体系。
4. 架构文档此前在 `docs/` 和 `backend/docs/` 有重复副本，容易发生内容漂移。

## 8. 历史文档去重建议

当时建议将文档职责固定如下：

### 项目级文档（canonical）

放在 `docs/`：

- `architecture-overview.md`：架构总览，单一入口
- `agent-first-architecture.md`：详细演进设计
- 其他跨模块设计文档

### 子目录文档（local）

放在 `backend/docs/` / `frontend/...`：

- 只写模块特有补充
- 或保留“跳转指针”到 `docs/` 的 canonical 文档
- 不再复制整篇项目级架构文档

## 9. 历史推荐阅读顺序

1. `README.md`
2. `docs/architecture-overview.md`
3. `docs/agent-first-architecture.md`
4. `backend/README.md`
5. `frontend/README.md`
