---
name: financial-analyst
description: 个人财务账单分析与健康诊断工具。支持解析支付宝和微信账单CSV文件，进行智能支出分类，生成财务健康诊断报告。Use when: (1) 用户请求分析账单文件（提及"支付宝账单"、"微信账单"、"CSV文件"、"支出分析"），(2) 用户需要财务健康诊断或建议（提及"财务健康"、"财务诊断"、"消费建议"），(3) 用户需要支出分类或消费趋势分析。
---

# Financial Analyst

## Overview

为个人用户提供智能财务分析服务，包括账单解析和 AI 财务健康诊断。

**核心定位：** Skill 作为 FastAPI 后端的「入口封装」，不维护独立的解析逻辑，解析能力统一由后端提供。

## Architecture

```
用户请求 → Skill (call_api.py) → FastAPI 后端 (/api/parse + /api/analyze) → AI 诊断报告
```

- **Skill 层**：封装 API 调用，处理参数和输出格式化
- **Backend 层**：负责 CSV 解析、分类规则、AI 诊断（Pydantic 强类型校验）

## 前置条件

**⚠️ 使用本 Skill 前，需要确保 FastAPI 后端服务已启动：**

```bash
cd <repository-root>/backend
python3 api_server.py
```

默认运行在 `http://localhost:8000`。可通过环境变量 `FINANCIAL_API_URL` 自定义地址。

## Quick Start

### 一键分析（推荐）

```bash
python3 scripts/call_api.py <账单CSV文件路径>
```

**示例：**
```bash
# 分析支付宝账单
python3 scripts/call_api.py ~/账单/支付宝交易明细_2026.csv

# 分析微信账单
python3 scripts/call_api.py ~/账单/微信支付账单_2026.csv
```

**执行流程：**
1. 上传 CSV 到后端 `/api/parse` → 解析交易
2. 汇总数据发送到 `/api/analyze` → AI 诊断报告

### 支持的文件类型

- **支付宝账单**: GBK 编码的 CSV 文件
- **微信账单**: UTF-8 编码的 CSV 文件

后端会自动检测编码和文件格式。

## Scripts

| 脚本 | 作用 |
|------|------|
| **call_api.py** | 主脚本，封装「解析 + 诊断」完整流程 |
| **health_diagnosis.py** | 直接调用 `/api/analyze`，需要预先解析好的 JSON 数据 |

## API Endpoints

后端接口详情见：`../api_server.py`

| Endpoint | Method | 作用 |
|----------|--------|------|
| `/api/parse` | POST | 上传 CSV，返回解析后的交易列表 |
| `/api/analyze` | POST | 发送汇总数据，返回 AI 诊断报告 |
| `/api/categorize` | POST | 批量 AI 分类（解决未知商户的分类问题） |

## References

- **categories.md**: 消费分类规则说明，供人类参考

