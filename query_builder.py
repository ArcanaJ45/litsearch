"""
查询构建器：将关键词或自然语言描述转换为检索式

v2: 支持 PubMed 同义词扩展 (PUBMED_SYNONYM_GROUPS)
    将用户关键词拆分为「概念组」，每组内部 OR 扩展、组间 AND 连接，
    避免把所有词都硬 AND 导致返回 0 结果。
"""

import re
from typing import List, Tuple

from domain_vocab import PUBMED_SYNONYM_GROUPS


# 常见中文→英文环境毒理学术语映射
ZH_EN_MAP = {
    "孕期": "pregnancy",
    "暴露": "exposure",
    "子代": "offspring",
    "神经发育": "neurodevelopment",
    "神经毒性": "neurotoxicity",
    "内分泌干扰": "endocrine disruption",
    "甲状腺": "thyroid",
    "肝毒性": "hepatotoxicity",
    "肾毒性": "nephrotoxicity",
    "生殖毒性": "reproductive toxicity",
    "致癌": "carcinogenicity",
    "氧化应激": "oxidative stress",
    "炎症": "inflammation",
    "表观遗传": "epigenetic",
    "基因表达": "gene expression",
    "流行病学": "epidemiology",
    "队列研究": "cohort study",
    "横断面研究": "cross-sectional study",
    "病例对照": "case-control",
    "meta分析": "meta-analysis",
    "荟萃分析": "meta-analysis",
    "剂量反应": "dose-response",
    "生物标志物": "biomarker",
    "血清": "serum",
    "尿液": "urine",
    "脐带血": "cord blood",
    "母乳": "breast milk",
    "胎盘": "placenta",
    "重金属": "heavy metals",
    "铅": "lead",
    "汞": "mercury",
    "镉": "cadmium",
    "砷": "arsenic",
    "多环芳烃": "polycyclic aromatic hydrocarbons",
    "有机磷": "organophosphorus",
    "农药": "pesticide",
    "空气污染": "air pollution",
    "颗粒物": "particulate matter",
    "水污染": "water contamination",
    "土壤污染": "soil contamination",
    "全氟": "PFAS",
    "双酚": "bisphenol",
    "邻苯二甲酸酯": "phthalate",
    "多溴联苯醚": "PBDE",
    "二噁英": "dioxin",
    "多氯联苯": "PCB",
    "儿童": "children",
    "新生儿": "neonate",
    "出生体重": "birth weight",
    "早产": "preterm birth",
    "发育迟缓": "developmental delay",
    "智力": "intelligence",
    "认知": "cognition",
    "行为": "behavior",
    "注意力": "attention",
    "自闭症": "autism",
    "多动症": "ADHD",
    "肥胖": "obesity",
    "糖尿病": "diabetes",
    "心血管": "cardiovascular",
    "免疫": "immune",
    "过敏": "allergy",
    "哮喘": "asthma",
    # ---- 动物实验相关 ----
    "动物实验": "animal experiment",
    "动物模型": "animal model",
    "小鼠": "mice",
    "大鼠": "rats",
    "小白鼠": "mice",
    "大白鼠": "rats",
    "斑马鱼": "zebrafish",
    "体内实验": "in vivo",
    "体外实验": "in vitro",
    "染毒": "exposure",
    "灌胃": "gavage",
    "腹腔注射": "intraperitoneal injection",
    "毒性": "toxicity",
    "发育毒性": "developmental toxicity",
    "致畸": "teratogenicity",
    "胚胎": "embryo",
    "围产期": "perinatal",
    "哺乳期": "lactation",
    "妊娠期": "gestation",
    "后代": "offspring",
    "环境污染物": "environmental pollutants",
    "持久性有机污染物": "persistent organic pollutants",
    "新污染物": "emerging contaminants",
    "微塑料": "microplastics",
    "纳米颗粒": "nanoparticles",
    "血脑屏障": "blood-brain barrier",
    "突触": "synapse",
    "海马": "hippocampus",
    "皮层": "cortex",
    "学习记忆": "learning and memory",
    "行为学": "behavioral test",
    "旷场实验": "open field test",
    "水迷宫": "Morris water maze",
    "高架十字迷宫": "elevated plus maze",
}

# PubMed 停用词
STOP_WORDS = {
    "的", "了", "在", "是", "和", "与", "对", "及", "或",
    "the", "a", "an", "of", "and", "or", "in", "on", "for",
    "to", "with", "by", "from", "at", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "can", "shall", "that", "this", "these",
    "those", "it", "its", "their", "they", "them", "we", "our",
    "影响", "研究", "关于", "通过", "进行",
}


def contains_chinese(text: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def translate_terms(text: str) -> List[str]:
    """将中文术语翻译为英文关键词"""
    translated = []
    remaining = text

    # 按长度降序匹配，优先匹配长词
    sorted_terms = sorted(ZH_EN_MAP.keys(), key=len, reverse=True)
    for zh in sorted_terms:
        if zh in remaining:
            translated.append(ZH_EN_MAP[zh])
            remaining = remaining.replace(zh, " ")

    # 剩余的英文词直接保留
    for word in remaining.split():
        word = word.strip()
        if word and not contains_chinese(word) and word.lower() not in STOP_WORDS:
            translated.append(word)

    return translated


# ─── 研究类型过滤器 (PubMed MeSH) ─────────────────
STUDY_TYPE_FILTERS = {
    "animal_only": {
        "label": "仅动物实验",
        "pubmed_append": ' AND "Animals"[MeSH] NOT "Humans"[MeSH]',
        "crossref_append": " animal model mice rats in vivo",
    },
    "human_only": {
        "label": "仅人群研究",
        "pubmed_append": ' AND "Humans"[MeSH] NOT "Animals"[MeSH]',
        "crossref_append": " human cohort epidemiology",
    },
    "review_only": {
        "label": "仅综述",
        "pubmed_append": ' AND "Review"[pt]',
        "crossref_append": " review",
    },
    "exclude_review": {
        "label": "排除综述",
        "pubmed_append": ' NOT "Review"[pt]',
        "crossref_append": "",
    },
}


def build_query(user_input: str,
                study_filters: list[str] | None = None) -> Tuple[str, str]:
    """
    将用户输入转换为检索式。
    study_filters: 可选的研究类型过滤器 key 列表，如 ["animal_only", "exclude_review"]
    返回 (pubmed_query, crossref_query)

    PubMed 策略（v2）：
      1. 按空格拆分得到 term 列表
      2. 对每个 term 查 PUBMED_SYNONYM_GROUPS，有则用 OR 扩展组替换
      3. 若多个 term 属于同一概念（如 PFOS、PFOA 都被 "pfas" OR 组覆盖），合并
      4. 不同概念间用 AND 连接
      5. 限制 AND 概念组不超过 3 个，以防止过于严格
    """
    user_input = user_input.strip()

    if contains_chinese(user_input):
        terms = translate_terms(user_input)
    else:
        # 英文输入：按空格拆词，过滤停用词
        raw_words = user_input.split()
        terms = [w for w in raw_words
                 if w.lower() not in STOP_WORDS and len(w) > 1]

    if not terms:
        terms = [user_input]  # fallback

    # ── Crossref：空格连接（它自己做相关性搜索）──
    crossref_query = " ".join(terms)

    # ── PubMed：同义词扩展 + 概念分组 ──
    pubmed_query = _build_pubmed_query(terms)

    # 应用研究类型过滤器
    if study_filters:
        for fkey in study_filters:
            if fkey in STUDY_TYPE_FILTERS:
                flt = STUDY_TYPE_FILTERS[fkey]
                pubmed_query += flt["pubmed_append"]
                crossref_query += flt["crossref_append"]

    return pubmed_query, crossref_query


def _build_pubmed_query(terms: list[str]) -> str:
    """
    根据 PUBMED_SYNONYM_GROUPS 将 terms 扩展为概念组。
    同一个 GROUP key 覆盖的 terms 合并到一个 OR 组，
    不同的 GROUP key 用 AND 连接。

    例: ["PFAS", "neurotoxicity", "pregnancy"]
    → ( "PFAS" OR "PFOS" ... ) AND ( "neurotoxicity" OR "neurodevelopment" ... )
      AND ( "pregnancy" OR "prenatal" ... )
    """
    used_groups = {}     # group_key → expanded string
    standalone = []      # 未被任何 group 覆盖的词

    for t in terms:
        t_lower = t.lower()
        matched_group = None
        for gkey, expanded_str in PUBMED_SYNONYM_GROUPS.items():
            # 精确匹配 OR 词根匹配
            if t_lower == gkey or t_lower in gkey:
                matched_group = gkey
                break
            # 也检查 expanded_str 里是否含有该词（如 "PFOS" 匹配 pfas 组）
            if f'"{t_lower}"' in expanded_str.lower() or f'"{t}"' in expanded_str:
                matched_group = gkey
                break
        if matched_group:
            used_groups[matched_group] = PUBMED_SYNONYM_GROUPS[matched_group]
        else:
            standalone.append(t)

    parts = list(used_groups.values())

    # standalone 词用简单包裹
    for word in standalone:
        # 多词短语用引号，单词直接用
        if " " in word:
            parts.append(f'"{word}"')
        else:
            parts.append(word)

    if not parts:
        return " AND ".join(terms)

    # 限制 AND 组数量≤4，避免过于严格
    if len(parts) > 4:
        # 保留前 4 个最重要的（OR 扩展组优先）
        expanded = [p for p in parts if p.startswith("(")]
        plain = [p for p in parts if not p.startswith("(")]
        parts = expanded[:3] + plain[:1] if expanded else parts[:4]

    return " AND ".join(parts)


def describe_query(user_input: str, pubmed_q: str, crossref_q: str,
                   study_filters: list[str] | None = None) -> str:
    """生成查询说明文本"""
    lines = [
        f"  原始输入: {user_input}",
        f"  PubMed 检索式: {pubmed_q}",
        f"  Crossref 检索词: {crossref_q}",
    ]
    if study_filters:
        labels = [STUDY_TYPE_FILTERS[k]["label"]
                  for k in study_filters if k in STUDY_TYPE_FILTERS]
        if labels:
            lines.append(f"  研究类型过滤: {', '.join(labels)}")
    return "\n".join(lines)
