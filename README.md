# Financial Assistant｜支持 API / MCP 接入的个人财务管理系统

这是从已提交版本整理出的**公开源码快照**，不携带原 Git 历史。包含 FastAPI 后端、Vue/Vite 前端、业务测试及部分说明文档；不包含 Durable Agent Runtime、原始线上 Trace 或个人部署配置。

**公开源码快照：** 本仓库已完成公开载荷审阅并获准发布，不包含原私有 Git 历史或私有原始 gold 语料。分类评估使用新的、确定性的 23 条公开合成用例，见 `evals/bill-classification-v1/SYNTHETIC_CORPUS.md`。源码公开不等于生产部署就绪；测试与 Eval 仅证明其各自声明的验证范围。

## 项目范围

- 解析账单、分类交易；配置数据库后提供持久化查询。
- Web 界面用于上传、查看统计和人工审核。
- API/MCP 提供结构化财务查询；查询接口与使用在线模型进行分类/分析是不同功能。
- 在线模型相关功能需要用户自行配置凭据，使用时可能向模型服务发送数据；本候选版不提供生产隐私合规或安全上线承诺。

## 开发入口

依赖定义分别位于 `backend/requirements.txt` 与 `frontend/package.json`。请在独立本地环境安装，不要使用生产数据库或真实账单进行验证。

```bash
cd backend
python -m pip install -r requirements.txt
# 从公开合成语料本地生成诊断报告；不下载或导入历史报告
python scripts/run_bill_classification_eval.py
python -m pytest

cd ../frontend
npm ci
npm test
npm run build
```

最新隔离验证在清空凭据并阻断出站 socket 的条件下完成：后端套件为 **167 passed, 1 warning**，评估使用 23 条公开合成用例。此前记录的 **169 passed / 29 cases** 仅是历史结果，不是本次候选版的新验证结果。报告层是评估运行后的诊断性 postprocess，不是实时 Trace，也不证明在线模型泛化、生产就绪、浏览器验收、真实数据库连接或在线模型调用。

配置文件只保留空凭据或示例设置。真实 `.env`、账单、数据库文件和生成产物应留在 Git 之外。

## AI 协作边界

该候选版记录的工作范围包括业务问题定义、关键设计、安全边界、测试/Eval 验收、核心代码阅读、审查与迭代决策；实现采用 AI 协作。生成的代码产物不自动等同于独立掌握的全部能力。

完整导出清单见 [PUBLIC_EXPORT_MANIFEST.md](PUBLIC_EXPORT_MANIFEST.md)，排除项与验证限制见 [PUBLIC_EXPORT_OMISSIONS.md](PUBLIC_EXPORT_OMISSIONS.md)。
