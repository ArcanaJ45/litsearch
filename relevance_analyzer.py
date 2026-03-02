"""
相关性分析 v2：多维度规则评分（可解释）

评分维度与权重：
  a) 污染物匹配     30 分（最高权重，精准锚定课题核心物质）
  b) 暴露窗口匹配   15 分
  c) 研究对象匹配   10 分
  d) 结局/终点匹配  25 分
  e) 机制/方法匹配  10 分
  f) TF-IDF 语义    10 分（保留原有能力，作为兜底项）
  总分 = 100 分

每篇文献输出：
  - relevance_score: float (0-100)
  - relevance_details: dict  (各维度得分 + 命中词列表)
"""

import re
import math
from collections import Counter
from typing import List, Dict, Optional, Any

from domain_vocab import (
    PFAS_SYNONYMS, HEAVY_METALS, OTHER_POLLUTANTS,
    NON_PFAS_EXPOSURES,
    EXPOSURE_WINDOWS, STUDY_SUBJECTS,
    NEURO_OUTCOMES, ENDOCRINE_OUTCOMES, IMMUNE_OUTCOMES,
    METABOLIC_OUTCOMES, CANCER_OUTCOMES,
    MECHANISM_TERMS, METHOD_TERMS,
    match_terms_in_text,
)


STOP_WORDS = {
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
}


def _build_topic_profile(user_topic):
    text = user_topic.lower()
    pollutant_set = set()
    pollutant_label = "unknown"
    if match_terms_in_text(text, PFAS_SYNONYMS):
        pollutant_set = PFAS_SYNONYMS
        pollutant_label = "PFAS"
    elif match_terms_in_text(text, HEAVY_METALS):
        pollutant_set = HEAVY_METALS
        pollutant_label = "heavy_metal"
    elif match_terms_in_text(text, OTHER_POLLUTANTS):
        pollutant_set = OTHER_POLLUTANTS
        pollutant_label = "other_pollutant"

    topic_windows = set()
    for key, info in EXPOSURE_WINDOWS.items():
        if match_terms_in_text(text, info["terms"]):
            topic_windows.add(key)

    topic_outcomes = set()
    outcome_sets = {
        "neuro": NEURO_OUTCOMES,
        "endocrine": ENDOCRINE_OUTCOMES,
        "immune": IMMUNE_OUTCOMES,
        "metabolic": METABOLIC_OUTCOMES,
        "cancer": CANCER_OUTCOMES,
    }
    for key, oset in outcome_sets.items():
        if match_terms_in_text(text, oset):
            topic_outcomes.add(key)

    topic_subjects = set()
    for key, info in STUDY_SUBJECTS.items():
        if match_terms_in_text(text, info["terms"]):
            topic_subjects.add(key)

    return {
        "pollutant_set": pollutant_set,
        "pollutant_label": pollutant_label,
        "windows": topic_windows,
        "outcomes": topic_outcomes,
        "subjects": topic_subjects,
    }


def _score_pollutant(text, profile):
    if not profile["pollutant_set"]:
        return 15.0, [], "未指定课题污染物"
    matched = match_terms_in_text(text, profile["pollutant_set"])
    if matched:
        score = min(30.0, 20.0 + len(matched) * 2)
        return score, list(matched), "命中 " + profile["pollutant_label"]
    non_target = match_terms_in_text(text, NON_PFAS_EXPOSURES)
    if non_target:
        return 0.0, list(non_target), "命中非目标暴露物: " + ", ".join(list(non_target)[:3])
    return 5.0, [], "未明确提及目标污染物"


def _score_exposure_window(text, profile):
    if not profile["windows"]:
        return 7.5, [], "未指定暴露窗口"
    all_window_terms = set()
    for wkey in profile["windows"]:
        if wkey in EXPOSURE_WINDOWS:
            all_window_terms |= EXPOSURE_WINDOWS[wkey]["terms"]
    matched = match_terms_in_text(text, all_window_terms)
    if matched:
        score = min(15.0, 10.0 + len(matched) * 1.5)
        return score, list(matched), "暴露窗口匹配"
    return 2.0, [], "未匹配暴露窗口"


def _score_subject(text, profile):
    if not profile["subjects"]:
        return 5.0, [], "未指定研究对象"
    best_score = 0.0
    best_matched = []
    best_reason = "未匹配研究对象"
    for skey in profile["subjects"]:
        if skey in STUDY_SUBJECTS:
            terms = STUDY_SUBJECTS[skey]["terms"]
            matched = match_terms_in_text(text, terms)
            if matched:
                sc = min(10.0, 7.0 + len(matched) * 0.5)
                if sc > best_score:
                    best_score = sc
                    best_matched = list(matched)
                    best_reason = "研究对象: " + STUDY_SUBJECTS[skey]["label"]
    if best_score == 0:
        return 2.0, [], best_reason
    return best_score, best_matched, best_reason


def _score_outcome(text, profile):
    outcome_map = {
        "neuro": NEURO_OUTCOMES,
        "endocrine": ENDOCRINE_OUTCOMES,
        "immune": IMMUNE_OUTCOMES,
        "metabolic": METABOLIC_OUTCOMES,
        "cancer": CANCER_OUTCOMES,
    }
    if not profile["outcomes"]:
        all_matched = set()
        for oset in outcome_map.values():
            all_matched |= match_terms_in_text(text, oset)
        if all_matched:
            return min(15.0, 8.0 + len(all_matched)), list(all_matched), "潜在相关结局"
        return 5.0, [], "未指定结局类型"
    target_terms = set()
    for okey in profile["outcomes"]:
        if okey in outcome_map:
            target_terms |= outcome_map[okey]
    matched = match_terms_in_text(text, target_terms)
    if matched:
        score = min(25.0, 15.0 + len(matched) * 1.5)
        return score, list(matched), "目标结局匹配"
    other_matched = set()
    for okey, oset in outcome_map.items():
        if okey not in profile["outcomes"]:
            other_matched |= match_terms_in_text(text, oset)
    if other_matched:
        return 5.0, list(other_matched), "非目标结局"
    return 2.0, [], "未匹配结局"


def _score_mechanism(text):
    mech_matched = match_terms_in_text(text, MECHANISM_TERMS)
    method_matched = match_terms_in_text(text, METHOD_TERMS)
    all_matched = mech_matched | method_matched
    if all_matched:
        score = min(10.0, 3.0 + len(all_matched) * 1.0)
        return score, list(all_matched), "机制/方法匹配"
    return 1.0, [], "无机制/方法关键词"


def _score_tfidf(topic_tokens, paper_tokens, idf=None):
    if not topic_tokens or not paper_tokens:
        return 0.0, [], "无法计算"
    if idf is None:
        all_docs = [topic_tokens, paper_tokens]
        n_docs = len(all_docs)
        df = Counter()
        for tokens in all_docs:
            for t in set(tokens):
                df[t] += 1
        idf = {t: math.log((n_docs + 1) / (d + 1)) + 1 for t, d in df.items()}
    tf_topic = Counter(topic_tokens)
    tf_paper = Counter(paper_tokens)
    vec_topic = {t: tf_topic[t] * idf.get(t, 1) for t in tf_topic}
    vec_paper = {t: tf_paper[t] * idf.get(t, 1) for t in tf_paper}
    common = set(vec_topic) & set(vec_paper)
    if not common:
        return 0.0, [], "无共同词"
    dot = sum(vec_topic[k] * vec_paper[k] for k in common)
    mag_a = math.sqrt(sum(v ** 2 for v in vec_topic.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in vec_paper.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0, [], "无共同词"
    cos_sim = dot / (mag_a * mag_b)
    score = round(min(10.0, cos_sim * 12), 1)
    return score, list(common)[:5], "cos=" + str(round(cos_sim, 3))


def tokenize(text):
    if not text:
        return []
    text = text.lower()
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


def compute_relevance(user_topic, title, abstract):
    details = compute_relevance_detailed(user_topic, title, abstract)
    return details["total_score"]


def compute_relevance_detailed(user_topic, title, abstract):
    if not user_topic:
        return {"total_score": 0.0, "dimensions": {}}
    profile = _build_topic_profile(user_topic)
    title_text = title or ""
    full_text = title_text + " " + (abstract or "")

    poll_score, poll_matched, poll_reason = _score_pollutant(full_text, profile)
    title_poll = match_terms_in_text(title_text, profile["pollutant_set"])
    if title_poll:
        poll_score = min(30.0, poll_score + 3.0)

    win_score, win_matched, win_reason = _score_exposure_window(full_text, profile)
    subj_score, subj_matched, subj_reason = _score_subject(full_text, profile)

    out_score, out_matched, out_reason = _score_outcome(full_text, profile)
    all_outcome_terms = (NEURO_OUTCOMES | ENDOCRINE_OUTCOMES |
                         IMMUNE_OUTCOMES | METABOLIC_OUTCOMES | CANCER_OUTCOMES)
    title_outcomes = match_terms_in_text(title_text, all_outcome_terms)
    if title_outcomes:
        out_score = min(25.0, out_score + 2.0)

    mech_score, mech_matched, mech_reason = _score_mechanism(full_text)

    topic_tokens = tokenize(user_topic)
    paper_tokens = tokenize(title) * 2 + tokenize(abstract)
    tfidf_score, tfidf_matched, tfidf_reason = _score_tfidf(topic_tokens, paper_tokens)

    total = round(poll_score + win_score + subj_score + out_score + mech_score + tfidf_score, 1)
    total = min(100.0, max(0.0, total))

    return {
        "total_score": total,
        "dimensions": {
            "pollutant": {"score": poll_score, "max": 30, "matched": poll_matched, "reason": poll_reason},
            "exposure_window": {"score": win_score, "max": 15, "matched": win_matched, "reason": win_reason},
            "subject": {"score": subj_score, "max": 10, "matched": subj_matched, "reason": subj_reason},
            "outcome": {"score": out_score, "max": 25, "matched": out_matched, "reason": out_reason},
            "mechanism": {"score": mech_score, "max": 10, "matched": mech_matched, "reason": mech_reason},
            "tfidf": {"score": tfidf_score, "max": 10, "matched": tfidf_matched, "reason": tfidf_reason},
        },
    }


def compute_batch_relevance(user_topic, papers):
    if not user_topic:
        return papers
    profile = _build_topic_profile(user_topic)
    topic_tokens = tokenize(user_topic)
    all_doc_tokens = [topic_tokens]
    paper_token_cache = []
    for p in papers:
        tokens = tokenize(p.title) * 2 + tokenize(p.abstract)
        paper_token_cache.append(tokens)
        all_doc_tokens.append(tokens)
    n_docs = len(all_doc_tokens)
    df = Counter()
    for tokens in all_doc_tokens:
        for t in set(tokens):
            df[t] += 1
    global_idf = {t: math.log((n_docs + 1) / (d + 1)) + 1 for t, d in df.items()}

    for i, p in enumerate(papers):
        title_text = p.title or ""
        full_text = title_text + " " + (p.abstract or "")
        poll_score, poll_matched, poll_reason = _score_pollutant(full_text, profile)
        title_poll = match_terms_in_text(title_text, profile["pollutant_set"])
        if title_poll:
            poll_score = min(30.0, poll_score + 3.0)
        win_score, win_matched, win_reason = _score_exposure_window(full_text, profile)
        subj_score, subj_matched, subj_reason = _score_subject(full_text, profile)
        out_score, out_matched, out_reason = _score_outcome(full_text, profile)
        all_outcome_terms = (NEURO_OUTCOMES | ENDOCRINE_OUTCOMES |
                             IMMUNE_OUTCOMES | METABOLIC_OUTCOMES | CANCER_OUTCOMES)
        title_outcomes = match_terms_in_text(title_text, all_outcome_terms)
        if title_outcomes:
            out_score = min(25.0, out_score + 2.0)
        mech_score, mech_matched, mech_reason = _score_mechanism(full_text)
        tfidf_score, tfidf_matched, tfidf_reason = _score_tfidf(
            topic_tokens, paper_token_cache[i], idf=global_idf)
        total = round(poll_score + win_score + subj_score + out_score + mech_score + tfidf_score, 1)
        total = min(100.0, max(0.0, total))
        p.relevance_score = total
        p._relevance_details = {
            "pollutant": {"score": poll_score, "matched": poll_matched, "reason": poll_reason},
            "exposure_window": {"score": win_score, "matched": win_matched, "reason": win_reason},
            "subject": {"score": subj_score, "matched": subj_matched, "reason": subj_reason},
            "outcome": {"score": out_score, "matched": out_matched, "reason": out_reason},
            "mechanism": {"score": mech_score, "matched": mech_matched, "reason": mech_reason},
            "tfidf": {"score": tfidf_score, "matched": tfidf_matched, "reason": tfidf_reason},
        }
    return papers


def extract_relevant_sentences(user_topic, abstract, max_sentences=5):
    if not user_topic or not abstract:
        return []
    topic_tokens = set(tokenize(user_topic))
    if not topic_tokens:
        return []
    sentences = re.split(r'[.。!！?？;；]\s*', abstract)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    if not sentences:
        return []
    scored = []
    for sent in sentences:
        sent_tokens = set(tokenize(sent))
        if not sent_tokens:
            continue
        matched = topic_tokens & sent_tokens
        if not matched:
            continue
        relevance = len(matched) / len(topic_tokens)
        len_factor = min(1.0, len(sent_tokens) / 10)
        score = relevance * 0.7 + len_factor * 0.3
        scored.append((score, sent, list(matched)))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s[1] for s in scored[:max_sentences]]


def generate_insights(user_topic, title, abstract, relevance_score=0):
    if not user_topic or not abstract:
        return "（需要提供课题描述和文献摘要才能生成分析）"
    details = compute_relevance_detailed(user_topic, title, abstract)
    dims = details["dimensions"]
    insights = []
    total = details["total_score"]
    if total >= 75:
        insights.append(" 综合相关度: {:.0f}/100  高度相关".format(total))
    elif total >= 45:
        insights.append(" 综合相关度: {:.0f}/100  中度相关".format(total))
    elif total >= 20:
        insights.append(" 综合相关度: {:.0f}/100  低度相关".format(total))
    else:
        insights.append(" 综合相关度: {:.0f}/100  关联较弱".format(total))

    insights.append("\n 各维度评分：")
    dim_labels = {
        "pollutant": "污染物匹配",
        "exposure_window": "暴露窗口",
        "subject": "研究对象",
        "outcome": "健康结局",
        "mechanism": "机制/方法",
        "tfidf": "语义相似度",
    }
    for key, label in dim_labels.items():
        d = dims[key]
        bar_len = int(d["score"] / d["max"] * 10) if d["max"] > 0 else 0
        bar = "" * bar_len + "" * (10 - bar_len)
        matched_str = ""
        if d["matched"]:
            matched_str = "  " + ", ".join(d["matched"][:4])
        insights.append("  {}: {:.0f}/{} {}{}".format(label, d["score"], d["max"], bar, matched_str))

    if dims["pollutant"]["matched"]:
        insights.append("\n 污染物: 命中 " + ", ".join(dims["pollutant"]["matched"][:5]))
    elif dims["pollutant"]["reason"].startswith("命中非目标"):
        insights.append("\n  注意: " + dims["pollutant"]["reason"] + "（非课题目标污染物）")

    relevant_sents = extract_relevant_sentences(user_topic, abstract, max_sentences=3)
    if relevant_sents:
        insights.append("\n 摘要中与您课题最相关的内容：")
        for i, sent in enumerate(relevant_sents, 1):
            if len(sent) > 200:
                sent = sent[:200] + "..."
            insights.append("   {}. {}".format(i, sent))

    if total >= 70:
        insights.append("\n 建议：该文献与您的课题高度相关，建议精读全文。")
    elif total >= 40:
        insights.append("\n 建议：该文献部分相关，建议浏览方法和结果部分。")
    else:
        insights.append("\n 建议：该文献关联较弱，可浏览参考文献列表发现更相关文献。")
    return "\n".join(insights)


def relevance_level(score):
    if score >= 75:
        return " 高度相关"
    elif score >= 45:
        return " 中度相关"
    elif score >= 20:
        return " 低度相关"
    else:
        return " 不太相关"
