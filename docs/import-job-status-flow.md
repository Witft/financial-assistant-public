# Import Job Status Flow Design（历史设计）

> 本设计文档记录 `financial-assistant` 的 import job 状态流转提案。
>
> **历史范围：** 本文不能证明当前候选版已实现这些状态、字段或接口，也不能作为测试通过或发布就绪依据。请以当前源码和载荷审查为准。

## Goal

把”上传账单 -> 解析分类 -> 写库 -> 待审核 -> 人工纠偏”的链路变成**显式状态流转**。

核心对象：

```text
账单导入任务（import job）— 由 POST /api/parse 触发
```

---

## 1. 为什么先选 import job

它已经是项目里最真实、最核心的一条链路：

- 有明确入口：前端上传文件，调用 `POST /api/parse`
- 有多阶段处理：解析 -> 分类 -> 落库 -> 前端展示
- 有明确失败点：文件格式错误、解析异常、数据库写入异常
- 有明确人工兜底点：低置信度 / `requires_human_review=true`

相比直接给所有交易、所有 Agent 查询都加状态，当时先把 import job 状态化被视为更符合 **YAGNI + Month 2 最小工程骨架**。

---

## 2. 设计背景

在 import job 状态化之前，系统里已存在”状态”，但它们散落在不同层：

### 后端（改造前）
- `/api/parse` 成功返回 `success=true`
- 解析报错时直接抛 `500`
- 有数据库时写入 PostgreSQL；无数据库时只返回 message
- 分类不确定时给交易打 `requires_human_review=true`

### 前端（改造前）
- UploadPage 根据返回结果决定跳 Dashboard 还是 ReviewPage
- ReviewPage 用 `pendingReviews` 过滤：
  - `requires_human_review === true`
  - 或 `category === 'other' / '其他'`
- 人工纠偏后通过 `/api/transactions/correct` 把单笔记录从待审核中移出

改造前的问题是：

> 系统没有一个地方能回答”这次导入任务现在整体处于什么状态”。

---

## 3. 这次要显式化的对象

## 3.1 Job 级对象：`import_job`

代表“一次上传/导入账单任务”。

它关心：
- 任务是否开始
- 是否正在执行
- 是否整体成功
- 是否整体失败
- 是否进入人工审核阶段

## 3.2 交易级对象：`transaction`

交易本身不引入一整套复杂状态机，暂时沿用现有字段：
- `requires_human_review`
- `confidence`
- `category`

也就是说：

- **Job 状态**回答“这一批导入整体怎么样”
- **Transaction 审核标记**回答“这一笔是否还需要人看”

这样可以避免第一步就把粒度做得过细。

---

## 4. 提议的 Job 状态定义

该历史提案使用 Month 2 规划里约定的 5 个状态：

- `PENDING`
- `RUNNING`
- `SUCCEEDED`
- `FAILED`
- `REVIEW_REQUIRED`

### 4.1 含义

#### `PENDING`
任务已创建，但后端还未真正开始处理。

#### `RUNNING`
后端已接管任务，正在执行解析 / 分类 / 落库中的一个或多个阶段。

#### `SUCCEEDED`
任务主链路已成功完成，且**没有遗留待审核交易**。

#### `FAILED`
任务在解析、分类、落库等阶段出现**致命错误**，无法继续推进。

#### `REVIEW_REQUIRED`
任务主链路已完成基础处理，但存在待人工确认的交易，因此任务不能算彻底完成。

---

## 5. 提议的第一版状态流转

## 5.1 Happy path（无待审核）

```text
PENDING -> RUNNING -> SUCCEEDED
```

场景：
- 文件可识别
- 解析成功
- 分类完成
- 数据库写入成功（若启用）
- 没有 `requires_human_review=true` 的交易

## 5.2 成功但需人工审核

```text
PENDING -> RUNNING -> REVIEW_REQUIRED -> SUCCEEDED
```

场景：
- 文件解析成功
- 部分交易低置信度 / 其他分类
- 前端进入 ReviewPage
- 用户完成全部必要纠偏后，任务整体转为 `SUCCEEDED`

这里的关键决定是：

> `REVIEW_REQUIRED` 不是失败，而是“成功走到人工协同阶段”。

## 5.3 致命失败

```text
PENDING -> RUNNING -> FAILED
```

场景：
- 文件格式无法识别
- 解析过程抛异常
- PostgreSQL 持久化异常（在数据库模式下）
- 关键中间步骤失败且无可接受兜底

---

## 6. 提议的状态判定规则

### 6.1 什么时候创建 `PENDING`
在 `POST /api/parse` 一进入时创建 job。

### 6.2 什么时候进入 `RUNNING`
当后端开始读取文件并进入解析逻辑时。

### 6.3 什么时候进入 `FAILED`
出现以下任一情况：
- 文件为空 / 非支持格式
- 解析函数抛出不可恢复异常
- 数据库启用时，事务写入失败
- 其他导致本次导入结果不可用的错误

### 6.4 什么时候进入 `REVIEW_REQUIRED`
满足以下两个条件：
- 导入主链路已跑完（至少拿到了交易列表）
- 存在至少一笔交易满足：
  - `requires_human_review = true`
  - 或业务上等价于待审核（当前前端兼容逻辑里包括 `category == other/其他`）

### 6.5 什么时候进入 `SUCCEEDED`
满足以下条件之一：
- 导入完成且无待审核交易
- 导入先进入 `REVIEW_REQUIRED`，后续人工完成所有必要纠偏

---

## 7. 提议字段

## 7.1 `import_jobs` 表

提议字段：

- `id`
- `status`
- `source`（alipay / wechat / ccb / unknown）
- `filename`
- `total_transactions`
- `review_required_count`
- `persisted_count`
- `error_message`
- `created_at`
- `started_at`
- `finished_at`
- `updated_at`

### 字段意图

- `status`：当前整体状态
- `total_transactions`：本次导入解析出多少笔
- `review_required_count`：当前还有多少笔待人工处理
- `persisted_count`：写库多少笔，帮助区分”解析成功”和”落库成功”
- `error_message`：失败时可追踪

---

## 8. 提议的执行记录（`import_job_runs`）

提议的 `import_job_runs` 表字段如下：
- `id`
- `job_id`
- `step`
- `final_status`
- `input_summary`（JSONB）
- `model_version`
- `output_summary`（JSONB）
- `error_message`
- `retry_count`
- `started_at`
- `finished_at`
- `updated_at`

### 提议的 step
- `parse_bill` — 解析账单文件
- `persist_transactions` — 写入数据库
- `awaiting_human_review` — 等待人工审核

`output_summary` 中通常会记录：
- `total_transactions`
- `persisted_count`
- `review_required_count`
- `failure_policy`（`no_retry_needed` / `handoff_to_human_review` / `mark_failed_and_stop`）

这样可以在不引入复杂 trace 平台的前提下，回答”失败死在哪一步”。

---

## 9. 与当时接口设想的映射

## 9.1 `POST /api/parse`

第一版建议承担：
- 创建 job
- 推进 `PENDING -> RUNNING`
- 解析 / 分类 / 持久化
- 根据结果写入 `SUCCEEDED / REVIEW_REQUIRED / FAILED`
- 返回 `job_id`

### 提议的 ParseResponse 返回字段
- `success`
- `transactions`
- `message`
- `job_id` — 本次导入任务 ID
- `run_id` — 本次执行记录 ID
- `job_status` — 任务最终状态
- `review_required_count` — 待审核交易数
- `persisted_count` — 实际写入数据库的笔数

这样前端不需要完全靠”猜测 message + 扫交易列表”来判断整体状态。

## 9.2 `GET /api/import-jobs/latest`

返回最近创建的一次 import job；若无记录则 `job=null`。

响应包含 job 完整字段，以及嵌套的 `latest_run` 执行记录。

## 9.3 `GET /api/import-jobs/{job_id}`

按 `job_id` 查询指定导入任务详情。

- 存在 → 返回完整 job + `latest_run`
- 不存在 → `404`

## 9.4 `POST /api/transactions/correct`

当时希望它能够：
- 保存用户分类偏好
- 写回单笔 PostgreSQL 交易分类

第一版建议扩一层职责：
- 若请求附带 `job_id`，则在纠偏后检查该 job 的 `review_required_count`
- 当最后一笔待审核交易被处理完成时：
  - job 状态从 `REVIEW_REQUIRED` -> `SUCCEEDED`

注意：
- 这一步不要求前端马上一次性重构完
- 但后端设计上要预留这个闭环

---

## 10. 与前端设想的映射

## 10.1 UploadPage
该设计假定上传成功后仍可基于返回的 transactions 列表做判断（兼容原有逻辑）；后续可改为优先看 `job_status`：
- `job_status == REVIEW_REQUIRED` -> 跳 ReviewPage
- `job_status == SUCCEEDED` -> 跳 Dashboard
- `job_status == FAILED` -> 展示错误

## 10.2 ReviewPage
ReviewPage 继续基于交易列表工作，但它不再只是”局部 UI 页面”，而是：

> 一个正在处理 `REVIEW_REQUIRED` job 的人工协同界面。

该设计设想纠偏提交带上 `job_id`，并在最后一笔待审核交易处理完成后将 job 状态从 `REVIEW_REQUIRED` 推进为 `SUCCEEDED`。

## 10.3 Dashboard
提议展示最近一次导入任务卡片，包含：
- 导入文件名
- 当前状态（带视觉色调：success / warning / danger / neutral）
- 来源、总笔数、已入库数、待审核数
- 更新时间
- 若状态为 `REVIEW_REQUIRED`，显示”去处理待审核交易”入口

该设计设想 Dashboard 初始化时调用 `GET /api/import-jobs/latest` 加载最近任务状态。

---

## 11. 第一版提议边界（非常重要）

这次只做最小闭环，不做以下内容：

- 不把所有 Agent 查询接口都状态机化
- 不给每笔交易引入复杂多状态生命周期
- 不做异步队列 / 后台 worker
- 不做通用 workflow engine
- 不做跨 job 的全局调度

第一版的核心只是：

> 给 `POST /api/parse` 产生的一次导入任务，建立可查询、可测试、可追踪的显式状态。

---

## 12. 历史实施清单（提议，不是当前状态）

### Step 1
提议 `import_jobs` 和 `import_job_runs` 两张 PostgreSQL 表（`backend/database.py`）。

### Step 2
提议 `/api/parse` 接入完整状态流转：
- create job as `PENDING`
- switch to `RUNNING`
- finalize to `SUCCEEDED / REVIEW_REQUIRED / FAILED`

### Step 3
提议扩展 `ParseResponse`：
- `job_id`
- `run_id`
- `job_status`
- `review_required_count`
- `persisted_count`

### Step 4
提议由基础测试覆盖（`backend/tests/test_api.py`）：
- 无待审核 -> `SUCCEEDED`
- 有待审核 -> `REVIEW_REQUIRED`
- 解析异常 -> `FAILED`
- import job 查询接口（latest / detail）

### Step 5
提议 `/api/transactions/correct` 支持 `job_id` 参数，纠偏后自动检查并推进 job 状态（`REVIEW_REQUIRED -> SUCCEEDED`）。

---

## 13. 这个设计回答了什么问题

若落地，系统将能够明确回答：

- 这次上传任务有没有真正开始？
- 现在是在跑、跑完、失败，还是卡在人审？
- 为什么上传成功了却还没彻底完成？
- 一次导入里到底有多少交易需要人工接住？
- 哪一步最容易失败？

这正是 Month 2 想补的“企业后端工程味道”。

---

## 14. 一句话结论

该历史设计认为，下一步合适的具体状态流转不是先抽象整个系统，而是先把：

```text
POST /api/parse 对应的一次账单导入任务
```

定义成：

```text
PENDING -> RUNNING -> SUCCEEDED
PENDING -> RUNNING -> REVIEW_REQUIRED -> SUCCEEDED
PENDING -> RUNNING -> FAILED
```

再围绕它补最小持久化、最小执行记录和最小测试。