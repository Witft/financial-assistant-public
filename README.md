# Financial Assistant｜支持 API / MCP 接入的个人财务管理系统

这是从已提交版本整理出的**公开源码候选快照**，不携带原 Git 历史。包含 FastAPI 后端、Vue/Vite 前端、业务测试及部分说明文档；不包含 Durable Agent Runtime、原始线上 Trace 或个人部署配置。

分类评估使用新的、确定性的 23 条公开合成用例，见 `evals/bill-classification-v1/SYNTHETIC_CORPUS.md`。本地验证不构成发布授权或生产部署承诺；测试、Eval 与浏览器验收只证明各自明确说明的范围。

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
python scripts/init_database.py
uvicorn api_server:app --host 127.0.0.1 --port 8000
```

应用不会替你建库、建角色或安装 PostgreSQL。`python scripts/init_database.py` 是唯一会创建缺失应用表的入口：它会先校验已存在对象是否完全符合当前契约，再创建缺失表。应用启动只读校验已配置的 schema；缺表或不兼容的表会导致启动失败，不会在启动、解析或查询时自动建表、修改表或迁移 schema。请在开始前确认 DSN 指向可清空的测试数据库。初始化账号需要创建应用表所需的权限；日常运行可另用仅有所需读写权限的账号。不兼容的旧 schema 会被拒绝，必须另行评估迁移方案，不能把重复执行初始化当作自动迁移。

持久化模式下，重复上传通过由来源、日期、描述、金额和类型计算出的稳定哈希交易 ID 做 upsert。数据库已启用时，`POST /api/parse` 会在写入前把每笔返回交易的 `id` 设为该稳定持久化 ID；该 ID 与 `import_job_id`（也等于响应顶层的 `job_id`）可直接用于 `POST /api/transactions/correct`。无数据库模式的 `tx_0` 一类解析序号不代表持久化行，不能用于持久化纠正。

导入任务处于 `REVIEW_REQUIRED` 时，`review_required_count` 记录的是导入完成时的初始待审核数量；单笔纠正不会逐笔递减。全部待审核交易清除后，任务转为 `SUCCEEDED`，该字段才重置为 0。

当前浏览器验收记录了两次连续、隔离的真实 PostgreSQL/浏览器运行均通过（每次均为 1 个 Playwright 测试）。两次运行都上传公开 `ccb_sample.xls` 的 12 笔交易，使用 parse 响应中的持久化 ID 完成纠正，随后 reload、启动新的后端进程并直接查询 PostgreSQL 以确认数据仍存在；该测试没有拦截或 mock API，且保留 HTTP 错误与控制台错误断言；持久化证据另由真实 PostgreSQL 查询核对。这是该工作树快照的浏览器证据，不是永久环境修复、生产适用性或发布授权。

## 测试、Eval 与合成语料生成

从仓库根目录运行。以下命令会生成本地诊断报告到 `evals/bill-classification-v1/reports/`；它们不是历史 Trace，不应提交。评估只使用公开的确定性合成语料。

```bash
. backend/.venv/bin/activate
unset DATABASE_URL SCHEMA_POSTGRES_TEST_DSN DEEPSEEK_API_KEY DEEPSEEK_BASE_URL DEEPSEEK_MODEL
python evals/bill-classification-v1/generate_synthetic_cases.py
python backend/scripts/run_bill_classification_eval.py
python -m pytest backend
python -m unittest discover -s scripts/tests -p test_release_package.py

cd frontend
npm test
npm run build
cd ..
```

本次候选版在凭据清空、外网阻断及全新专用 PostgreSQL 环境下复验：后端 205 passed，打包测试 7 passed；合并运行输出为 `212 passed, 1 warning, 4 subtests passed`（subtests 不额外算作主测试）。公开合成分类 Eval 为 23/23 通过；前端 Vitest 为 22/22 通过，构建通过。后端有一个既有弃用警告，构建有大 chunk 提示；这些结果不证明在线模型或生产部署。较早的 167 passed 仅属于历史验证，不能与本轮总计合并。

普通测试命令不启用真实 PostgreSQL schema 测试。`SCHEMA_POSTGRES_TEST_DSN` 是该集成测试的单独开关：测试会反复执行 `DROP SCHEMA public CASCADE` 并创建测试角色，**只能指向全新、可丢弃的隔离测试实例**，绝不能复用应用数据库、共享库或生产库。未设置该变量时，这组测试会跳过；这不等于通过完整 PostgreSQL 验收。

## 运行时归档包（与源码 checkout 分开）

运行时归档包是单独的、较窄的部署载荷：其中包含已构建的前端静态文件、后端运行依赖声明、`schema.py` 和初始化脚本；不包含前端源码或 npm 项目，也不包含 `evals/` 的语料与生成器。因此不要在归档包内执行前端 `npm` 命令或 Eval 命令；这些命令只适用于源码 checkout。

解压归档包后，在其根目录创建 Python 环境并安装归档中提供的后端依赖：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt
unset DATABASE_URL DEEPSEEK_API_KEY DEEPSEEK_BASE_URL DEEPSEEK_MODEL
bash start.sh
```

归档包的 `start.sh` 以 loopback 地址启动 `python -m uvicorn api_server:app --host 127.0.0.1 --port 8000`，并服务已构建的前端。若要使用持久化，只能先为可丢弃的本地专用 PostgreSQL 设置 `DATABASE_URL`，然后在同一已激活环境中运行 `python backend/scripts/init_database.py`，最后执行 `bash start.sh`。该显式初始化和 fail-closed schema 契约与源码模式相同。

## AI 协作边界

该候选版记录的工作范围包括业务问题定义、关键设计、安全边界、测试/Eval 验收、核心代码阅读、审查与迭代决策；实现采用 AI 协作。生成的代码产物不自动等同于独立掌握的全部能力。

[PUBLIC_EXPORT_MANIFEST.md](PUBLIC_EXPORT_MANIFEST.md) 仅列出公开评估资产及其验证范围，并非完整公开载荷清单；排除项与验证限制见 [PUBLIC_EXPORT_OMISSIONS.md](PUBLIC_EXPORT_OMISSIONS.md)。
