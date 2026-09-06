# 财务助手：Agent-first 架构演进设计文档（历史设计 rationale）

> 本文保留当时的架构方向和风险边界，供理解设计意图；它不是当前实现清单、运行状态或发布承诺。示例字段和值仅用于说明结构，不代表公开载荷中的真实财务数据。

## 1. 架构理念：从“人机交互”到“智能体协同”

### 1.1 核心差异
| 维度 | 传统 Web 财务助手 | Agent-first 财务助手 |
| --- | --- | --- |
| **主要使用者** | 人类（通过浏览器点击和查看） | AI Agent（通过 API/协议拉取并分析数据，向人汇报） |
| **功能入口** | Dashboard、表单、按钮 | 自然语言对话、自动化定时任务（Cron） |
| **页面定位** | 系统的绝对主体，承担所有操作 | **退居二线**，定位为“高阶可视化仪表盘”与“人工审核台” |
| **数据输出** | 为人类渲染的 HTML、Markdown、图表 | **双轨制**：给人类看图表，给 Agent 提供严格结构化 JSON |
| **决策模式** | 机器统计数据，人类得出结论 | 机器与 Agent 统计并得出结论，人类审批/纠偏 |

### 1.2 产品定位三层结构
1. **底层财务大脑 (Core Engine)**：基于 Python FastAPI 提供的纯粹计算与数据清洗能力。
2. **AI 代理交互层 (API/MCP)**：通过标准的 REST API 或 Model Context Protocol (MCP)，将“大脑”能力开放给任何 LLM/Agent。
3. **人类协同审核台 (Human UI)**：Vue + Spring Boot 网关构成的后台，只用于数据修正、高危操作授权以及复杂宏观图表查看。

---

## 2. Core Engine 核心能力规划 (Python 端)

作为财务大脑，需要具备以下原子能力：
1. **解析与分类 (Categorize)**：对原始流水进行打标，必须包含结构化分类、金额提取。
2. **多维统计 (Aggregate)**：支持按月、周、分类、标签等多维度输出聚合统计。
3. **异常检测 (Anomaly Detection)**：发现异常大额支出、重复扣款或偏离历史基线的消费。
4. **预算监控 (Budget Monitor)**：结合预算设定，给出当前进度的结构化报警等级。
5. **周期性分析 (Report Generation)**：生成支持 Agent 二次解读的周期财务快照（数据切片）。

---

## 3. Agent-Facing API 设计规范 (关键点)

为了让 Agent 用得爽且不出错，接口不能像以前一样直接返回 Markdown 文本，需要遵循以下原则：

### 3.1 稳定且富含下文的 Schema
返回的 JSON 必须包含丰富的决策上下文：
```json
{
  "transaction_id": "tx_10023",
  "inferred_category": "餐饮美食",
  "confidence": 0.85,           // 【关键】让 Agent 知道自己该不该向人类确认
  "reason": "包含关键词'星巴克'，且属于高频小额消费",
  "requires_human_review": false 
}
```

### 3.2 错误码与自修复提示
如果 Agent 调用出错，接口需要告诉 Agent **下一步该怎么做**：
```json
{
  "error_code": "INVALID_DATE_FORMAT",
  "message": "月份格式错误",
  "suggestion": "请使用 YYYY-MM 格式重试，例如 2026-04" 
}
```

---

## 4. 隐私、安全与人机边界

Agent 获取了财务数据，必须设定严格的边界：
1. **敏感数据最小暴露**：API 默认对交易对手账号、卡号等进行脱敏，除非 Agent 明确使用 `need_sensitive_info=true` 且具备高权限 token。
2. **Human-in-the-loop (人工介入)**：
   * 当 `confidence < 0.7`（例如出现没见过的消费类型）。
   * 当单笔开销超标或者预测即将严重超支时。
   * Agent 不自动写库更改核心数据，而是生成“待定事项”放入 Vue Dashboard 的审核列表，或推送到飞书等待指令 `[确认/修改]`。
3. **操作审计日志**：记录每一次 Agent 的分析请求和数据修改记录，支持防伪溯源。

---

## 5. 历史重构路线图（提案，非当前状态）

### Phase 1: Python API 结构化改造（当时提案）
* 将现有的 `/api/analyze` 和 `/api/categorize` 接口剥离 Markdown/文本渲染逻辑。
* 重新定义 Pydantic Schema，强制返回结构化 JSON（包含 `confidence` 和 `reason`）。
* 跑通至少一个针对新 API 的纯结构化测试用例。

### Phase 2: Agent 链路打通 (Hermes 接入)
* 编写供 Hermes 调用的本地 Skill，封装对上述 API 的请求（或者直接编写一套基础的 MCP Server）。
* 在飞书端测试：直接对话查询“本月目前花了多少钱”、“有没有异常账单”。

### Phase 3: 网关与前端改造为“审核台” (Spring Boot + Vue)
* 升级 Spring Boot 的路由与鉴权逻辑，区分 Human Request 与 Agent Request。
* 在 Vue Dashboard 添加“待处理事项 (Pending Review)” 面板，承接 Agent 认为不确定的分类。
* 优化可视化图表，直接拉取 Phase 1 改造好的结构化接口数据。