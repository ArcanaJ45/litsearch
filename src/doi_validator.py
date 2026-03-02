"""
DOI 验证模块：格式校验 + 在线验证
"""

import re
import time
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from models import Paper

# DOI 正则：10.xxxx/xxxx 格式
DOI_PATTERN = re.compile(r'^10\.\d{4,9}/[^\s]+$')

# 验证用的请求头
VERIFY_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "LitSearchTool/1.0",
}


def is_valid_doi_format(doi: str) -> bool:
    """检查 DOI 格式是否合法"""
    if not doi:
        return False
    doi = doi.strip()
    return bool(DOI_PATTERN.match(doi))


def verify_doi_online(doi: str, timeout: float = 8) -> bool:
    """
    通过 doi.org HEAD 请求验证 DOI 是否可解析。
    返回 True 表示 DOI 存在且可解析。
    """
    if not is_valid_doi_format(doi):
        return False

    url = f"https://doi.org/{doi}"
    try:
        resp = requests.head(url, headers=VERIFY_HEADERS,
                             allow_redirects=True, timeout=timeout)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def verify_doi_crossref(doi: str, timeout: float = 8) -> bool:
    """
    通过 Crossref API 验证 DOI。
    比 doi.org HEAD 请求更可靠。
    """
    if not is_valid_doi_format(doi):
        return False

    url = f"https://api.crossref.org/works/{doi}"
    try:
        resp = requests.head(url, headers=VERIFY_HEADERS, timeout=timeout)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def validate_papers(papers: List[Paper],
                    method: str = "crossref",
                    max_workers: int = 5,
                    verbose: bool = False) -> List[Paper]:
    """
    批量验证文献 DOI。
    method: "format" (仅格式) / "crossref" (Crossref API) / "doi_org" (doi.org)
    """
    if verbose:
        print(f"\n  正在验证 {len(papers)} 篇文献的 DOI ...")

    if method == "format":
        # 仅格式校验，速度最快
        for p in papers:
            p.doi_verified = is_valid_doi_format(p.doi)
        verified_count = sum(1 for p in papers if p.doi_verified)
        if verbose:
            print(f"  格式验证完成: {verified_count}/{len(papers)} 通过")
        return papers

    # 在线验证（使用线程池并发）
    verify_fn = verify_doi_crossref if method == "crossref" else verify_doi_online

    def _verify_one(paper: Paper) -> Paper:
        if not paper.doi:
            paper.doi_verified = False
            return paper
        if not is_valid_doi_format(paper.doi):
            paper.doi_verified = False
            return paper
        paper.doi_verified = verify_fn(paper.doi)
        return paper

    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_verify_one, p): p for p in papers}
        for future in as_completed(futures):
            done += 1
            if verbose and done % 10 == 0:
                print(f"  已验证 {done}/{len(papers)} ...")

    verified_count = sum(1 for p in papers if p.doi_verified)
    if verbose:
        print(f"  DOI 验证完成: {verified_count}/{len(papers)} 通过")

    return papers
