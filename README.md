# Financial Assistant｜支持 API / MCP 接入的个人财务管理系统

这是从已提交版本整理出的**公开源码快照**，不携带原 Git 历史。包含 FastAPI 后端、Vue/Vite 前端、业务测试及部分说明文档；不包含 Durable Agent Runtime、原始线上 Trace 或个人部署配置。

**公开源码快照：** 本仓库已完成公开载荷审阅并获准发布，不包含原私有 Git 历史或私有原始 gold 语料。分类评估使用新的、确定性的 23 条公开合成用例，见 `evals/bill-classification-v1/SYNTHETIC_CORPUS.md`。源码公开不等于生产部署就绪；测试与 Eval 仅证明其各自声明的验证范围。

## 项目范围

- 解析账单、分类交易；配置 PostgreSQL 后提供持久化查询。
- Web 界面用于上传、查看统计和人工审核。
- API/MCP 提供结构化财务查询；查询接口与使用在线模型进行分类/分析是不同功能。
- 在线模型相关功能需要用户自行配置凭据，使用时可能向模型服务发送数据；本候选版不提供生产隐私合规或安全上线承诺。

## 前置条件与干净安装

以下命令从一个**干净 clone 的仓库根目录**开始执行；不要在 `backend/` 或 `frontend/` 外猜测相对路径。请只上传公开合成账单，不要使用真实账单、生产数据库或真实凭据。

- Python：依赖声明在 `backend/requirements.txt`；最近的隔离验证使用 Python 3.11。建议使用 Python 3.11 或兼容版本，并建立项目内虚拟环境。
- Node.js：`frontend/package.json` 要求 `^20.19.0 || >=22.12.0`；需要随 Node 安装的 npm。
- PostgreSQL：仅在需要持久化查询时才需要。应用不会创建数据库或用户；请先自行创建一个专用于本项目测试的本地数据库和最小权限账号。

```bash
git clone https://github.com/Witft/financial-assistant-public.git financial-assistant
cd financial-assistant

# 后端：仍位于仓库根目录时创建环境
python3 -m venv backend/.venv
. backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt

# 前端：切换到前端目录再安装
cd frontend
npm ci
cd ..
```

配置文件只保留空凭据或示例设置。真实 `.env`、账单、数据库文件和生成产物应留在 Git 之外。

## 无数据库、无模型的本地解析模式

此模式不设置 `DATABASE_URL`，也不设置 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL` 或 `DEEPSEEK_MODEL`。`POST /api/parse` 仍会用本地规则解析 CSV/XLS/XLSX；它不会写入数据库，也不会调用在线模型。AI 分类和 AI 财务诊断接口在未配置 API Key 时不可用。

终端 1（从仓库根目录）：

```bash
. backend/.venv/bin/activate
cd backend
unset DATABASE_URL DEEPSEEK_API_KEY DEEPSEEK_BASE_URL DEEPSEEK_MODEL
uvicorn api_server:app --host 127.0.0.1 --port 8000
```

终端 2（另开终端，从仓库根目录）：

```bash
cd frontend
VITE_API_BASE_URL=http://127.0.0.1:8000/api npm run dev -- --host 127.0.0.1
```

打开 Vite 输出的 loopback 地址并上传公开合成工作簿 `backend/tests/fixtures/ccb_sample.xls`。记录的无数据库验收中，该文件解析出 12 笔交易，响应会说明“未配置 DATABASE_URL，当前未写入数据库”。浏览器可在内存/本地缓存路径中进入审核和仪表盘；但 `/api/agent/months`、`/api/agent/transactions`、`/api/agent/monthly-summary` 和 `/api/import-jobs/*` 是持久化查询，在无 `DATABASE_URL` 时返回 503。

`VITE_API_BASE_URL` 是前端实际读取的环境变量；未设置时前端默认请求相对路径 `/api`。上面的显式值适用于前后端分别在 loopback 端口运行的开发模式。

## 可选：专用本地 PostgreSQL 持久化测试

仅对你创建的**可丢弃、本地、专用测试库**设置 `DATABASE_URL`，绝不要指向生产库、共享库或含真实账单的库。示例刻意没有有效密码：

```bash
# 先由数据库管理员/本机用户创建专用数据库与最小权限账号。
# 不要把真实 DSN 或密码写入仓库、README 或提交记录。
export DATABASE_URL='postgresql://financial_test_user:CHANGE_ME@127.0.0.1:5432/financial_assistant_test'

. backend/.venv/bin/activate
cd backend
uvicorn api_server:app --host 127.0.0.1 --port 8000
```

应用不会替你建库、建角色或安装 PostgreSQL。连接到已存在的测试库后，首次相关操作以 `CREATE TABLE IF NOT EXISTS` 懒创建 `transactions`、`import_jobs` 与 `import_job_runs`；上传解析会写入交易和导入任务。请在开始前确认 DSN 指向可清空的测试数据库。

持久化模式下，重复上传通过由来源、日期、描述、金额和类型计算出的稳定哈希交易 ID 做 upsert。`POST /api/parse` 的返回交易 ID 是本次解析序号（如 `tx_0`），不是持久化行 ID；若要调用 `POST /api/transactions/correct` 同步修改数据库中的交易，先从 `GET /api/agent/transactions?month=YYYY-MM` 取得该行的稳定 `id`，并同时传入对应 `job_id`。直接使用 parse 响应的 `tx_0` 一类 ID 在已启用数据库时不能定位持久化行。

导入任务处于 `REVIEW_REQUIRED` 时，`review_required_count` 记录的是导入完成时的初始待审核数量；单笔纠正不会逐笔递减。全部待审核交易清除后，任务转为 `SUCCEEDED`，该字段才重置为 0。

已记录的持久化证据仅覆盖真实 FastAPI `TestClient`：公开 `ccb_sample.xls` 写入 PostgreSQL、查询接口返回持久化数据、用查询到的稳定 ID 完成一次纠正，并在新的 Python 进程/新 `TestClient` 中重启后仍能读到该数据。它不等同于“前端已在 PostgreSQL 模式完成端到端浏览器验收”；该浏览器验收尚未声明通过。

## 测试、Eval 与合成语料生成

从仓库根目录运行。以下命令会生成本地诊断报告到 `evals/bill-classification-v1/reports/`；它们不是历史 Trace，不应提交。评估只使用公开的确定性合成语料。

```bash
. backend/.venv/bin/activate
python evals/bill-classification-v1/generate_synthetic_cases.py
python backend/scripts/run_bill_classification_eval.py
python -m pytest backend

cd frontend
npm test
npm run build
cd ..
```

最近记录的隔离验证结果为：分类 Eval 23/23 通过；后端 `pytest` 为 167 passed、1 warning；前端 Vitest 为 22/22 通过，生产构建通过。该记录不证明在线模型、生产部署或真实数据库浏览器流程。

## AI 协作边界

该候选版记录的工作范围包括业务问题定义、关键设计、安全边界、测试/Eval 验收、核心代码阅读、审查与迭代决策；实现采用 AI 协作。生成的代码产物不自动等同于独立掌握的全部能力。

完整导出清单见 [PUBLIC_EXPORT_MANIFEST.md](PUBLIC_EXPORT_MANIFEST.md)，排除项与验证限制见 [PUBLIC_EXPORT_OMISSIONS.md](PUBLIC_EXPORT_OMISSIONS.md)。
