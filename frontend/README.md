# Frontend

财务助手前端，基于 **Vue 3 + Vite + Pinia + Vue Router + ECharts**。

职责很明确：

- 上传账单文件并调用后端解析
- 展示收支概览、分类统计和图表
- 提供待审核分类列表
- 在人工修正分类后，把纠偏偏好同步回后端

## 页面结构

当前有 3 个核心页面：

- `/`：上传页 `src/views/UploadPage.vue`
- `/dashboard`：Dashboard `src/views/DashboardPage.vue`
- `/review`：人工审核页 `src/views/ReviewPage.vue`

路由定义见 `src/router/index.js`。

## 目录结构

```text
frontend/
├── src/
│   ├── components/       # 图表、摘要卡片、交易列表等 UI 组件
│   ├── router/           # Vue Router 路由定义
│   ├── stores/           # Pinia 状态管理（核心：finance.ts）
│   ├── types/            # 前端类型定义
│   ├── utils/            # API、分类映射、本地存储工具
│   └── views/            # Upload / Dashboard / Review 页面
├── tests/                # Vitest 用例
├── requirements/         # 前端需求文档
├── package.json
└── vite.config.js
```

## 本地开发

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

默认使用 Vite 开发服务器。

如果前后端分开启动，建议在 `frontend/.env.local` 中指定后端地址：

```env
VITE_API_BASE_URL=http://localhost:8000/api
```

如果不配置，前端默认请求相对路径 `/api`。

## 可用脚本

```bash
npm run dev       # 启动开发服务器
npm run build     # 生产构建
npm run preview   # 预览构建结果
npm run test      # 运行 vitest
npm run lint      # 运行 oxlint + eslint（会自动 fix）
npm run format    # 格式化 src/
```

## 与后端的接口关系

前端当前主要依赖这些接口：

- `POST /api/parse`：上传并解析账单
- `POST /api/analyze`：获取 AI 财务诊断
- `POST /api/transactions/correct`：保存人工纠偏规则

实现入口：

- `src/utils/api.ts`
- `src/stores/finance.ts`

## 数据流说明

### 1. 上传解析

`UploadPage` 调用 `fetchParsedTransactions()` 上传文件到 `/api/parse`，后端返回解析后的交易数据和状态消息。

### 2. 本地展示

交易数据进入 `finance` store，并落到本地存储；Dashboard 和 Review 页面都从同一个 store 读取。

### 3. 待审核逻辑

以下交易会进入待审核列表：

- `requires_human_review === true`
- 分类为 `other` 或 `其他`

相关逻辑在 `src/stores/finance.ts` 的 `pendingReviews` 计算属性。

### 4. 人工纠偏

审核页修改分类后，前端会调用 `/api/transactions/correct`，让后端记住用户规则，后续解析可直接复用。

## 测试

当前已有一些轻量回归测试，主要覆盖：

- API 返回数据到前端数据结构的映射
- 分类标签归一化
- 金额方向/展示逻辑
- `pendingReviews` 和统计 store 逻辑

运行：

```bash
npm run test
```

测试目录：`tests/`

## 架构文档

建议先读：

- `../docs/architecture-overview.md`：项目整体架构总览
- `../docs/agent-first-architecture.md`：Agent-first 演进背景与详细设计

## 注意事项

- `dist/` 是构建产物，不应手工修改。
- 前端使用中英分类混合输入时，会通过 `normalizeCategoryLabel()` 统一成 UI 使用的展示标签。
- 若后端接口结构变更，优先补 `tests/` 里的回归用例，避免再次出现映射错位问题。
