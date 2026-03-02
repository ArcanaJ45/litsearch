"""
文献结构打标 (Paper Tagger)

根据标题 + 摘要自动为文献打上结构化标签：
  - research_type:       研究类型（流行病学 / 动物实验 / 体外实验 / 综述 / 其他）
  - pollutant_category:  污染物类别（PFAS / 重金属 / 其他环境污染物 / 未知）
  - exposure_window:     暴露窗口（孕期 / 围产期 / 哺乳期 / 儿童期 / 成年期 / 未知）

标签存储为 Paper 对象的动态属性 _tag_* ，可在表格 / 导出中使用。
"""

from typing import List

from domain_vocab import (
    identify_pollutant_category,
    identify_exposure_window,
    identify_research_type,
)


def tag_paper(paper) -> dict:
    """
    为单篇文献打标, 返回标签字典, 同时存到 paper._tag_* 属性上。
    """
    text = f"{paper.title or ''} {paper.abstract or ''}"

    tags = {
        "research_type":      identify_research_type(text),
        "pollutant_category": identify_pollutant_category(text),
        "exposure_window":    identify_exposure_window(text),
    }

    paper._tag_research_type = tags["research_type"]
    paper._tag_pollutant_category = tags["pollutant_category"]
    paper._tag_exposure_window = tags["exposure_window"]

    return tags


def tag_papers(papers: list) -> list:
    """
    批量打标，返回 papers 列表（原地修改）。
    """
    for p in papers:
        tag_paper(p)
    return papers


def get_tag_summary(papers: list) -> dict:
    """
    统计结构标签分布，返回类似:
    {
        "research_type":      {"流行病学": 5, "动物实验": 3, ...},
        "pollutant_category": {"PFAS": 8, ...},
        "exposure_window":    {"孕期": 6, ...},
    }
    """
    summary = {
        "research_type": {},
        "pollutant_category": {},
        "exposure_window": {},
    }
    for p in papers:
        rt = getattr(p, '_tag_research_type', '未标注')
        pc = getattr(p, '_tag_pollutant_category', '未标注')
        ew = getattr(p, '_tag_exposure_window', '未标注')
        summary["research_type"][rt] = summary["research_type"].get(rt, 0) + 1
        summary["pollutant_category"][pc] = summary["pollutant_category"].get(pc, 0) + 1
        summary["exposure_window"][ew] = summary["exposure_window"].get(ew, 0) + 1
    return summary
