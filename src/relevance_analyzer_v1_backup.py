"""
相关性分析模块：分析文献与用户课题的相关程度，提取有用信息

功能：
1. 计算文献与用户课题的相关度分数（0-100）
2. 提取摘要中与用户课题最相关的句子
3. 生成对用户课题的参考建议（如何利用该文献改进研究）

使用纯 Python 实现（无需 scikit-learn / nltk 等重依赖），
基于 TF-IDF 余弦相似度和关键词匹配。
"""

import re
import math
from collections import Counter
from typing import List, Tuple, Optional


# ─── 停用词 ──────────────────────────────────────────
STOP_WORDS = {
    # 英文
    "the", "a", "an", "of", "and", "or", "in", "on", "for", "to",
    "with", "by", "from", "at", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can",
    "shall", "that", "this", "these", "those", "it", "its",
    "their", "they", "them", "we", "our", "not", "no", "but",
    "if", "so", "then", "than", "very", "also", "both", "each",
    "all", "any", "more", "most", "other", "some", "such", "into",
    "over", "after", "before", "between", "under", "above", "up",
    "down", "out", "off", "about", "through", "during", "while",
    "which", "who", "whom", "where", "when", "how", "what", "why",
    "as", "s", "t", "don", "didn", "doesn", "isn", "aren", "wasn",
    "weren", "haven", "hasn", "hadn", "won", "wouldn", "couldn",
    "shouldn", "here", "there", "just", "only",
    # 学术常见词（太常见无区分度）
    "study", "studies", "research", "results", "result",
    "found", "showed", "shown", "associated", "using",
    "used", "however", "therefore", "conclusion", "conclusions",
    "method", "methods", "data", "analysis", "analyzed",
    "investigated", "examined", "reported", "observed",
    "significant", "significantly", "compared", "higher",
    "lower", "increased", "decreased", "effect", "effects",
    "group", "groups", "sample", "samples", "total", "among",
    "respectively", "based", "including", "included", "ci",
    "p", "n", "vs", "et", "al",
    # 中文
    "的", "了", "在", "是", "和", "与", "对", "及", "或", "中",
    "为", "有", "我", "你", "他", "她", "它", "们", "这", "那",
    "着", "过", "等", "不", "也", "都", "到", "被", "把", "能",
    "会", "要", "就", "已", "将", "而", "但", "因", "所", "以",
    "关于", "通过", "进行", "具有", "其中", "可以", "本文",
    "研究", "结果", "方法", "分析", "影响",
}


def tokenize(text: str) -> List[str]:
    """
    分词：英文按空格拆分并小写化，中文按字/词切分。
    返回清理后的词列表。
    """
    if not text:
        return []

    # 转小写
    text = text.lower()

    # 移除特殊字符，保留字母数字和中文
    text = re.sub(r'[^\w\u4e00-\u9fff\-]', ' ', text)

    tokens = []
    for word in text.split():
        word = word.strip('-_')
        if not word or len(word) < 2:
            continue
        if word in STOP_WORDS:
            continue
        tokens.append(word)

    return tokens


def compute_tf(tokens: List[str]) -> Counter:
    """计算词频 (Term Frequency)"""
    return Counter(tokens)


def compute_idf(doc_token_lists: List[List[str]]) -> dict:
    """计算逆文档频率 (IDF)"""
    n_docs = len(doc_token_lists)
    if n_docs == 0:
        return {}

    # 每个词出现在多少个文档中
    df = Counter()
    for tokens in doc_token_lists:
        unique_tokens = set(tokens)
        for t in unique_tokens:
            df[t] += 1

    # IDF = log(N / df)
    idf = {}
    for term, doc_freq in df.items():
        idf[term] = math.log((n_docs + 1) / (doc_freq + 1)) + 1

    return idf


def cosine_similarity(vec_a: dict, vec_b: dict) -> float:
    """计算两个稀疏向量的余弦相似度"""
    # 共同词
    common_keys = set(vec_a.keys()) & set(vec_b.keys())
    if not common_keys:
        return 0.0

    dot_product = sum(vec_a[k] * vec_b[k] for k in common_keys)
    mag_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot_product / (mag_a * mag_b)


def compute_relevance(user_topic: str, title: str, abstract: str) -> float:
    """
    计算文献与用户课题的相关度分数。

    返回 0-100 的分数：
      - 80-100: 高度相关
      - 50-80:  中度相关
      - 20-50:  低度相关
      - 0-20:   不太相关

    算法：
      1. TF-IDF 余弦相似度（标题权重 × 2）
      2. 关键词覆盖率加分
      3. 特定领域术语匹配加分
    """
    if not user_topic:
        return 0.0

    # 分词
    topic_tokens = tokenize(user_topic)
    title_tokens = tokenize(title)
    abstract_tokens = tokenize(abstract)

    if not topic_tokens:
        return 0.0

    # 构建文档：标题权重加倍
    paper_tokens = title_tokens * 2 + abstract_tokens

    if not paper_tokens:
        return 0.0

    # ── 1. TF-IDF 余弦相似度 ──
    all_docs = [topic_tokens, paper_tokens]
    idf = compute_idf(all_docs)

    # 计算 TF-IDF 向量
    tf_topic = compute_tf(topic_tokens)
    tf_paper = compute_tf(paper_tokens)

    vec_topic = {t: tf_topic[t] * idf.get(t, 1) for t in tf_topic}
    vec_paper = {t: tf_paper[t] * idf.get(t, 1) for t in tf_paper}

    cos_sim = cosine_similarity(vec_topic, vec_paper)

    # ── 2. 关键词覆盖率 ──
    topic_set = set(topic_tokens)
    paper_set = set(paper_tokens)
    coverage = len(topic_set & paper_set) / len(topic_set) if topic_set else 0

    # ── 3. 综合评分 ──
    # 余弦相似度贡献 60%，覆盖率贡献 40%
    raw_score = cos_sim * 0.6 + coverage * 0.4

    # 映射到 0-100（非线性，让分数分布更合理）
    score = min(100, raw_score * 120)

    return round(score, 1)


def compute_batch_relevance(user_topic: str,
                            papers: list) -> list:
    """
    批量计算文献相关度，使用共享 IDF 以获得更准确的评分。
    papers: List[Paper] (从 models.py)
    """
    if not user_topic:
        return papers

    topic_tokens = tokenize(user_topic)
    if not topic_tokens:
        return papers

    # 构建所有文档的 token 列表
    all_doc_tokens = [topic_tokens]
    paper_token_lists = []
    for p in papers:
        tokens = tokenize(p.title) * 2 + tokenize(p.abstract)
        paper_token_lists.append(tokens)
        all_doc_tokens.append(tokens)

    # 全局 IDF
    idf = compute_idf(all_doc_tokens)

    # 用户课题 TF-IDF 向量
    tf_topic = compute_tf(topic_tokens)
    vec_topic = {t: tf_topic[t] * idf.get(t, 1) for t in tf_topic}
    topic_set = set(topic_tokens)

    for i, p in enumerate(papers):
        if not paper_token_lists[i]:
            p.relevance_score = 0.0
            continue

        tf_paper = compute_tf(paper_token_lists[i])
        vec_paper = {t: tf_paper[t] * idf.get(t, 1) for t in tf_paper}

        cos_sim = cosine_similarity(vec_topic, vec_paper)
        paper_set = set(paper_token_lists[i])
        coverage = len(topic_set & paper_set) / len(topic_set) if topic_set else 0

        raw_score = cos_sim * 0.6 + coverage * 0.4
        p.relevance_score = round(min(100, raw_score * 120), 1)

    return papers


def extract_relevant_sentences(user_topic: str, abstract: str,
                               max_sentences: int = 5) -> List[str]:
    """
    从摘要中提取与用户课题最相关的句子。

    返回按相关度排序的句子列表。
    """
    if not user_topic or not abstract:
        return []

    topic_tokens = set(tokenize(user_topic))
    if not topic_tokens:
        return []

    # 按句号切分摘要
    sentences = re.split(r'[.。!！?？;；]\s*', abstract)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    if not sentences:
        return []

    # 计算每个句子与课题的相关度
    scored = []
    for sent in sentences:
        sent_tokens = set(tokenize(sent))
        if not sent_tokens:
            continue

        # 匹配的关键词数
        matched = topic_tokens & sent_tokens
        if not matched:
            continue

        # 相关度 = 匹配词数 / 课题词数 * 句子长度权重
        relevance = len(matched) / len(topic_tokens)
        # 句子适中长度加分（不太短也不太长）
        len_factor = min(1.0, len(sent_tokens) / 10)
        score = relevance * 0.7 + len_factor * 0.3

        scored.append((score, sent, list(matched)))

    # 按相关度降序排列
    scored.sort(key=lambda x: x[0], reverse=True)

    return [s[1] for s in scored[:max_sentences]]


def generate_insights(user_topic: str, title: str, abstract: str,
                      relevance_score: float = 0) -> str:
    """
    根据文献内容生成对用户课题的参考建议。

    分析文献可能为用户课题提供的帮助：
    - 研究方法参考
    - 数据/证据支持
    - 理论框架借鉴
    - 不同研究角度
    """
    if not user_topic or not abstract:
        return "（需要提供课题描述和文献摘要才能生成分析）"

    topic_tokens = set(tokenize(user_topic))
    title_tokens = set(tokenize(title))
    abstract_tokens = set(tokenize(abstract))
    all_paper_tokens = title_tokens | abstract_tokens

    matched = topic_tokens & all_paper_tokens
    if not matched:
        return "该文献与您的课题关键词重叠较少，可能提供不同视角的参考。"

    insights = []

    # ── 分析研究方法 ──
    method_keywords = {
        "cohort", "cross-sectional", "case-control", "meta-analysis",
        "systematic review", "randomized", "longitudinal", "prospective",
        "retrospective", "in vivo", "in vitro", "mice", "rats",
        "zebrafish", "animal", "model", "experiment", "clinical",
        "trial", "survey", "questionnaire", "biomonitoring",
    }
    methods_found = method_keywords & abstract_tokens
    if methods_found:
        methods_str = "、".join(methods_found)
        insights.append(f"📋 研究方法参考：该文献使用了 {methods_str} 方法，"
                        "可作为您课题研究设计的参考。")

    # ── 分析生物标志物/指标 ──
    biomarker_keywords = {
        "biomarker", "serum", "urine", "blood", "plasma", "cord",
        "concentration", "level", "metabolite", "hormone",
        "receptor", "gene", "protein", "expression", "pathway",
        "oxidative", "antioxidant", "cytokine", "antibody",
    }
    biomarkers_found = biomarker_keywords & abstract_tokens
    if biomarkers_found:
        bio_str = "、".join(biomarkers_found)
        insights.append(f"🔬 生物指标：文献涉及 {bio_str} "
                        "等指标，可考虑在您的研究中参考类似检测指标。")

    # ── 分析统计方法 ──
    stat_keywords = {
        "regression", "correlation", "anova", "chi-square",
        "logistic", "linear", "multivariate", "adjusted",
        "confidence", "odds", "ratio", "hazard", "risk",
        "prevalence", "incidence", "median", "mean", "percentile",
    }
    stats_found = stat_keywords & abstract_tokens
    if stats_found:
        stats_str = "、".join(stats_found)
        insights.append(f"📊 统计分析参考：使用了 {stats_str} "
                        "等统计方法，可为您的数据分析提供思路。")

    # ── 分析健康效应 ──
    health_keywords = {
        "neurodevelopment", "neurotoxicity", "cognitive", "behavior",
        "thyroid", "endocrine", "reproductive", "birth", "weight",
        "preterm", "growth", "obesity", "diabetes", "cancer",
        "cardiovascular", "immune", "allergy", "asthma",
        "inflammation", "apoptosis", "genotoxicity",
    }
    health_found = health_keywords & abstract_tokens
    if health_found:
        health_str = "、".join(health_found)
        insights.append(f"🏥 健康效应：涉及 {health_str} "
                        "等健康终点，与您的课题可能存在关联。")

    # ── 关键词重叠分析 ──
    coverage_pct = len(matched) / len(topic_tokens) * 100 if topic_tokens else 0
    matched_str = "、".join(list(matched)[:8])

    if coverage_pct >= 60:
        insights.insert(0, f"✅ 高度匹配：与您的课题共享关键词 [{matched_str}]，"
                           f"覆盖率 {coverage_pct:.0f}%。该文献很可能直接支持您的研究。")
    elif coverage_pct >= 30:
        insights.insert(0, f"🔶 中度匹配：与您的课题共享关键词 [{matched_str}]，"
                           f"覆盖率 {coverage_pct:.0f}%。可提供部分参考或补充证据。")
    else:
        insights.insert(0, f"🔷 低度匹配：与您的课题共享关键词 [{matched_str}]，"
                           f"覆盖率 {coverage_pct:.0f}%。可作为扩展阅读或不同视角参考。")

    # ── 相关句子 ──
    relevant_sents = extract_relevant_sentences(user_topic, abstract, max_sentences=3)
    if relevant_sents:
        insights.append("\n📖 摘要中与您课题最相关的内容：")
        for i, sent in enumerate(relevant_sents, 1):
            # 截断过长的句子
            if len(sent) > 200:
                sent = sent[:200] + "..."
            insights.append(f"   {i}. {sent}")

    # ── 建议 ──
    if relevance_score >= 70:
        insights.append("\n💡 建议：该文献与您的课题高度相关，建议精读全文，"
                        "重点关注其研究方法、数据来源和主要发现。")
    elif relevance_score >= 40:
        insights.append("\n💡 建议：该文献与您的课题有一定相关性，"
                        "建议阅读其方法和结果部分，看是否能为您的研究提供支持证据或方法参考。")
    else:
        insights.append("\n💡 建议：该文献与您的课题相关性较低，"
                        "但仍可浏览其参考文献列表，可能发现更相关的文献。")

    return "\n".join(insights)


def relevance_level(score: float) -> str:
    """相关度等级标签"""
    if score >= 80:
        return "🔴 高度相关"
    elif score >= 50:
        return "🟠 中度相关"
    elif score >= 20:
        return "🟡 低度相关"
    else:
        return "⚪ 不太相关"
