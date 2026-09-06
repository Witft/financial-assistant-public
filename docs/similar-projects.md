# 类似项目调研：支付宝 / 微信账单分析

整理时间：2026-04-29

用途：记录网络上与个人财务助手项目功能相近的产品/开源项目，后续可作为竞品分析、功能设计和解析兼容性的参考。

## 1. Bill Insight / payment_record_analysis

- GitHub: https://github.com/Hessel2333/payment_record_analysis
- Demo: https://hessel.pythonanywhere.com/
- 类型：账单分析 Web 应用
- 技术栈：Flask + 前端模板/静态资源
- 支持：支付宝 CSV、微信 XLSX/CSV
- 主要功能：
  - 年度分析
  - 月度分析
  - 分类分析
  - 时间分析
  - 消费洞察
  - 交易记录
  - 可视化图表
- 参考价值：
  - 和本项目相似度较高，适合参考 Web 分析页面、交互设计、图表维度和用户体验。
  - 偏传统 Web 分析工具，本项目可在 Agent-first、结构化 AI 诊断、人类审核闭环上做差异化。

## 2. alipay-wechat-merge

- GitHub: https://github.com/yann0917/alipay-wechat-merge
- 类型：账单合并 + 简单图表分析工具
- 技术栈：Go + ECharts
- 支持：支付宝、微信 CSV 账单
- 主要功能：
  - 合并支付宝和微信账单
  - 输出标准 CSV
  - 生成简单图表 HTML
- 已知格式处理：
  - 支付宝：16 项数据列，前 4 行说明，GBK 编码
  - 微信：11 项数据列，前 16 行说明，UTF-8 编码
  - 会过滤部分“中性交易”，如充值、提现、理财通购买、零钱通存取、信用卡还款等
- 参考价值：
  - 账单格式兼容逻辑
  - 支付宝/微信统一字段映射
  - 中性交易识别与过滤策略

## 3. aliwepaystat

- GitHub: https://github.com/vogo/aliwepaystat
- 类型：支付宝/微信账单统计工具
- 技术栈：Go + SQLite + Web UI
- 支持：支付宝、微信 CSV 账单
- 主要功能：
  - 将 CSV 账单导入 SQLite
  - 基于 SQLite 查询和统计
  - CLI 命令
  - Web 界面
  - 上传 CSV
  - 查看统计图表
  - 管理交易
  - 配置分类关键词
  - 支持 JSON 输出
- 参考价值：
  - “CSV 导入 → SQLite 持久化 → 查询统计 → Web 展示”的架构
  - CLI + Web 双入口
  - 分类关键词配置
  - 后续如果本项目要做长期数据沉淀，可以参考其数据库化路线。

## 4. bill-parser

- GitHub: https://github.com/lyenrowe/bill-parser
- 类型：支付平台账单解析库
- 技术栈：PHP / Composer
- 支持：支付宝、微信、银联等支付账单文件
- 主要功能：
  - 根据文件头自动判断账单类型
  - 使用对应解析类解析账单
  - 返回结构化 rows，便于写入数据库
- 参考价值：
  - Parser 抽象设计
  - 多支付平台解析适配
  - 可参考类似接口：`BillParser -> AlipayBillParser / WeChatBillParser / BankBillParser`

## 5. beancount_importer

- GitHub: https://github.com/chryoung/beancount_importer
- 类型：支付宝/微信账单导入 Beancount 的 GUI 工具
- 技术栈：Python GUI
- 支持：支付宝、微信账单
- 主要功能：
  - 导入支付宝/微信账单
  - 根据用户账户体系生成 Beancount 记账文件
- 参考价值：
  - 面向专业记账用户的复式记账路线
  - 如果本项目未来支持导出 Beancount / 标准记账格式，可以参考。

## 6. Beancount-Trans / 类似 Beancount 转换工具

- 来源：搜索到的文章提及，具体项目需后续再核实
- 类型：多平台账单转 Beancount 标准格式
- 支持：支付宝、微信支付、银行账单等 CSV/PDF/Excel
- 参考价值：
  - “多来源账单 → 标准化财务格式”的路线
  - 适合重度记账用户，但对普通用户门槛较高。

## 7. 商业产品 / 记账 App / 企业财务工具

代表方向：

- 个人记账 App：随手记、挖财、钱迹、有鱼记账、鲨鱼记账等
- 企业财务工具：金蝶 AI 星辰、精斗云等

常见能力：

- 账单同步或批量导入
- 消费分类
- 预算管理
- 资产负债
- 企业收款、发票、税务、进销存、经营报表

局限：

- 很多不支持自由导入官方账单
- 数据隐私不可控
- 个性化分析能力有限
- AI 诊断偏浅
- 难以和个人 Agent 工作流结合

## 对本项目的差异化启发

本项目不应只重复“账单图表工具”，更适合强化以下方向：

1. Agent-first
   - 用户通过 Agent 上传/发送账单。
   - Agent 自动解析、分类、诊断、追问和生成建议。

2. 结构化 AI 分类 + 人类审核闭环
   - 分类结果包含 `category`、`confidence`、`reason`、`requires_human_review`。
   - 低置信度交易进入待审核区，用户确认后沉淀规则。

3. 长期财务健康诊断
   - 不止展示“花了多少钱”，还要诊断现金流缺口、家庭支持压力、预算执行、异常大额支出、下月风险等。

4. 隐私优先、本地运行
   - 原始账单尽量本地处理。
   - 支持脱敏、可控上传、可选私有模型/本地模型。

5. 数据沉淀和可查询
   - 可以参考 SQLite / PostgreSQL 持久化路线。
   - 为后续 Agent 查询“过去 3 个月餐饮趋势”“本月异常支出”等能力打基础。

## 建议优先参考顺序

1. Bill Insight / payment_record_analysis：参考 Web 产品形态和分析维度。
2. aliwepaystat：参考 SQLite 持久化、CLI/Web 双入口和统计结构。
3. alipay-wechat-merge：参考账单格式兼容、合并账单和中性交易处理。
4. bill-parser：参考 parser 抽象。
5. beancount_importer：参考专业记账/Beancount 路线。
