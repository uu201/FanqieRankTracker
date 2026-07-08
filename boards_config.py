"""
榜单配置 —— 多榜单流水线的单一事实源。

每个榜单(board)描述一个「频道 + 榜单类型」组合，例如：
  - 女频新书榜 (female-new)  —— 已知 init_url = /rank/0_1_1139
  - 男频新书榜 (male-new)    —— 待 discover_boards.py 确认
  - 热销榜     (bestseller) —— 待确认
  - 完结榜     (completed)  —— 待确认

爬虫与构建脚本都从这里读取榜单列表、赛道分组(genre_groups)和题材关键词(keywords)。
赛道分组按「频道」复用：女频一套、男频一套；热销/完结这类跨频道聚合榜可以
不配 genre_groups —— 此时构建脚本会自动跳过「综合赛道」聚合，只产出「具体分类」热度。
"""

# ============================================================
#  题材关键词：按频道区分（命中新书简介即加权）
# ============================================================

FEMALE_KEYWORDS = [
    "重生", "穿书", "快穿", "系统", "空间", "团宠", "萌宝", "幼崽", "女配", "炮灰",
    "反派", "权臣", "宅斗", "宫斗", "和离", "替嫁", "逃荒", "种田", "美食", "经商",
    "年代", "七零", "八零", "军婚", "豪门", "总裁", "真假千金", "先婚后爱", "追妻",
    "甜宠", "双洁", "强制爱", "无CP", "末世", "废土", "天灾", "囤货", "异能",
    "国运", "星际", "修仙", "玄学", "无限流", "悬疑", "直播", "综艺", "娱乐圈",
    "校园", "暗恋", "青梅竹马", "民国", "兽世", "远古", "基建",
]

# 男频常见题材（参考番茄男频高频标签，可在拿到真实分类后增补）
MALE_KEYWORDS = [
    "系统", "重生", "穿越", "无敌", "签到", "苟道", "种田", "无限流", "诸天", "万界",
    "都市", "异能", "兵王", "战神", "赘婿", "神医", "金融", "鉴宝", "美食", "直播",
    "玄幻", "修仙", "炼丹", "宗门", "废柴逆袭", "天才", "废土", "末世", "丧尸", "星际",
    "机甲", "科技", "工业", "国运", "历史", "争霸", "三国", "大明", "种马", "后宫",
    "网游", "电竞", "副本", "克苏鲁", "灵异", "规则怪谈", "悬疑", "推理", "盗墓",
    "扮猪吃虎", "杀伐果断", "热血", "龙傲天",
]

# 通用关键词（跨频道兜底用，男女题材合并；当前 4 榜均按频道用专属词表）
GENERAL_KEYWORDS = list(dict.fromkeys(FEMALE_KEYWORDS + MALE_KEYWORDS))


# ============================================================
#  综合赛道分组：按频道区分
# ============================================================

FEMALE_GENRE_GROUPS = [
    {"name": "古风言情", "categories": ["古风世情", "古言脑洞", "宫斗宅斗", "种田"]},
    {"name": "现代言情", "categories": ["现言脑洞", "豪门总裁", "职场婚恋", "青春甜宠"]},
    {"name": "幻想言情", "categories": ["玄幻言情", "科幻末世", "悬疑脑洞", "女频悬疑"]},
    {"name": "快穿衍生", "categories": ["快穿", "女频衍生"]},
    {"name": "年代民国", "categories": ["年代", "民国言情"]},
    {"name": "娱乐星光", "categories": ["星光璀璨"]},
    {"name": "游戏体育", "categories": ["游戏体育"]},
]

# 男频赛道分组（与当前 discover 到的男频分类名保持一致）
MALE_GENRE_GROUPS = [
    {"name": "玄幻仙侠", "categories": ["西方奇幻", "东方仙侠", "传统玄幻", "玄幻脑洞"]},
    {"name": "都市现实", "categories": ["都市日常", "都市修真", "都市高武", "都市种田", "都市脑洞", "战神赘婿"]},
    {"name": "历史军事", "categories": ["历史古代", "历史脑洞", "抗战谍战"]},
    {"name": "科幻末世", "categories": ["科幻末世"]},
    {"name": "悬疑灵异", "categories": ["悬疑脑洞", "悬疑灵异"]},
    {"name": "游戏衍生", "categories": ["游戏体育", "动漫衍生", "男频衍生"]},
]


# ============================================================
#  榜单注册表
# ============================================================
#  字段：
#    slug           —— 英文短名，决定数据目录 data/<slug>/ 与 api/<slug>/
#    name           —— 中文榜单名，前端展示
#    channel        —— female / male
#    init_url       —— 榜单入口页（分类自动从页面发现）
#    rank_prefix    —— /rank/<prefix>_<分类> 的频道+类型前缀，用于过滤本榜分类
#    enabled        —— 是否参与抓取/构建
#    genre_groups   —— 赛道分组；None 表示不做赛道聚合
#    keywords       —— 题材关键词表
#
#  URL 规律：/rank/<频道>_<类型>_<分类>
#    频道 0=女频 1=男频；类型 1=新书榜 2=阅读榜。
#    新书榜与阅读榜共享同频道的分类目录，故复用同一套 genre_groups / keywords。

BOARDS = [
    {
        "slug": "female-new",
        "name": "女频新书榜",
        "channel": "female",
        "init_url": "https://fanqienovel.com/rank/0_1_1139",
        "rank_prefix": "0_1",
        "enabled": True,
        "genre_groups": FEMALE_GENRE_GROUPS,
        "keywords": FEMALE_KEYWORDS,
    },
    {
        "slug": "female-read",
        "name": "女频阅读榜",
        "channel": "female",
        "init_url": "https://fanqienovel.com/rank/0_2_1139",
        "rank_prefix": "0_2",
        "enabled": True,
        "genre_groups": FEMALE_GENRE_GROUPS,
        "keywords": FEMALE_KEYWORDS,
    },
    {
        "slug": "male-new",
        "name": "男频新书榜",
        "channel": "male",
        "init_url": "https://fanqienovel.com/rank/1_1_1141",
        "rank_prefix": "1_1",
        "enabled": True,
        "genre_groups": MALE_GENRE_GROUPS,
        "keywords": MALE_KEYWORDS,
    },
    {
        "slug": "male-read",
        "name": "男频阅读榜",
        "channel": "male",
        "init_url": "https://fanqienovel.com/rank/1_2_1141",
        "rank_prefix": "1_2",
        "enabled": True,
        "genre_groups": MALE_GENRE_GROUPS,
        "keywords": MALE_KEYWORDS,
    },
]


def enabled_boards():
    """返回已启用且配置了 init_url 的榜单。"""
    return [b for b in BOARDS if b.get("enabled") and b.get("init_url")]


def get_board(slug: str):
    for b in BOARDS:
        if b["slug"] == slug:
            return b
    return None


def board_public_meta(board: dict) -> dict:
    """供前端 api/boards.json 使用的精简元信息。"""
    return {
        "slug": board["slug"],
        "name": board["name"],
        "channel": board["channel"],
        "has_genres": bool(board.get("genre_groups")),
    }
