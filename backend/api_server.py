import os
import io
import json
import re
import csv
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
import httpx
from openpyxl import load_workbook
try:
    import xlrd
except ModuleNotFoundError:  # pragma: no cover - optional until .xls parsing is used
    xlrd = None
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import database

# 加载 .env 文件中的环境变量
load_dotenv()

# ==========================================
# 1. 跨域配置 (CORS)
# ==========================================
app = FastAPI(title="Financial Assistant AI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 2. AI 模型配置 (DeepSeek)
# ==========================================
# 优先读取系统环境变量或 .env 文件中的 DEEPSEEK_API_KEY
AI_API_KEY = os.getenv("DEEPSEEK_API_KEY")
AI_BASE_URL = os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1"
AI_MODEL = os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"

print(f"🤖 AI 配置: 模型={AI_MODEL}, 端点={AI_BASE_URL}")

# ==========================================
# 3. 支持的分类列表
# ==========================================
CATEGORIES = ["餐饮", "交通", "购物", "娱乐", "通讯", "住房", "医疗", "人情", "转账", "收入", "数码订阅", "日用百货", "其他"]

# ==========================================
# 4. 账单解析：分类规则
# ==========================================
# ==========================================
# 4. 账单解析：分类规则（V2 精细化版）
#
# 关键词匹配规则：substr 包含匹配（已自动 tolower）
# 匹配优先级：按 CLASSIFICATION_RULES 遍历顺序，先命中先返回
# 置信度体系：
#   0.95 — 精准关键词命中（专属词，无歧义）
#   0.85 — 通用关键词命中（通用词，可能轻微歧义）
#   0.60 — 类型 fallback（中置信度，建议审核）
#   0.10 — 兜底 other（低置信度，必须审核）
# ==========================================

CLASSIFICATION_RULES = {
    'family_support': {
        'keywords': [
            # 家庭关系 / 家用支持
            '亲属卡', '妈妈', '爸爸', '妈', '爸', '父母', '家人',
            '爷爷', '奶奶', '外公', '外婆', '姥姥', '姥爷', '亲戚',
            '哥哥', '姐姐', '弟弟', '妹妹', '生活费', '孝敬',
        ],
        'types': ['亲属卡']
    },
    'investment': {
        'keywords': [
            # 理财产品
            '基金', '余额宝', '理财', '零钱通', '投付宝',
            '银行理财产品', '国债', '逆回购', '朝朝盈', '朝朝宝',
            # 借贷
            '借呗', '花呗', '京东金条', '白条', '微粒贷',
        ],
        'types': ['转入零钱通', '投付宝', '理财产品', '基金']
    },
    'dining': {
        'keywords': [
            # 连锁餐饮品牌
            '茶百道', '茶颜悦色', '霸王茶姬', '古茗', '沪上阿姨',
            '肯德基', '麦当劳', '德克士', '华莱士', '汉堡王',
            '星巴克', '瑞幸', '库迪', 'Manner', '皮爷咖啡',
            '海底捞', '喜茶', '奈雪', '蜜雪冰城', '一点点',
            '外婆家', '绿茶', '新白鹿', '外婆', '西贝',
            '麦当劳', '汉堡', '必胜客', '尊宝', '尊宝比萨',
            # 便利店/超市属于日用百货，移至 daily_necessities
            '盒马', '永辉', '大润发', '华润', '物美', '沃尔玛',
            # 外卖平台
            '淘宝闪购', '美团', '饿了么', '大众点评', '外卖',
            # 通用餐饮词
            '餐饮', '美食', '小吃', '快餐', '火锅', '烧烤', '烤肉',
            '饮品', '蛋糕', '面包', '烘焙', '甜品', '奶茶', '果茶',
            '食堂', '饭团', '炒饭', '麻辣烫', '黄焖鸡', '炸鸡',
            '烤鱼', '寿司', '拉面', '米线', '螺蛳粉', '酸辣粉',
            '团购', '套餐', '代金券', '买单', '结账',
        ],
        'types': ['外卖美食', '餐饮', '美食', '超市']
    },
    'transportation': {
        'keywords': [
            # 打车平台
            '滴滴', '高德打车', '高德地图', '曹操出行', '首汽约车', 'T3出行', '嘀嗒',
            '打车', '叫车', '出租车',
            # 公共交通
            '地铁', '地铁票', '地铁充值', '公交', '公交车', '公交集团',
            '杭州通', '深圳通', '上海公交', '北京公交', '羊城通', '苏通卡',
            # 共享出行
            '哈啰', '美团单车', '青桔', '小蓝', '共享单车', '共享电单车',
            # 出行服务
            '出行', '机票', '火车票', '高铁', '动车', '携程', '去哪儿',
            '飞猪', '酒店', '民宿', '门票', '景点', '旅游',
            # 停车/加油
            '停车', '停车场', '停车费', '加油', '中石化', '中石油', '壳牌',
            '高速', '通行费', 'ETC', '过路费',
        ],
        'types': ['交通出行', '出行', '加油', '停车']
    },
    'shopping': {
        'keywords': [
            # 电商平台
            '淘宝', '天猫', '京东', '拼多多', '唯品会', '抖音商城', '小红书商城',
            '购物', '网购', '电商', '快递', '菜鸟', '顺丰', '京东快递', '圆通',
            '中通', '韵达', '申通', '极兔',
            # 服装鞋包
            '衣服', '裤子', '裙子', '外套', '卫衣', '衬衫', 'T恤', '羽绒服',
            '鞋子', '运动鞋', '皮鞋', '帆布鞋', '球鞋',
            '蕉内', 'Ubras', '内外', '耐克', '阿迪达斯', '李宁', '安踏', '特步',
            '优衣库', 'ZARA', 'HM', 'GAP', '无印良品', '热风', '红蜻蜓',
            '鞋包', '箱包', '背包', '双肩包', '钱包', '皮带', '围巾', '帽子',
            # 数码电子产品（通用消费电子产品）
            '手机', '电脑', '平板', '耳机', '音箱', '键盘', '鼠标', '充电器',
            '数据线', '充电宝', 'U盘', '硬盘', '固态硬盘', '内存条',
            '小米', '华为', '三星', 'OPPO', 'VIVO', '一加',
            '荣耀', 'realme', 'iqoo', '红米', 'Redmi',
            # 眼镜（线上购买）
            '眼镜', '墨镜', '隐形眼镜',
            # 家居家纺
            '家具', '床', '床垫', '枕头', '被子', '四件套', '窗帘', '地毯',
            '收纳', '置物架', '衣架', '家居',
            # 美妆护肤
            '化妆品', '护肤品', '彩妆', '口红', '粉底', '眼影', '美妆',
            '水乳', '面霜', '精华', '防晒', '卸妆', '洁面',
            '兰蔻', '雅诗兰黛', 'SKII', '海蓝之谜', '资生堂', '理肤泉',
            '薇诺娜', '珀莱雅', '完美日记', '花西子', '彩棠',
            # 其他购物
            '玩具', '文具', '礼品', '鲜花', '绿植', '宠物', '母婴', '奶粉',
            '纸尿裤', '儿童', '婴儿', '乐器', '图书',
        ],
        'types': ['购物', '网购', '商城']
    },
    'entertainment': {
        'keywords': [
            # 影视
            '电影', '电影院', '影院', '影片', 'IMAX', '杜比全景声',
            # 长视频平台（付费订阅+内容消费）
            'B站充电', '哔哩哔哩充电', 'B站大会员', '哔哩哔哩大会员', 'B站', '哔哩哔哩', '爱奇艺', '优酷', '腾讯视频', '芒果TV',
            # 演出/娱乐场所
            'KTV', '卡拉OK', '剧本杀', '密室逃脱', '密室', '狼人杀',
            '游乐园', '欢乐谷', '迪士尼', '方特', '海洋馆', '动物园',
            '酒吧', '清吧', '夜店', 'LiveHouse', '演唱会', '音乐节',
            # 游戏
            '游戏', '手游', '端游', '网游', '氪金', '点券', '皮肤',
            '原石', '原神', '王者', '王者荣耀', '和平精英', 'LOL',
            'Steam', 'Epic', 'Switch', 'PlayStation', 'Xbox',
            # 棋牌
            '棋牌', '麻将', '棋牌室', '桌游',
            # 短视频/直播（内容消费）
            '抖音', '快手', '微视', '视频号',
            # 票务
            '机票', '火车票', '高铁票'  # 注：已在交通归类，此处为兜底
        ],
        'types': ['娱乐', '文化娱乐', '游戏', '旅游']
    },
    'digital_subscription': {
        'keywords': [
            # 云计算/服务器
            '服务器', 'ecs', '云服务器', 'VPS', 'Bandwagon', '搬瓦工',
            '阿里云', '腾讯云', '华为云', 'AWS', 'Azure', '金山云', 'UCloud',
            '域名', '域名续费', 'SSL证书', '证书续费',
            # 开发者服务
            'GitHub', 'Copilot', 'JetBrains', 'Pycharm', 'WebStorm', 'DataGrip',
            'CodePlanPlus', 'CodePlan', 'Notion', 'Obsidian', '印象笔记',
            '有道云', '为知笔记', 'OneNote',
            # 媒体订阅
            'Apple', 'apple.com', 'App Store', 'iCloud', 'AppleMusic', 'Apple TV+',
            'Netflix', 'Disney+', 'HBO', 'YouTube', 'YouTube Premium',
            'Spotify', 'QQ音乐', '网易云音乐', '酷狗', '酷我',
            # 视频/直播平台会员（B站/哔哩哔哩属于entertainment，避免重复）
            '大会员', 'B币', '直播', '斗鱼', '虎牙', 'YY',
            # 游戏订阅
            'Xbox', 'PlayStation', 'Nintendo', 'Switch', 'Steam', 'Epic',
            # 工具订阅
            'ChatGPT', 'Claude', 'Midjourney', 'OpenAI', 'AI', '大模型',
            'VPN', '翻墙', '机场', '订阅', '包月', '包年', '续费', '充值',
            '会员', 'VIP', '高级会员', '黄金会员', '钻石会员',
        ],
        'types': ['会员', '订阅', '充值', '增值服务']
    },
    'daily_necessities': {
        'keywords': [
            # 超市/便利店
            '超市', '便利店', '全家', '711', '罗森', '便利蜂',
            # 纸品/清洁用品
            '纸巾', '湿巾', '洗脸巾', '卫生纸', '卷纸', '抽纸', '厨房纸',
            '维达', '得宝', 'Tempo', '洁柔', '清风', '心相印', '斑布',
            '威露士', '滴露', '奥妙', '立白', '雕牌', '白猫', '超能',
            # 日化用品
            '洗衣液', '洗衣粉', '洗衣皂', '洗洁精', '洗手液', '沐浴露',
            '洗发水', '护发素', '发膜', '牙膏', '牙刷', '漱口水', '牙线',
            '洗面奶', '香皂', '精油皂', '硫磺皂',
            # 家庭清洁工具
            '清洁剂', '消毒水', '消毒酒精', '84消毒液', '洁厕剂', '去污粉',
            '抹布', '拖把', '扫帚', '簸箕', '垃圾桶', '垃圾袋',
            '扫地机器人', '吸尘器', '空气净化器', '加湿器', '除湿机',
            '云鲸', '科沃斯', '石头', '追觅', '小米扫地',
            # 厨房用品
            '保鲜膜', '保鲜袋', '锡纸', '油纸', '吸油纸',
            '砧板', '刀具', '炒锅', '蒸锅', '电饭煲', '空气炸锅',
            '微波炉', '破壁机', '榨汁机', '料理机', '绞肉机',
            # 一次性用品
            '一次性手套', '一次性口罩', '一次性鞋套',
            # 收纳整理
            '收纳盒', '收纳箱', '收纳袋', '压缩袋', '衣柜收纳',
            # 生活用纸品牌
            '艾禾美', '舒洁', '妮飘', '得仕',
        ],
        'types': ['日用品', '生活用品', '清洁用品', '纸品']
    },
    'fitness_health': {
        'keywords': [
            # 健身运动
            '健身房', '健身', '健身卡', '私教', '团课',
            'Keep', '超级猩猩', '乐刻', '威尔仕', '一兆韦德', '舒适堡',
            '瑜伽', '普拉提', '舞蹈', '游泳', '游泳馆', '游泳池',
            '篮球', '足球', '网球', '羽毛球', '乒乓球', '台球',
            '跑步', '马拉松', '骑行', '爬山', '攀岩',
            '运动', '体育', '体育用品', '体育器材',
            # 保健品
            '维生素', '钙片', '鱼油', '蛋白粉', '褪黑素', '氨糖', '胶原',
            'Swisse', '汤臣倍健', '善存', '安利', '同仁堂',
        ],
        'types': ['运动健身', '健身', '体育']
    },
    'housing': {
        'keywords': [
            # 房租/物业
            '房租', '租金', '物业', '物业费', '物业管理', '水电', '水电费', '燃气费',
            '燃气', '天然气', '煤气', '自来水', '电费', '阶梯电价',
            # 住房服务
            '宽带', '光纤', 'WiFi', '中国移动宽带', '中国电信宽带', '联通宽带',
            '有线电视', '电视费', '有线费',
            # 住房维修
            '维修', '安装', '搬家', '开锁', '疏通', '保洁', '家政',
            '自如', '蛋壳', '贝壳', '中介费', '中介服务',
        ],
        'types': ['住房', '房租', '物业', '水电', '宽带']
    },
    'personal_care': {
        'keywords': [
            # 美容美发
            '理发', '美发', '造型', '染发', '烫发', '剪发',
            '美容', 'SPA', '按摩', '推拿', '足疗', '采耳',
            '美甲', '美睫', '纹眉', '半永久', '皮肤管理', '医美',
            '脱毛', '祛痘', '整形', '牙科', '口腔',
            # 洗浴
            '洗浴', '汗蒸', '温泉', '搓澡', '泡澡',
            # 化妆品/护肤品（线下购买）
            '丝芙兰', '屈臣氏', '万宁', '娇兰佳人',
        ],
        'types': ['美容', '美发', '美甲', '洗浴', '按摩']
    },
    'education': {
        'keywords': [
            # 学习教育
            '书籍', '图书', '电子书', 'Kindle', '多看',
            '课程', '培训', '学费', '教材', '辅导班', '补习班',
            '在线教育', '学而思', '猿辅导', '作业帮', '高途', '有道精品课',
            '网易云课堂', '腾讯课堂', 'B站课堂', 'Coursera', 'edX',
            # 知识付费
            '得到', '知乎', '喜马拉雅', '混沌', '樊登读书',
            '在行', '分答', '小鹅通', '知识星球',
            # 考试
            '考试', '报名费', '雅思', '托福', 'GRE', 'GMAT', '考研',
            '驾照', '学车', '驾校', '科目', '驾照考试',
        ],
        'types': ['教育', '学习', '培训', '书籍']
    },
    'healthcare': {
        'keywords': [
            # 医疗机构
            '医院', '诊所', '药店', '药房', '门诊', '急诊', '住院',
            '体检', '体检中心', '美年大健康', '慈铭', '爱康',
            '中医', '中药', '同仁堂', '方回春堂', '胡庆余堂',
            # 医药
            '买药', '医药', '处方药', '非处方药', '布洛芬', '感冒药',
            '医保', '社保', '医疗险', '保险', '报销',
            # 医疗器材
            '口罩', '酒精', '碘伏', '绷带', '创可贴', '体温计', '血压计',
            '隐形眼镜', '护理液', '眼药水',
        ],
        'types': ['医疗', '医院', '药店', '健康']
    },
}

# ==========================================
# 4. 数据模型定义
# ==========================================

class TransactionSummary(BaseModel):
    income: str = Field(..., description="当月总收入金额，保留两位小数", examples=["12500.00"]) 
    expense: str = Field(..., description="当月总支出金额，保留两位小数", examples=["8450.50"])
    balance: str = Field(..., description="当月结余金额，可为负数", examples=["4049.50"])

class TopCategoryItem(BaseModel):
    name: str = Field(..., description="消费分类名称", examples=["餐饮"])
    amount: str = Field(..., description="该分类总支出金额", examples=["2500.00"])
    pct: str = Field(..., description="该分类占总支出的百分比", examples=["29%"])

class TopExpenseItem(BaseModel):
    date: str = Field(..., description="交易发生日期", examples=["2026-04-10 12:30:00"])
    category: str = Field(..., description="交易所属分类", examples=["购物"])
    amount: str = Field(..., description="单笔支出金额（绝对值）", examples=["599.00"])
    desc: str = Field(..., description="商户名称或交易描述", examples=["Apple Store"])

class FinancialData(BaseModel):
    month: str = Field(..., description="财务月份标识", examples=["2026-04", "全部历史"])
    summary: TransactionSummary = Field(..., description="当月收支汇总")
    top_categories: List[TopCategoryItem] = Field(..., description="按金额排序的前几大支出分类")
    top_expenses: List[TopExpenseItem] = Field(..., description="按金额排序的前几笔最大单笔支出")

class AnalyzeRequest(BaseModel):
    financial_data: FinancialData = Field(..., description="前端聚合清洗后的财务诊断核心数据")

class CategorizeRequest(BaseModel):
    descriptions: List[str] = Field(..., description="需要 AI 进行批量分类的商户描述/交易摘要列表", examples=[["滴滴出行", "瑞幸咖啡", "星巴克"]])

class CategoryResult(BaseModel):
    category: str = Field(..., description="推断出的消费分类")
    confidence: float = Field(..., description="置信度，0.0 到 1.0 之间")
    reason: str = Field(..., description="判断理由，不超过50个字")
    requires_human_review: bool = Field(..., description="如果置信度低于 0.7 或者是未见过的类型，需为 True")

class CategorizeResponse(BaseModel):
    success: bool = Field(..., description="接口调用是否成功")
    mapping: Dict[str, CategoryResult] = Field(..., description="商户描述与消费分类的映射字典")

class Anomaly(BaseModel):
    category: str = Field(..., description="具体类别或项目")
    reason: str = Field(..., description="异常原因")

class AnalyzeDiagnostic(BaseModel):
    overall_evaluation: str = Field(..., description="总体评价")
    risk_warnings: List[str] = Field(..., description="风险提示列表")
    optimization_suggestions: List[str] = Field(..., description="优化建议列表")
    anomalies: List[Anomaly] = Field(default=[], description="可能存在的异常消费或异常占比")

class AnalyzeResponse(BaseModel):
    success: bool = Field(..., description="接口调用是否成功")
    result: AnalyzeDiagnostic = Field(..., description="大模型返回的Markdown格式财务诊断报告")

# ==========================================
# 5. 账单解析：数据模型
# ==========================================

class ParsedTransaction(BaseModel):
    id: str = Field(..., description="交易ID")
    date: str = Field(..., description="交易日期 YYYY-MM-DD")
    amount: float = Field(..., description="交易金额，支出为负数")
    category: str = Field(..., description="消费分类")
    description: str = Field(..., description="交易描述")
    source: str = Field(..., description="来源: wechat / alipay / ccb")
    type: str = Field(..., description="交易类型: expense/income/transfer")
    import_job_id: Optional[str] = Field(None, description="关联的导入任务 ID")

class ParseResponse(BaseModel):
    success: bool = Field(..., description="解析是否成功")
    transactions: List[ParsedTransaction] = Field(..., description="解析后的交易列表")
    message: Optional[str] = Field(None, description="附加信息")
    job_id: Optional[str] = Field(None, description="本次导入任务 ID")
    run_id: Optional[str] = Field(None, description="本次导入任务执行记录 ID")
    job_status: Optional[str] = Field(None, description="本次导入任务状态")
    review_required_count: int = Field(0, description="本次导入仍需人工审核的交易数")
    persisted_count: int = Field(0, description="本次导入实际写入数据库的交易数")

class ImportJobRun(BaseModel):
    id: str = Field(..., description="执行记录 ID")
    job_id: str = Field(..., description="关联的导入任务 ID")
    step: str = Field(..., description="当前或最终停留的执行步骤")
    final_status: str = Field(..., description="执行记录最终状态")
    input_summary: Dict[str, Any] = Field(default_factory=dict, description="输入摘要")
    model_version: Optional[str] = Field(None, description="模型或解析器版本")
    output_summary: Dict[str, Any] = Field(default_factory=dict, description="输出摘要")
    error_message: Optional[str] = Field(None, description="执行错误信息")
    retry_count: int = Field(0, description="重试次数")
    started_at: Optional[datetime] = Field(None, description="执行开始时间")
    finished_at: Optional[datetime] = Field(None, description="执行结束时间")
    updated_at: Optional[datetime] = Field(None, description="执行记录更新时间")

class ImportJob(BaseModel):
    id: str = Field(..., description="导入任务 ID")
    status: str = Field(..., description="导入任务状态")
    source: str = Field(..., description="来源: alipay / wechat / ccb")
    filename: str = Field(..., description="导入文件名")
    total_transactions: int = Field(0, description="本次导入解析到的总交易数")
    review_required_count: int = Field(0, description="仍需人工审核的交易数")
    persisted_count: int = Field(0, description="已写入数据库的交易数")
    error_message: Optional[str] = Field(None, description="失败原因")
    created_at: Optional[datetime] = Field(None, description="任务创建时间")
    started_at: Optional[datetime] = Field(None, description="任务开始时间")
    finished_at: Optional[datetime] = Field(None, description="任务完成时间")
    updated_at: Optional[datetime] = Field(None, description="任务更新时间")
    latest_run: Optional[ImportJobRun] = Field(None, description="最近一次执行记录")

class ImportJobResponse(BaseModel):
    success: bool = Field(..., description="查询是否成功")
    job: Optional[ImportJob] = Field(None, description="导入任务详情；latest 在无记录时为 null")

class MonthlySummary(BaseModel):
    income: float = Field(..., description="月收入合计")
    expense: float = Field(..., description="月支出合计，按正数展示")
    transfer: float = Field(..., description="不计收支/内部流转合计")
    balance: float = Field(..., description="收入减支出后的结余")
    transaction_count: int = Field(..., description="交易笔数")

class CategoryExpense(BaseModel):
    category: str = Field(..., description="分类 code")
    amount: float = Field(..., description="该分类支出合计，按正数展示")
    transaction_count: int = Field(..., description="该分类交易笔数")

class MonthlySummaryResponse(BaseModel):
    success: bool = Field(..., description="查询是否成功")
    month: str = Field(..., description="月份 YYYY-MM")
    summary: MonthlySummary = Field(..., description="月度收支汇总")
    category_expenses: List[CategoryExpense] = Field(..., description="按分类聚合的支出")

class AgentTransaction(BaseModel):
    id: str = Field(..., description="交易 ID")
    date: str = Field(..., description="交易日期 YYYY-MM-DD")
    amount: float = Field(..., description="交易金额，支出为负数")
    category: str = Field(..., description="分类 code")
    description: str = Field(..., description="交易描述")
    source: str = Field(..., description="来源: alipay/wechat/ccb")
    type: str = Field(..., description="交易类型: expense/income/transfer")
    transaction_type: Optional[str] = Field(None, description="原始账单交易类型/分类")
    confidence: Optional[float] = Field(None, description="分类置信度")
    requires_human_review: bool = Field(False, description="是否需要人工审核")
    import_job_id: Optional[str] = Field(None, description="关联的导入任务 ID")

class AgentTransactionsResponse(BaseModel):
    success: bool = Field(..., description="查询是否成功")
    count: int = Field(..., description="返回交易笔数")
    transactions: List[AgentTransaction] = Field(..., description="交易明细列表")

# ==========================================
# 6. 通用函数：调用 DeepSeek API
# ==========================================
def call_deepseek(prompt: str, system_msg: str = "", temperature: float = 0.7, max_tokens: int = 1000) -> str:
    """调用 DeepSeek API"""
    if not AI_API_KEY:
        raise HTTPException(status_code=500, detail="后端未配置 API Key")
    
    # 智能处理 URL，防止重复拼接 /chat/completions
    base_url = AI_BASE_URL.rstrip('/')
    if base_url.endswith('/chat/completions'):
        url = base_url
    else:
        url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = []
    if system_msg:
        messages.append({"role": "system", "content": system_msg})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]

# ==========================================
# 7. 核心路由：批量 AI 分类（Layer 2）
# ==========================================
@app.post(
    "/api/categorize",
    summary="批量 AI 账单分类",
    description="接收一批商户描述，利用大模型推断它们最可能的消费分类（返回带置信度的结构化 JSON）。",
    tags=["AI 核心功能"],
    response_model=CategorizeResponse
)
async def categorize_transactions(request: CategorizeRequest):
    if not AI_API_KEY:
        raise HTTPException(status_code=500, detail="后端未配置 API Key")
    
    descriptions = request.descriptions
    if not descriptions:
        return {"success": True, "mapping": {}}
    
    prompt = f"""
你是一个账单分类助手。根据以下商户描述，推断它们最可能的消费分类。

【支持的分类】
{', '.join(CATEGORIES)}

【商户描述列表】
{chr(10).join([f"{i+1}. {desc}" for i, desc in enumerate(descriptions)])}

【输出要求】
1. 仅输出严格的 JSON 格式，不要有其他文字或 Markdown 标签。
2. JSON 格式需为字典，键为"商户描述"，值为一个对象，结构如下：
{{
  "商户描述（必须与输入完全一致）": {{
    "category": "必须在上方给出的【支持的分类】列表中，如果无法判断填'其他'",
    "confidence": 0.85, 
    "reason": "判断的理由，不超过50个字",
    "requires_human_review": false
  }}
}}
3. “商户描述”键名要完全与输入的参数一致，不要自行填加空格等字符，不要修改标点符号的中英文。
"""

    try:
        result_text = call_deepseek(
            prompt, 
            system_msg="你是一个专业的账单分类助手。请严格输出JSON。",
            temperature=0.3
        )
        
        try:
            mapping = json.loads(result_text)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
            if json_match:
                mapping = json.loads(json_match.group())
            else:
                raise ValueError("无法解析模型返回的 JSON")
        
        return CategorizeResponse(success=True, mapping=mapping)
    
    except Exception as e:
        print(f"AI 分类失败: {e}")
        raise HTTPException(status_code=500, detail=f"AI 分类失败: {str(e)}")

# ==========================================
# 8. 核心路由：AI 财务诊断
# ==========================================
@app.post(
    "/api/analyze",
    summary="AI 财务诊断 (结构化)",
    description="接收前端清洗后的财务汇总数据，调用大模型生成结构化的财务诊断建议（Agent-friendly JSON）。",
    tags=["AI 核心功能"],
    response_model=AnalyzeResponse
)
async def analyze_finances(request: AnalyzeRequest):
    if not AI_API_KEY:
        raise HTTPException(status_code=500, detail="后端未配置 API Key")
        
    data = request.financial_data
    
    prompt = f"""
你是一位专业的个人财务规划师。请根据以下用户的本月账单数据，生成一份结构化的财务诊断报告。

【用户当月收支数据】
- 总收入: {data.summary.income} 元
- 总支出: {data.summary.expense} 元
- 结余: {data.summary.balance} 元

【各项支出占比】
{json.dumps([item.model_dump() for item in data.top_categories], ensure_ascii=False, indent=2)}

【输出要求】
1. 仅输出严格的 JSON 格式，不要有任何其他文字或 Markdown 标签。
2. 结构必须严格符合以下 JSON 格式：
{{
  "overall_evaluation": "总体评价，例如：本月结余良好，但存在部分超支情况...",
  "risk_warnings": [
    "风险提示1...",
    "风险提示2..."
  ],
  "optimization_suggestions": [
    "优化建议1...",
    "优化建议2..."
  ],
  "anomalies": [
    {{
      "category": "具体类别或项目",
      "reason": "异常原因，例如：此分类消费频率异于寻常"
    }}
  ]
}}
"""
    
    try:
        result_text = call_deepseek(
            prompt,
            system_msg="你是一位专业的个人财务规划师。请严格按照要求输出JSON，不带Markdown块语法。",
            temperature=0.7
        )
        
        try:
            result_json = json.loads(result_text)
        except json.JSONDecodeError:
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result_json = json.loads(json_match.group())
            else:
                raise ValueError("无法解析模型返回的 JSON: " + result_text)
                
        return AnalyzeResponse(success=True, result=result_json)
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"调用大模型失败: {error_details}")
        raise HTTPException(status_code=500, detail=f"AI 分析失败: {str(e)} \nTraceback:\n{error_details}")

# ==========================================
# 9. 账单解析：工具函数
# ==========================================

def detect_encoding(content: bytes) -> str:
    """Detect file encoding (utf-8 or gbk)"""
    try:
        content.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        return 'gbk'

# ==========================================
# 4. 账单解析：分类规则与用户记忆库
# ==========================================
import os
import json

USER_RULES_FILE = os.path.join(os.path.dirname(__file__), "user_rules.json")

def get_user_category(description: str) -> Optional[str]:
    """从用户自定义记忆库中读取分类"""
    if not description or not os.path.exists(USER_RULES_FILE):
        return None
    try:
        with open(USER_RULES_FILE, "r", encoding="utf-8") as f:
            rules = json.load(f)
        return rules.get(description)
    except Exception:
        return None

def save_user_category(description: str, category: str):
    """保存或覆盖用户的分类纠偏习惯"""
    if not description:
        return
    rules = {}
    if os.path.exists(USER_RULES_FILE):
        try:
            with open(USER_RULES_FILE, "r", encoding="utf-8") as f:
                rules = json.load(f)
        except Exception:
            pass # 如果文件损坏，就用空字典覆盖
    
    rules[description] = category
    with open(USER_RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

CATEGORY_LABEL_TO_CODE = {
    "转账": "family_support",
    "投资理财": "investment",
    "餐饮": "dining",
    "交通": "transportation",
    "健身健康": "fitness_health",
    "住房": "housing",
    "个人护理": "personal_care",
    "教育": "education",
    "医疗": "healthcare",
    "购物": "shopping",
    "娱乐": "entertainment",
    "数码订阅": "digital_subscription",
    "日用百货": "daily_necessities",
    "收入": "income",
    "其他": "other",
}


def normalize_user_category(category: str) -> str:
    """Normalize UI labels / legacy values into canonical backend category codes."""
    value = (category or "").strip()
    if not value:
        raise ValueError("category 不能为空")
    return CATEGORY_LABEL_TO_CODE.get(value, value)

def classify_transaction(description: str, transaction_type: str, skip_memory: bool = False) -> tuple[str, float, bool]:
    """
    智能分类交易记录 — Rule 引擎版

    采用优先级规则引擎：每个规则独立判断是否匹配，按优先级从高到低执行，
    首个匹配的规则胜出。新增 A/B 只需添加一条 Rule，无需改动主流程。

    置信度体系：
      0.95 — 精准关键词命中（专属词，无歧义，如品牌名/具体品类词）
      0.90 — 场景覆盖命中（次要场景关键词覆盖平台默认）
      0.85 — 通用关键词命中（通用品类词，轻微歧义，如"超市""会员"）
      0.60 — 类型 fallback（中置信度，建议审核）
      0.15 — 模糊转账/人名（低置信度，必须审核）
      0.10 — 兜底 other（低置信度，必须审核）
    """
    description = description.lower() if description else ''
    transaction_type = transaction_type or ''

    # ── 用户记忆（最高优先级，不走规则引擎） ──
    if not skip_memory:
        user_cat = get_user_category(description)
        if user_cat:
            return user_cat, 1.0, False

    # ── 规则引擎：按 priority 降序执行，首个匹配胜出 ──
    for rule in _CLASSIFICATION_RULES:
        result = rule.match(description, transaction_type)
        if result is not None:
            return result.category, result.confidence, result.requires_review

    # ── 兜底 ──
    return 'other', 0.10, True


# ═══════════════════════════════════════════════════════════════
#  Rule 引擎基础设施
# ═══════════════════════════════════════════════════════════════

from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Optional as _Optional


@dataclass(frozen=True)
class ClassificationResult:
    """一条规则的匹配结果"""
    category: str
    confidence: float
    requires_review: bool


class Rule(ABC):
    """分类规则基类。子类实现 match()，返回 ClassificationResult 或 None。"""
    priority: int  # 数值越大优先级越高

    @abstractmethod
    def match(self, description: str, transaction_type: str) -> _Optional[ClassificationResult]:
        ...

    def __repr__(self):
        return f"<{self.__class__.__name__} priority={self.priority}>"


# ── 具体规则实现 ──────────────────────────────────────────────

class TransferKeywordsRule(Rule):
    """语义型转账：信用卡还款等天然表示账户间资金流转的描述。"""
    priority = 90

    _KEYWORDS = ('信用卡还款', '卡号还款', '还信用卡')

    def match(self, description, transaction_type):
        if any(kw in description for kw in self._KEYWORDS):
            return ClassificationResult('transfer', 0.95, False)
        return None


class FamilyTransferRule(Rule):
    """人名/昵称型转账边界：需要家庭关系证据才判为 family_support。"""
    priority = 80

    _FAMILY_KEYWORDS = (
        '妈妈', '爸爸', '妈', '爸', '父母', '家人',
        '爷爷', '奶奶', '外公', '外婆', '姥姥', '姥爷',
        '哥哥', '姐姐', '弟弟', '妹妹', '亲属卡',
        '转账备注:微信转账',
    )
    _AMBIGUOUS_HINTS = (
        '微信转账', '转账给', '向', '收款方', '付款给', '红包', '转账备注',
    )

    def match(self, description, transaction_type):
        has_family = any(kw in description for kw in self._FAMILY_KEYWORDS)
        has_ambiguous = (
            any(kw in description for kw in self._AMBIGUOUS_HINTS)
            or transaction_type in {'转账', '微信转账', '红包'}
        )
        if not has_ambiguous:
            return None
        if has_family:
            return ClassificationResult('family_support', 0.95, False)
        return ClassificationResult('other', 0.15, True)


class PlatformSecondaryOverrideRule(Rule):
    """平台名 + 次要场景关键词覆盖：当平台默认分类与次要场景冲突时，次要场景胜出。"""
    priority = 70

    _PLATFORM_DEFAULTS = {
        'dining': ('美团', '饿了么', '大众点评', '外卖'),
        'shopping': ('淘宝', '天猫', '京东', '拼多多', '抖音商城'),
    }
    _SECONDARY_OVERRIDES = {
        'healthcare': ('药', '买药', '快药', '健康', '医院', '诊所', '门诊', '挂号', '体检'),
        'shopping': ('超市', '便利', '日用', '百货'),
        'transportation': ('出行', '打车', '公交', '地铁'),
    }

    def match(self, description, transaction_type):
        for default_cat, platforms in self._PLATFORM_DEFAULTS.items():
            if any(p in description for p in platforms):
                for override_cat, indicators in self._SECONDARY_OVERRIDES.items():
                    if override_cat != default_cat and any(ind in description for ind in indicators):
                        return ClassificationResult(override_cat, 0.90, False)
        return None


class KeywordMatchRule(Rule):
    """关键词匹配：扫描 CLASSIFICATION_RULES 中的关键词库，区分精准/通用命中。"""
    priority = 50

    # 每个类别的前 N 个关键词视为"精准词"（具体品牌/强特征）
    PRECISE_COUNTS = {
        'family_support': 5,
        'investment': 3,
        'dining': 15,
        'transportation': 10,
        'shopping': 20,
        'digital_subscription': 15,
        'daily_necessities': 15,
        'fitness_health': 10,
        'housing': 8,
        'personal_care': 10,
        'education': 10,
        'healthcare': 10,
        'entertainment': 15,
    }

    def match(self, description, transaction_type):
        for category, rules in CLASSIFICATION_RULES.items():
            keywords = rules['keywords']
            precise_count = self.PRECISE_COUNTS.get(category, 5)
            for i, keyword in enumerate(keywords):
                if keyword.lower() in description:
                    if i < precise_count:
                        return ClassificationResult(category, 0.95, False)
                    else:
                        return ClassificationResult(category, 0.85, False)
        return None


class TypeFallbackRule(Rule):
    """类型 fallback：当关键词未命中时，用交易类型做兜底匹配。"""
    priority = 30

    def match(self, description, transaction_type):
        for category, rules in CLASSIFICATION_RULES.items():
            if transaction_type in rules['types']:
                return ClassificationResult(category, 0.60, True)
        return None


# ── 规则注册（优先级降序） ────────────────────────────────────
_CLASSIFICATION_RULES: list[Rule] = [
    TransferKeywordsRule(),       # 90 — 语义型转账
    FamilyTransferRule(),         # 80 — 人名/昵称转账边界
    PlatformSecondaryOverrideRule(),  # 70 — 平台名 + 次要场景覆盖
    KeywordMatchRule(),           # 50 — 关键词匹配
    TypeFallbackRule(),           # 30 — 类型 fallback
]

def determine_transaction_type(pay_direction: str, amount: float) -> str:
    """Normalize raw bill direction into expense/income/transfer."""
    pay_direction = (pay_direction or '').strip()

    if '不计收支' in pay_direction:
        return 'transfer'
    if '支出' in pay_direction or amount < 0:
        return 'expense'
    if '收入' in pay_direction:
        return 'income'
    return 'transfer'


def detect_bill_format(headers: List[str]) -> Optional[str]:
    """Detect supported bill source from normalized header names."""
    header_set = {str(h).strip() for h in headers if str(h).strip()}

    if '交易时间' in header_set and '交易类型' in header_set and '交易对方' in header_set:
        return 'wechat'
    if '交易时间' in header_set and ('商品说明' in header_set or '交易分类' in header_set):
        return 'alipay'
    if {'摘要', '交易日期', '交易金额', '交易地点/附言'}.issubset(header_set):
        return 'ccb'
    return None


def compact_date_to_iso(text: str) -> str:
    """Convert YYYYMMDD text into YYYY-MM-DD when possible."""
    value = str(text or '').strip()
    if re.fullmatch(r'\d{8}', value):
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    return value.split(' ')[0] if ' ' in value else value


def infer_ccb_pay_direction(summary: str, amount: float, note: str = '') -> str:
    """Infer normalized direction from CCB summary + signed amount."""
    summary = (summary or '').strip()
    note = (note or '').strip()

    if '支付机构提现' in summary or '信用卡卡号还款' in summary:
        return '不计收支'
    if '消费退货' in summary:
        return '收入'
    # 附言含理财/基金/余额宝/零钱通等关键词 → 内部转账，非真实消费
    _transfer_keywords = ('理财', '基金', '余额宝', '零钱通', '定期')
    if any(kw in note for kw in _transfer_keywords):
        return '不计收支'
    if amount < 0:
        return '支出'
    if amount > 0:
        return '收入'
    if '退货' in note:
        return '收入'
    return '不计收支'


def parse_csv_content(content: str, source: str = 'unknown') -> List[dict]:
    """解析 CSV 内容，自动识别微信或支付宝格式，使用动态列索引映射"""
    lines = content.split('\n')
    
    # 找到标题行
    header_line = None
    data_start = 0
    file_type = None
    for i, line in enumerate(lines):
        headers = [h.strip() for h in line.split(',')]
        detected = detect_bill_format(headers)
        if detected in {'wechat', 'alipay'}:
            header_line = line.strip()
            data_start = i + 1
            file_type = detected
            break
    
    if header_line is None:
        raise HTTPException(status_code=400, detail="无法识别 CSV 格式")
    
    # 解析表头，构建列索引映射
    headers = [h.strip() for h in header_line.split(',')]
    column_map = {h: i for i, h in enumerate(headers)}
    
    # 解析数据
    transactions = []
    
    def get_value(row: List[str], col_names: List[str], default: str = '') -> str:
        """动态获取列值，支持多个可能的列名"""
        for col_name in col_names:
            if col_name in column_map and column_map[col_name] < len(row):
                return row[column_map[col_name]].strip()
        return default
    
    for line in lines[data_start:]:
        if not line.strip() or '---' in line:
            continue
        
        values = [v.strip() for v in line.split(',')]
        if len(values) < 5:
            continue
        
        try:
            if file_type == 'wechat':
                date = get_value(values, ['交易时间'])
                trade_type = get_value(values, ['交易类型'])
                counterparty = get_value(values, ['交易对方'])
                description = get_value(values, ['商品']) or counterparty
                pay_direction = get_value(values, ['收/支'])
                amount = float(get_value(values, ['金额(元)', '金额'], '0').replace('¥', '').replace(',', ''))
                status = get_value(values, ['当前状态'])

                # 跳过交易失败、关闭或退款的订单
                if status and ('失败' in status or '关闭' in status or '退款' in status):
                    continue

                transactions.append(build_transaction(
                    date, amount, pay_direction, description, trade_type, 'wechat'
                ))

            else:  # alipay
                date = get_value(values, ['交易时间', '交易创建时间'])
                trade_type = get_value(values, ['交易分类'])
                description = get_value(values, ['商品说明']) or get_value(values, ['交易对方'])
                pay_direction = get_value(values, ['收/支'])
                amount = float(get_value(values, ['金额'], '0').replace('¥', '').replace(',', ''))
                status = get_value(values, ['交易状态'])

                # 支付宝的退款也是一种状态
                if status and ('关闭' in status or '失败' in status or '退款' in status):
                    continue

                transactions.append(build_transaction(
                    date, amount, pay_direction, description, trade_type, 'alipay'
                ))
                
        except (ValueError, IndexError):
            continue
    
    return transactions


# ==========================================
# 9. 共享：构造交易记录
# ==========================================

def normalize_amount(amount: float, normalized_type: str) -> float:
    """根据交易类型规范化金额符号"""
    if normalized_type == 'income':
        return abs(amount)
    elif normalized_type == 'expense':
        return -abs(amount)
    return amount  # transfer 保留原始符号


def build_transaction(date_str: str, amount: float, pay_direction: str,
                      description: str, trade_type: str, source: str) -> dict:
    """从提取的原始值构造标准交易记录"""
    normalized_type = determine_transaction_type(pay_direction, amount)
    final_amount = normalize_amount(amount, normalized_type)
    category, confidence, requires_review = classify_transaction(description, trade_type)

    return {
        'date': date_str,
        'description': description,
        'transaction_type': trade_type,
        'amount': final_amount,
        'category': category,
        'type': normalized_type,
        'source': source,
        'confidence': confidence,
        'requires_human_review': requires_review
    }


# ==========================================
# 10. xlsx 解析函数（支持微信/支付宝 Excel 格式）
# ==========================================

def excel_date_to_str(value) -> str:
    """将 Excel 日期值转换为 YYYY-MM-DD 格式字符串"""
    if isinstance(value, (datetime, date)):
        return value.strftime('%Y-%m-%d')
    if isinstance(value, (int, float)):
        days = int(value) - 25569
        return (datetime(1899, 12, 1) + timedelta(days=days)).strftime('%Y-%m-%d')
    return compact_date_to_iso(str(value))


def parse_excel_rows(file_type: str, headers: List[str], rows: List[List[object]]) -> List[dict]:
    """Parse normalized spreadsheet rows for a known bill format."""
    column_map = {h: i for i, h in enumerate(headers)}
    transactions = []

    def get_value(row: List[object], col_names: List[str], default: str = '') -> str:
        for col_name in col_names:
            idx = column_map.get(col_name)
            if idx is not None and idx < len(row):
                value = row[idx]
                if value is None:
                    return default
                return str(value).strip()
        return default

    for row in rows:
        if not row or all(cell is None or str(cell).strip() == '' for cell in row):
            continue

        try:
            if file_type == 'wechat':
                date = excel_date_to_str(row[column_map.get('交易时间', 0)] or '')
                trade_type = str(row[column_map.get('交易类型', 0)] or '')
                counterparty = str(row[column_map.get('交易对方', 0)] or '')
                description = str(row[column_map.get('商品', 0)] or counterparty)
                pay_direction = str(row[column_map.get('收/支', 0)] or '')
                amount = float(str(row[column_map.get('金额(元)', column_map.get('金额', 0))] or '0').replace('¥', '').replace(',', ''))

                transactions.append(build_transaction(
                    date, amount, pay_direction, description, trade_type, 'wechat'
                ))

            elif file_type == 'alipay':
                date = excel_date_to_str(row[column_map.get('交易时间', column_map.get('交易创建时间', 0))] or '')
                trade_type = str(row[column_map.get('交易分类', 0)] or '')
                description = str(row[column_map.get('商品说明', 0)] or row[column_map.get('交易对方', 0)] or '')
                pay_direction = str(row[column_map.get('收/支', 0)] or '')
                amount = float(str(row[column_map.get('金额', 0)] or '0').replace('¥', '').replace(',', ''))

                transactions.append(build_transaction(
                    date, amount, pay_direction, description, trade_type, 'alipay'
                ))

            elif file_type == 'ccb':
                date = excel_date_to_str(row[column_map.get('交易日期', 0)] or '')
                trade_type = str(row[column_map.get('摘要', 0)] or '')
                note = get_value(row, ['交易地点/附言'])
                description = note or trade_type
                amount = float(get_value(row, ['交易金额'], '0').replace('¥', '').replace(',', ''))
                pay_direction = infer_ccb_pay_direction(trade_type, amount, note)

                transactions.append(build_transaction(
                    date, amount, pay_direction, description, trade_type, 'ccb'
                ))

        except (ValueError, IndexError, TypeError):
            continue

    return transactions


def parse_xls_content(content: bytes) -> List[dict]:
    """解析老式 .xls 文件，当前支持建行样式账单。"""
    if xlrd is None:
        raise ValueError("当前环境缺少 xlrd，无法解析 .xls 文件")

    workbook = xlrd.open_workbook(file_contents=content)
    if workbook.nsheets == 0:
        raise ValueError("Excel 文件中没有可用工作表")

    sheet = workbook.sheet_by_index(0)
    header_idx = None
    headers: List[str] = []
    file_type = None

    for row_idx in range(sheet.nrows):
        row_headers = [
            str(sheet.cell_value(row_idx, col)).strip() if sheet.cell_value(row_idx, col) is not None else ''
            for col in range(sheet.ncols)
        ]
        detected = detect_bill_format(row_headers)
        if detected:
            header_idx = row_idx
            headers = row_headers
            file_type = detected
            break

    if header_idx is None or not file_type:
        raise ValueError("无法识别 xls 文件格式")

    rows = [sheet.row_values(row_idx) for row_idx in range(header_idx + 1, sheet.nrows)]
    return parse_excel_rows(file_type, headers, rows)


def parse_xlsx_content(content: bytes) -> List[dict]:
    """解析 .xlsx Excel 文件，自动识别微信、支付宝或建行格式"""
    wb = load_workbook(io.BytesIO(content), data_only=True)
    ws = wb.active
    if ws is None:
        raise ValueError("Excel 文件中没有活动工作表")

    header_row = None
    headers: List[str] = []
    file_type = None
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        row_headers = [str(col).strip() if col else '' for col in row]
        detected = detect_bill_format(row_headers)
        if detected:
            header_row = row_idx
            headers = row_headers
            file_type = detected
            break

    if header_row is None:
        raise ValueError("未找到有效的表头行")
    if not file_type:
        raise ValueError("无法识别 xlsx 文件格式")

    rows = [list(row) for row in ws.iter_rows(min_row=header_row + 1, values_only=True)]
    return parse_excel_rows(file_type, headers, rows)


# ==========================================
# 10. 核心路由：账单解析
# ==========================================

@app.post(
    "/api/parse",
    summary="解析账单 CSV/XLS/XLSX 文件",
    description="上传微信、支付宝或建行账单 CSV/XLS/XLSX 文件，返回解析后的交易列表",
    tags=["账单解析"],
    response_model=ParseResponse
)
async def parse_bill(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件名")

    filename = file.filename.lower()
    is_excel = filename.endswith('.xlsx') or filename.endswith('.xls')

    if not is_excel and not filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="只支持 CSV、XLS 或 XLSX 文件")

    file_kind = 'xls' if filename.endswith('.xls') else 'xlsx' if filename.endswith('.xlsx') else 'csv'
    job_id = database.create_import_job(filename=file.filename, source='unknown')
    run_id = database.create_import_job_run(
        job_id,
        step='parse_bill',
        input_summary={
            'filename': file.filename,
            'file_kind': file_kind,
            'source': 'unknown',
        },
        model_version=None,
        retry_count=0,
    )
    persisted_count = 0
    review_required_count = 0
    current_step = 'parse_bill'

    try:
        database.update_import_job_status(job_id, 'RUNNING')
        content = await file.read()

        if is_excel:
            if filename.endswith('.xls'):
                transactions_data = parse_xls_content(content)
            else:
                transactions_data = parse_xlsx_content(content)
        else:
            encoding = detect_encoding(content)
            csv_text = content.decode(encoding)
            transactions_data = parse_csv_content(csv_text)

        review_required_count = sum(
            1 for t in transactions_data
            if t.get('requires_human_review') is True or t.get('category') in {'other', '其他'}
        )
        job_status = 'REVIEW_REQUIRED' if review_required_count > 0 else 'SUCCEEDED'

        for t in transactions_data:
            t['import_job_id'] = job_id

        transactions = []
        for i, t in enumerate(transactions_data):
            transactions.append(ParsedTransaction(
                id=f"tx_{i}",
                date=t['date'].split(' ')[0] if ' ' in t['date'] else t['date'],
                amount=t['amount'],
                category=t['category'],
                description=t['description'],
                source=t['source'],
                type=t['type'],
                import_job_id=t.get('import_job_id'),
            ))

        database_enabled = database.is_database_enabled()
        if database_enabled:
            current_step = 'persist_transactions'
            persisted_count = database.save_transactions(transactions_data)
            message = f"成功解析 {len(transactions)} 笔交易，并已写入数据库 {persisted_count} 笔"
        else:
            message = f"成功解析 {len(transactions)} 笔交易；未配置 DATABASE_URL，当前未写入数据库"

        run_step = 'awaiting_human_review' if job_status == 'REVIEW_REQUIRED' else ('persist_transactions' if database_enabled else 'parse_bill')
        failure_policy = 'handoff_to_human_review' if job_status == 'REVIEW_REQUIRED' else 'no_retry_needed'
        database.finalize_import_job_run(
            run_id,
            step=run_step,
            final_status=job_status,
            output_summary={
                'total_transactions': len(transactions),
                'persisted_count': persisted_count,
                'review_required_count': review_required_count,
                'failure_policy': failure_policy,
            },
            error_message=None,
        )
        database.finalize_import_job(
            job_id,
            status=job_status,
            total_transactions=len(transactions),
            review_required_count=review_required_count,
            persisted_count=persisted_count,
            error_message=None,
        )

        return ParseResponse(
            success=True,
            transactions=transactions,
            message=message,
            job_id=job_id,
            run_id=run_id,
            job_status=job_status,
            review_required_count=review_required_count,
            persisted_count=persisted_count,
        )

    except Exception as e:
        try:
            database.finalize_import_job_run(
                run_id,
                step=current_step,
                final_status='FAILED',
                output_summary={
                    'total_transactions': 0,
                    'persisted_count': persisted_count,
                    'review_required_count': review_required_count,
                    'failure_policy': 'mark_failed_and_stop',
                },
                error_message=str(e),
            )
            database.finalize_import_job(
                job_id,
                status='FAILED',
                total_transactions=0,
                review_required_count=0,
                persisted_count=0,
                error_message=str(e),
            )
        except Exception:
            pass
        print(f"解析失败: {e}")
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")

# ==========================================
# 11. Agent-facing 查询 API
# ==========================================

@app.get(
    "/api/agent/monthly-summary",
    summary="查询月度财务汇总",
    description="从 PostgreSQL 读取指定月份的结构化财务快照，供 Agent 调用。",
    tags=["Agent 查询"],
    response_model=MonthlySummaryResponse,
)
async def agent_monthly_summary(month: str = Query(..., pattern=r"^\d{4}-\d{2}$")):
    if not database.is_database_enabled():
        raise HTTPException(status_code=503, detail="未配置 DATABASE_URL，无法查询持久化财务数据")

    try:
        data = database.get_monthly_summary(month)
        return MonthlySummaryResponse(success=True, **data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询月度汇总失败: {str(e)}")

@app.get(
    "/api/agent/transactions",
    summary="查询交易明细",
    description="从 PostgreSQL 按月份、分类、来源和交易类型查询交易明细，供 Agent 调用。",
    tags=["Agent 查询"],
    response_model=AgentTransactionsResponse,
)
async def agent_transactions(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    category: Optional[str] = Query(None),
    source: Optional[str] = Query(None, pattern=r"^(alipay|wechat|ccb)$"),
    type: Optional[str] = Query(None, pattern=r"^(expense|income|transfer)$"),
    limit: int = Query(50, ge=1, le=500),
):
    if not database.is_database_enabled():
        raise HTTPException(status_code=503, detail="未配置 DATABASE_URL，无法查询持久化财务数据")

    try:
        rows = database.get_transactions(
            month=month,
            category=category,
            source=source,
            transaction_type=type,
            limit=limit,
        )
        return AgentTransactionsResponse(success=True, count=len(rows), transactions=[AgentTransaction.model_validate(r) for r in rows])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询交易明细失败: {str(e)}")


@app.get(
    "/api/agent/months",
    summary="查询已有交易的月份列表",
    description="返回数据库中所有存在交易记录的月份（YYYY-MM 格式），供 MCP 工具发现入口",
    tags=["Agent 查询"],
)
async def agent_list_months():
    if not database.is_database_enabled():
        raise HTTPException(status_code=503, detail="未配置 DATABASE_URL，无法查询持久化财务数据")

    try:
        months = database.get_available_months()
        return {"success": True, "months": months}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询月份列表失败: {str(e)}")


@app.get(
    "/api/import-jobs/latest",
    summary="查询最近一次导入任务",
    description="返回最近创建的一次 import job；如果还没有导入记录，则返回 job=null",
    tags=["Import Jobs"],
    response_model=ImportJobResponse,
)
async def get_latest_import_job():
    if not database.is_database_enabled():
        raise HTTPException(status_code=503, detail="未配置 DATABASE_URL，无法查询导入任务")

    try:
        job = database.get_latest_import_job()
        return ImportJobResponse(
            success=True,
            job=ImportJob.model_validate(job) if job else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询最近导入任务失败: {str(e)}")


@app.get(
    "/api/import-jobs/{job_id}",
    summary="查询指定导入任务详情",
    description="按 job_id 返回 import job 详情；如果不存在则返回 404",
    tags=["Import Jobs"],
    response_model=ImportJobResponse,
)
async def get_import_job_detail(job_id: str):
    if not database.is_database_enabled():
        raise HTTPException(status_code=503, detail="未配置 DATABASE_URL，无法查询导入任务")

    try:
        job = database.get_import_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"未找到导入任务: {job_id}")
        return ImportJobResponse(success=True, job=ImportJob.model_validate(job))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询导入任务失败: {str(e)}")


# ==========================================
# 12. 前端静态资源服务（Release 包使用）
# ==========================================
FRONTEND_DIST_DIR = os.path.join(os.path.dirname(__file__), "frontend_dist")

if os.path.isdir(FRONTEND_DIST_DIR):
    assets_dir = os.path.join(FRONTEND_DIST_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(os.path.join(FRONTEND_DIST_DIR, "favicon.ico"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        """Serve the Vue single-page app for local release artifacts."""
        requested_path = os.path.abspath(os.path.join(FRONTEND_DIST_DIR, full_path))
        if requested_path.startswith(os.path.abspath(FRONTEND_DIST_DIR)) and os.path.isfile(requested_path):
            return FileResponse(requested_path)
        return FileResponse(os.path.join(FRONTEND_DIST_DIR, "index.html"))

# ==========================================
# 12. 启动入口
# ==========================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# ==========================================
# 用户自定义分类纠正 API
# ==========================================
class CorrectionRequest(BaseModel):
    transaction_id: Optional[str] = None
    description: str
    category: str
    job_id: Optional[str] = None

@app.post(
    "/api/transactions/correct",
    summary="纠正并记住账单分类",
    tags=["API"]
)
async def correct_transaction_category(req: CorrectionRequest):
    """
    当用户在前端手动纠正一笔账单的分类时，将映射关系存入后端的长期记忆库。
    下次再解析含有该商户名(description)的账单时，将直接使用此分类。
    如果本次请求带了 transaction_id，且数据库已启用，则同步把该笔历史交易写回 PostgreSQL。
    """
    normalized_category = normalize_user_category(req.category)
    save_user_category(req.description, normalized_category)

    updated_transaction = False
    if req.transaction_id and database.is_database_enabled():
        try:
            database.update_transaction_category(req.transaction_id, normalized_category)
            updated_transaction = True
            if req.job_id:
                database.complete_import_job_if_review_finished(req.job_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "success": True,
        "message": "分类习惯已记住，下次将自动应用",
        "normalized_category": normalized_category,
        "updated_transaction": updated_transaction,
    }
