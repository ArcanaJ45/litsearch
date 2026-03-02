"""
期刊影响因子模块：通过 OpenAlex API 获取期刊影响力指标

OpenAlex 是免费开放的学术数据库，提供期刊级别的引用统计：
  - summary_stats.2yr_mean_citedness：等效于 2 年影响因子 (IF)
  - cited_by_count：总被引次数
  - works_count：总发文量

API 文档：https://docs.openalex.org/api-entities/sources
"""

import time
import re
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from models import Paper

# ─── OpenAlex API ────────────────────────────────────
OPENALEX_SOURCES = "https://api.openalex.org/sources"

HEADERS = {
    "User-Agent": "LitSearchTool/1.0 (mailto:arcbj045@gmail.com)",
    "Accept": "application/json",
}

# 请求间隔，避免触发限流（OpenAlex 免费层 10 req/s）
REQUEST_DELAY = 0.12

# 内存缓存：期刊名 → IF 值
_if_cache: Dict[str, Optional[float]] = {}


def get_journal_if(journal_name: str, issn: str = "",
                   timeout: float = 10) -> Optional[float]:
    """
    获取期刊的影响因子（2 年平均被引次数，等效 JCR IF）。

    优先使用 ISSN 查询（更精确），否则按期刊名搜索。
    返回 None 表示未查到。
    """
    if not journal_name and not issn:
        return None

    # 缓存命中
    cache_key = (issn or journal_name).lower().strip()
    if cache_key in _if_cache:
        return _if_cache[cache_key]

    impact_factor = None

    try:
        if issn:
            # 按 ISSN 精确查询
            impact_factor = _query_by_issn(issn, timeout)

        if impact_factor is None and journal_name:
            # 按期刊名搜索
            impact_factor = _query_by_name(journal_name, timeout)

    except Exception:
        pass

    # 写入缓存
    _if_cache[cache_key] = impact_factor
    return impact_factor


def _query_by_issn(issn: str, timeout: float) -> Optional[float]:
    """通过 ISSN 查询影响因子"""
    # 清理 ISSN 格式
    issn = issn.strip().replace(" ", "")
    if not issn:
        return None

    url = f"{OPENALEX_SOURCES}/issn:{issn}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            return _extract_if(data)
    except Exception:
        pass
    return None


def _query_by_name(journal_name: str, timeout: float) -> Optional[float]:
    """通过期刊名称搜索影响因子"""
    # 清理期刊名
    name = journal_name.strip()
    if not name or len(name) < 3:
        return None

    params = {
        "search": name,
        "per_page": 3,
        "select": "display_name,issn_l,summary_stats,cited_by_count,works_count",
    }

    try:
        resp = requests.get(OPENALEX_SOURCES, params=params,
                            headers=HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return None
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return None

        # 尝试精确匹配期刊名
        name_lower = name.lower()
        for r in results:
            r_name = (r.get("display_name") or "").lower()
            if r_name == name_lower or name_lower in r_name:
                if_val = _extract_if(r)
                if if_val is not None:
                    return if_val

        # 如果没有精确匹配，取第一个结果
        return _extract_if(results[0])

    except Exception:
        return None


def _extract_if(source_data: dict) -> Optional[float]:
    """从 OpenAlex source 数据中提取影响因子"""
    stats = source_data.get("summary_stats", {})
    if not stats:
        return None

    # 2yr_mean_citedness 等效于 2 年影响因子
    if_val = stats.get("2yr_mean_citedness")
    if if_val is not None and if_val > 0:
        return round(if_val, 3)

    return None


def format_if(impact_factor: Optional[float]) -> str:
    """格式化影响因子显示"""
    if impact_factor is None:
        return "N/A"
    return f"{impact_factor:.3f}"


def if_level(impact_factor: Optional[float]) -> str:
    """
    根据影响因子给出等级评价
    """
    if impact_factor is None:
        return ""
    if impact_factor >= 20:
        return "🏆 顶刊"
    elif impact_factor >= 10:
        return "⭐ 高影响力"
    elif impact_factor >= 5:
        return "🔵 中高影响力"
    elif impact_factor >= 2:
        return "🟢 中等影响力"
    elif impact_factor >= 1:
        return "🟡 一般"
    else:
        return "⚪ 较低"


def fetch_impact_factors(papers: List[Paper],
                         max_workers: int = 4,
                         verbose: bool = False) -> List[Paper]:
    """
    批量获取文献列表中所有期刊的影响因子。
    使用线程池并发查询，并利用缓存避免重复请求。
    """
    # 先收集需要查询的期刊（去重）
    journals_to_query = set()
    for p in papers:
        if p.journal:
            cache_key = p.journal.lower().strip()
            if cache_key not in _if_cache:
                journals_to_query.add(p.journal)

    if verbose:
        print(f"  [IF] 需要查询 {len(journals_to_query)} 个期刊的影响因子")

    # 并发查询
    if journals_to_query:
        done = 0
        def _query_one(journal_name):
            nonlocal done
            result = get_journal_if(journal_name)
            time.sleep(REQUEST_DELAY)
            done += 1
            return journal_name, result

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_query_one, j) for j in journals_to_query]
            for future in as_completed(futures):
                try:
                    journal_name, if_val = future.result()
                    if verbose and if_val is not None:
                        print(f"  [IF] {journal_name}: {if_val}")
                except Exception:
                    pass

    # 将影响因子赋值到每篇文献
    for p in papers:
        if p.journal:
            cache_key = p.journal.lower().strip()
            p.impact_factor = _if_cache.get(cache_key)

    if verbose:
        found = sum(1 for p in papers if p.impact_factor is not None)
        print(f"  [IF] 已获取 {found}/{len(papers)} 篇文献的影响因子")

    return papers
