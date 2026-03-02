#!/usr/bin/env python3
"""
LitSearch - 文献检索工具 (CLI)
用于环境毒理学/流行病学研究的 PubMed + Crossref 文献检索

使用方式:
    python main.py "PFAS neurotoxicity pregnancy"
    python main.py "孕期暴露PFAS对子代神经发育影响"
    python main.py "heavy metals oxidative stress" -n 30 --csv results.csv
"""

import argparse
import sys
import os
import time
from typing import List

# 将当前目录加入 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Paper
from query_builder import build_query, describe_query
from api_client import search_pubmed, search_crossref
from doi_validator import validate_papers
from exporter import export_csv, export_txt


def merge_results(pubmed_papers: List[Paper],
                  crossref_papers: List[Paper]) -> List[Paper]:
    """
    按 DOI 去重合并两个来源的结果。
    有 DOI 的按 DOI 去重；无 DOI 的按标题去重。
    """
    merged = {}

    # 先加入 PubMed（通常信息更完整）
    for p in pubmed_papers:
        key = p.doi.lower().strip() if p.doi else f"title:{p.title.lower().strip()}"
        if key and key in merged:
            merged[key] = merged[key].merge(p)
        else:
            merged[key] = p

    # 再合并 Crossref
    for p in crossref_papers:
        key = p.doi.lower().strip() if p.doi else f"title:{p.title.lower().strip()}"
        if key and key in merged:
            merged[key] = merged[key].merge(p)
        else:
            merged[key] = p

    return list(merged.values())


def sort_papers(papers: List[Paper], sort_by: str = "year") -> List[Paper]:
    """排序文献列表"""
    if sort_by == "year":
        return sorted(papers, key=lambda p: p.year or "0000", reverse=True)
    # relevance: 保持 API 返回的原始顺序
    return papers


def filter_no_doi(papers: List[Paper], keep_no_doi: bool = False) -> List[Paper]:
    """过滤无 DOI 的文献"""
    if keep_no_doi:
        return papers
    return [p for p in papers if p.doi]


def print_results(papers: List[Paper], max_display: int = 20):
    """终端打印结果"""
    display = papers[:max_display]
    print(f"\n{'=' * 72}")
    print(f"  检索结果（显示前 {len(display)} / 共 {len(papers)} 条）")
    print(f"{'=' * 72}")

    for i, p in enumerate(display, 1):
        print()
        print(p.short_str(i))

    print(f"\n{'=' * 72}")

    # 统计
    verified = sum(1 for p in papers if p.doi_verified)
    with_doi = sum(1 for p in papers if p.doi)
    sources = {}
    for p in papers:
        sources[p.source] = sources.get(p.source, 0) + 1

    print(f"  总计: {len(papers)} 篇  |  有 DOI: {with_doi}  |  DOI 验证通过: {verified}")
    src_str = "  |  ".join(f"{k}: {v}" for k, v in sources.items())
    print(f"  来源: {src_str}")
    print(f"{'=' * 72}")


def main():
    parser = argparse.ArgumentParser(
        description="LitSearch - PubMed + Crossref 文献检索工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python main.py "PFAS neurotoxicity pregnancy"
  python main.py "孕期暴露PFAS对子代神经发育影响"
  python main.py "heavy metals oxidative stress children" -n 30
  python main.py "PFAS exposure birth weight" --csv results.csv --sort year
  python main.py "bisphenol A endocrine disruption" --source pubmed --no-verify
        """)

    parser.add_argument("query", type=str,
                        help="检索关键词或自然语言描述")
    parser.add_argument("-n", "--num", type=int, default=20,
                        help="返回结果数量 (默认: 20)")
    parser.add_argument("--max-fetch", type=int, default=40,
                        help="每个数据源最大获取数量 (默认: 40)")
    parser.add_argument("--source", type=str, default="both",
                        choices=["both", "pubmed", "crossref"],
                        help="检索来源 (默认: both)")
    parser.add_argument("--sort", type=str, default="year",
                        choices=["year", "relevance"],
                        help="排序方式 (默认: year)")
    parser.add_argument("--csv", type=str, default=None,
                        help="导出 CSV 文件路径")
    parser.add_argument("--txt", type=str, default=None,
                        help="导出 TXT 文件路径")
    parser.add_argument("--abstract", action="store_true",
                        help="CSV 中包含摘要")
    parser.add_argument("--keep-no-doi", action="store_true",
                        help="保留无 DOI 的文献 (默认过滤掉)")
    parser.add_argument("--no-verify", action="store_true",
                        help="跳过 DOI 在线验证 (仅做格式校验)")
    parser.add_argument("--min-year", type=int, default=None,
                        help="最早年份过滤 (如: 2015)")
    parser.add_argument("--max-year", type=int, default=None,
                        help="最晚年份过滤 (如: 2026)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="显示详细过程信息")

    args = parser.parse_args()

    # ── 构建检索式 ──
    print(f"\n{'─' * 60}")
    print("  LitSearch - 文献检索工具")
    print(f"{'─' * 60}")

    pubmed_query, crossref_query = build_query(args.query)
    print(describe_query(args.query, pubmed_query, crossref_query))
    print(f"  结果数量: {args.num}  |  排序: {args.sort}")
    if args.min_year or args.max_year:
        yr_range = f"{args.min_year or '...'} ~ {args.max_year or '...'}"
        print(f"  年份范围: {yr_range}")
    print(f"{'─' * 60}")

    # ── 检索 ──
    print("\n  正在检索文献 ...")
    t0 = time.time()

    pubmed_papers = []
    crossref_papers = []

    if args.source in ("both", "pubmed"):
        try:
            pubmed_papers = search_pubmed(
                pubmed_query,
                max_results=args.max_fetch,
                sort=args.sort,
                min_year=args.min_year,
                max_year=args.max_year,
                verbose=args.verbose)
        except Exception as e:
            print(f"  [PubMed] 检索出错: {e}")

    if args.source in ("both", "crossref"):
        try:
            crossref_papers = search_crossref(
                crossref_query,
                max_results=args.max_fetch,
                sort=args.sort,
                min_year=args.min_year,
                max_year=args.max_year,
                verbose=args.verbose)
        except Exception as e:
            print(f"  [Crossref] 检索出错: {e}")

    elapsed_search = time.time() - t0
    print(f"  检索完成 ({elapsed_search:.1f}s)"
          f"  PubMed: {len(pubmed_papers)}  |  Crossref: {len(crossref_papers)}")

    # ── 合并去重 ──
    papers = merge_results(pubmed_papers, crossref_papers)
    print(f"  合并去重后: {len(papers)} 篇")

    # ── 过滤无 DOI ──
    papers = filter_no_doi(papers, keep_no_doi=args.keep_no_doi)
    if not args.keep_no_doi:
        print(f"  过滤无 DOI 后: {len(papers)} 篇")

    if not papers:
        print("\n  未找到符合条件的文献。请尝试修改关键词。")
        return

    # ── DOI 验证 ──
    verify_method = "format" if args.no_verify else "crossref"
    papers = validate_papers(papers, method=verify_method,
                             verbose=args.verbose)

    # ── 排序 ──
    papers = sort_papers(papers, sort_by=args.sort)

    # ── 显示结果 ──
    print_results(papers, max_display=args.num)

    # ── 导出 ──
    if args.csv:
        path = export_csv(papers, args.csv, include_abstract=args.abstract)
        print(f"\n  ✓ 已导出 CSV: {path}")

    if args.txt:
        path = export_txt(papers, args.txt)
        print(f"\n  ✓ 已导出 TXT: {path}")

    if not args.csv and not args.txt:
        print(f"\n  提示: 使用 --csv results.csv 可导出为 CSV 文件")


if __name__ == "__main__":
    main()
