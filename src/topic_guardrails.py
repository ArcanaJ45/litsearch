"""
课题防护栏 (Topic Guardrails)

在最终展示结果前执行规则化的 rerank / filter，确保核心污染物文献优先展示。

当前支持：PFAS 课题专项规则
设计为可扩展：未来可新增重金属、农药等课题的 guardrail 配置。

规则逻辑：
  1. 文献命中课题核心污染物 → 保留，优先排序
  2. 文献未命中核心污染物，但命中了其他明确暴露物（如 nicotine, morphine 等）
     → 大幅降权（relevance_score × penalty_factor）
  3. 文献两者均未命中（可能是泛环境综述、方法学文章）
     → 小幅降权，保留但排在后面
"""

from typing import List
from domain_vocab import (
    PFAS_SYNONYMS, HEAVY_METALS, OTHER_POLLUTANTS,
    NON_PFAS_EXPOSURES,
    match_terms_in_text, topic_contains_pfas,
)

# ─── Guardrail 配置 ──────────────────────────────────

GUARDRAIL_CONFIGS = {
    "pfas": {
        "detect_fn": topic_contains_pfas,
        "target_terms": PFAS_SYNONYMS,
        "negative_terms": NON_PFAS_EXPOSURES,
        "penalty_non_target_exposure": 0.15,   # 命中非目标暴露物 → 分数 × 0.15
        "penalty_no_pollutant": 0.60,           # 无明确污染物 → 分数 × 0.60
        "bonus_target_in_title": 8.0,           # 标题命中核心物 → +8 分
    },
    "heavy_metal": {
        "detect_fn": lambda t: bool(match_terms_in_text(t.lower(), HEAVY_METALS)),
        "target_terms": HEAVY_METALS,
        "negative_terms": NON_PFAS_EXPOSURES | PFAS_SYNONYMS,
        "penalty_non_target_exposure": 0.20,
        "penalty_no_pollutant": 0.65,
        "bonus_target_in_title": 6.0,
    },
}


def apply_topic_guardrails(papers: list, user_topic: str,
                           hide_below: float = 0.0) -> list:
    """
    对排序后的文献列表应用课题防护栏。

    参数:
        papers: 文献列表（已有 relevance_score）
        user_topic: 用户课题描述
        hide_below: 最终分数低于此值的文献将被移除（默认 0 = 不移除）

    返回:
        重新排序（并可能过滤）后的文献列表
    """
    if not user_topic or not papers:
        return papers

    # 识别适用的 guardrail
    active_config = None
    for key, cfg in GUARDRAIL_CONFIGS.items():
        if cfg["detect_fn"](user_topic):
            active_config = cfg
            break

    if active_config is None:
        # 无适用 guardrail，仅按 relevance_score 排序
        papers.sort(key=lambda p: p.relevance_score, reverse=True)
        return papers

    target_terms = active_config["target_terms"]
    negative_terms = active_config["negative_terms"]
    penalty_neg = active_config["penalty_non_target_exposure"]
    penalty_none = active_config["penalty_no_pollutant"]
    bonus_title = active_config["bonus_target_in_title"]

    for p in papers:
        text = f"{p.title} {p.abstract}"
        title_text = p.title or ""

        has_target = bool(match_terms_in_text(text, target_terms))
        has_negative = bool(match_terms_in_text(text, negative_terms))
        target_in_title = bool(match_terms_in_text(title_text, target_terms))

        # 存储 guardrail 标记
        p._guardrail_tag = "neutral"

        if has_target:
            # 核心匹配 → 保留，标题命中额外加分
            p._guardrail_tag = "target_matched"
            if target_in_title:
                p.relevance_score = min(100.0, p.relevance_score + bonus_title)
        elif has_negative:
            # 命中非目标暴露物 → 大幅降权
            p._guardrail_tag = "non_target_penalty"
            p.relevance_score = round(p.relevance_score * penalty_neg, 1)
        else:
            # 无明确污染物 → 小幅降权
            p._guardrail_tag = "no_pollutant_penalty"
            p.relevance_score = round(p.relevance_score * penalty_none, 1)

    # 按调整后的分数重新排序
    papers.sort(key=lambda p: p.relevance_score, reverse=True)

    # 可选：隐藏低分文献
    if hide_below > 0:
        papers = [p for p in papers if p.relevance_score >= hide_below]

    return papers
