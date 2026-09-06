# Changelog

## [v0.1.0-alpha] - 2026-04-25

### Added (新增功能)
- **账单解析引擎**: 支持支付宝和微信支付导出的 CSV 账单解析。
- **混合分类系统 (v1)**: 
  - 后端基于关键词与交易类型的硬编码预分类。
  - 前端基于本地缓存 `localStorage` 的二次匹配。
  - 集成大模型 (DeepSeek) 针对未知商户进行批量智能推断。
- **前端可视化看板 (Dashboard)**:
  - 月度收支概览（总收入、总支出、结余）。
  - 各类消费占比饼图。
  - 支出排行榜 Top 3 预览。
- **AI 财务诊断报告**: 基于当月数据聚合，由 AI 提供总体评价、风险预警及优化建议。
- **交易审核工作流 (Review 页面)**: 针对 AI 无法完全确定的“其他”分类，提供人工纠错与确认的专属界面。

### Changed (变更)
- 优化了 AI 分类请求机制，对商户名称进行去重，减少不必要的 Token 消耗。
- 前端路由改造，上传解析账单后自动跳转至待审核（Review）页面。

### Technical Details (技术细节)
- **后端**: FastAPI + Python, HTTPX, Pydantic, Uvicorn
- **前端**: Vue 3 + Pinia + Vue Router, Vite
- **AI**: DeepSeek API