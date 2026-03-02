"""
结果导出：CSV 文件输出
"""

import csv
import os
from typing import List

from models import Paper


def export_csv(papers: List[Paper], filepath: str,
               include_abstract: bool = False) -> str:
    """
    将文献列表导出为 CSV 文件。
    返回实际保存的文件路径。
    """
    # 确保目录存在
    dirpath = os.path.dirname(filepath)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    fieldnames = [
        "序号", "标题", "作者", "期刊", "年份",
        "影响因子", "相关度",
        "DOI", "DOI验证", "PMID", "链接", "来源",
    ]
    if include_abstract:
        fieldnames.append("摘要")

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, p in enumerate(papers, 1):
            if_str = f"{p.impact_factor:.3f}" if p.impact_factor else "N/A"
            row = {
                "序号": i,
                "标题": p.title,
                "作者": p.authors,
                "期刊": p.journal,
                "年份": p.year,
                "影响因子": if_str,
                "相关度": f"{p.relevance_score}%",
                "DOI": p.doi,
                "DOI验证": "通过" if p.doi_verified else "未通过",
                "PMID": p.pmid,
                "链接": p.display_link,
                "来源": p.source,
            }
            if include_abstract:
                row["摘要"] = p.abstract
            writer.writerow(row)

    return os.path.abspath(filepath)


def export_txt(papers: List[Paper], filepath: str) -> str:
    """导出为纯文本格式（方便粘贴引用）"""
    dirpath = os.path.dirname(filepath)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        for i, p in enumerate(papers, 1):
            verified = "✓" if p.doi_verified else "✗"
            if_str = f"{p.impact_factor:.3f}" if p.impact_factor else "N/A"
            f.write(f"[{i}] {p.title}\n")
            f.write(f"    {p.authors}\n")
            f.write(f"    {p.journal}, {p.year}  |  IF: {if_str}\n")
            f.write(f"    DOI: {p.doi} [验证: {verified}]\n")
            f.write(f"    相关度: {p.relevance_score}%\n")
            if p.pmid:
                f.write(f"    PMID: {p.pmid}\n")
            f.write(f"    {p.display_link}\n")
            f.write("\n")

    return os.path.abspath(filepath)
