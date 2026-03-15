"""
国际化模块：支持中英文切换。
"""

_lang = "en"
_callbacks: list = []


def get_lang() -> str:
    return _lang


def set_lang(lang: str) -> None:
    global _lang
    _lang = lang
    for cb in list(_callbacks):
        try:
            cb()
        except Exception:
            pass


def toggle() -> None:
    set_lang("en" if _lang == "zh" else "zh")


def register(callback) -> None:
    if callback not in _callbacks:
        _callbacks.append(callback)


def unregister(callback) -> None:
    if callback in _callbacks:
        _callbacks.remove(callback)


def t(text: str) -> str:
    """翻译 UI 字符串。"""
    if _lang == "zh":
        return text
    return _UI_EN.get(text, text)


def pos_t(zh_name: str) -> str:
    """翻译位置名称。"""
    if _lang == "zh":
        return zh_name
    return _POS_EN.get(zh_name, zh_name)


def attr_t(pm_idx: int, zh_name: str) -> str:
    """翻译球员属性（pm_ 系列）。"""
    if _lang == "zh":
        return zh_name
    return _PM_EN.get(pm_idx, zh_name)


def hidden_t(ph_idx: int, zh_name: str) -> str:
    """翻译隐藏属性（ph_ 系列）。"""
    if _lang == "zh":
        return zh_name
    return _PH_EN.get(ph_idx, zh_name)


def attr_name_t(zh_name: str) -> str:
    """按中文名称翻译属性（用于没有 idx 的场合，如推荐卡片）。"""
    if _lang == "zh":
        return zh_name
    return _ZH_ATTR_NAME_EN.get(zh_name, zh_name)


# ── 位置名称 ──────────────────────────────────────────────────────
_POS_EN = {
    "门将":   "GK",
    "未知":   "Unknown",
    "左后卫": "LB",
    "中后卫": "CB",
    "右后卫": "RB",
    "防守中场": "DM",
    "左前卫": "LM",
    "中前卫": "CM",
    "右前卫": "RM",
    "左路攻前": "AML",
    "中路攻前": "AMC",
    "右路攻前": "AMR",
    "前锋":   "ST",
    "左翼卫": "LWB",
    "右翼卫": "RWB",
}

# ── 球员属性（pm_ 索引）────────────────────────────────────────────
_PM_EN = {
    # Technical
    42: "Corners",
    15: "Crossing",
    16: "Dribbling",
    17: "Finishing",
    37: "First Touch",
    50: "Free Kick",
    18: "Heading",
    19: "Long Shots",
    45: "Long Throws",
    20: "Marking",
    22: "Passing",
    23: "Pen. Taking",
    24: "Tackling",
    38: "Technique",
    # GK Technical
    27: "Aerial Reach",
    28: "Cmd of Area",
    29: "Communication",
    46: "Eccentricity",
    26: "Handling",
    30: "Kicking",
    34: "One on Ones",
    48: "Punching",
    36: "Reflexes",
    47: "Rushing Out",
    31: "Throwing",
    # Mental
    60: "Aggression",
    32: "Anticipation",
    58: "Bravery",
    67: "Composure",
    68: "Concentration",
    33: "Decisions",
    66: "Determination",
    41: "Flair",
    55: "Leadership",
    21: "Off The Ball",
    35: "Positioning",
    43: "Teamwork",
    25: "Vision",
    44: "Work Rate",
    # Physical
    49: "Acceleration",
    56: "Agility",
    57: "Balance",
    54: "Jumping Reach",
    65: "Natural Fitness",
    53: "Pace",
    52: "Stamina",
    51: "Strength",
    39: "Left Foot",
    40: "Right Foot",
    # Personality
    59: "Consistency",
    61: "Versatility",
    62: "Big Matches",
    63: "Injury Prone",
    64: "Adaptability",
}

# ── 隐藏属性（ph_ 索引）───────────────────────────────────────────
_PH_EN = {
    0: "Adaptability",
    1: "Ambition",
    2: "Controversy",
    3: "Loyalty",
    4: "Pressure",
    5: "Professionalism",
    6: "Sportsmanship",
    7: "Temperament",
}

# ── UI 字符串 ─────────────────────────────────────────────────────
_UI_EN = {
    # main.py
    "正在加载球员数据，请稍候…": "Loading player data, please wait…",
    "发生错误": "Error",
    # list_page.py
    "⚽ Football Hacker — 球员数据库": "⚽ Football Hacker — Player Database",
    "输入球员姓名后按回车或点击搜索…": "Enter name and press Enter or click Search…",
    "搜索": "Search",
    "加载中…": "Loading…",
    "双击行查看球员详情  ·  点击表头排序": "Double-click for details  ·  Click header to sort",
    # list columns
    "姓名":   "Name",
    "当前能力": "Ability",
    "潜力上限": "Potential",
    "能力变化": "Ability Δ",
    "潜力变化": "Potential Δ",
    "年龄":   "Age",
    "主要位置": "Position",
    # detail_page.py
    "← 返回列表": "← Back to List",
    "赛季：":  "Season:",
    "基本信息": "Basic Info",
    "出生日期": "Born",
    "身高":   "Height",
    "国籍":   "Nationality",
    "球衣号":  "Squad No.",
    "薪资（/周）": "Wage (/wk)",
    "所属球队：": "Club:",
    "能力值":  "Ability",
    "位置评分": "Position Ratings",
    "技术":   "Technical",
    "门将":   "Goalkeeper",
    "心理":   "Mental",
    "身体":   "Physical",
    "性格":   "Personality",
    # club_page.py
    "← 返回球员": "← Back to Player",
    "推荐引援": "Recommend Signings",
    # recommend dialog
    "重新推荐": "Recommend Again",
    "关闭":   "Close",
    "正在分析阵容，请稍候…": "Analyzing squad, please wait…",
    "推荐失败，请检查模型文件是否存在。": "Recommendation failed. Please check model files.",
}

# ── 按中文名称翻译属性（推荐卡片等无 idx 场合）────────────────────
_ZH_ATTR_NAME_EN = {
    "角球": "Corners", "传中": "Crossing", "盘带": "Dribbling",
    "射门": "Finishing", "停球": "First Touch", "任意球": "Free Kick",
    "头球": "Heading", "远射": "Long Shots", "界外球": "Long Throws",
    "盯人": "Marking", "传球": "Passing", "点球": "Pen. Taking",
    "抢断": "Tackling", "技术": "Technique",
    "制空范围": "Aerial Reach", "拦截传中": "Cmd of Area",
    "指挥防守": "Communication", "意外性": "Eccentricity",
    "手控球": "Handling", "大脚开球": "Kicking",
    "一对一": "One on Ones", "击球倾向": "Punching",
    "反应": "Reflexes", "出击倾向": "Rushing Out", "手抛球": "Throwing",
    "侵略性": "Aggression", "预判": "Anticipation", "勇敢": "Bravery",
    "镇定": "Composure", "专注": "Concentration", "决断": "Decisions",
    "意志力": "Determination", "才华": "Flair", "领导力": "Leadership",
    "无球跑动": "Off The Ball", "防守站位": "Positioning",
    "团队合作": "Teamwork", "视野": "Vision", "工作投入": "Work Rate",
    "爆发力": "Acceleration", "灵活": "Agility", "平衡": "Balance",
    "弹跳": "Jumping Reach", "体质": "Natural Fitness", "速度": "Pace",
    "耐力": "Stamina", "强壮": "Strength",
    "左脚": "Left Foot", "右脚": "Right Foot",
}
