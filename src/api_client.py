"""
API 客户端：PubMed E-utilities + Crossref REST API
"""

import time
import xml.etree.ElementTree as ET
from typing import List, Optional

import requests

from models import Paper

# ─── PubMed E-utilities ─────────────────────────────
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# ─── Crossref ───────────────────────────────────────
CROSSREF_WORKS = "https://api.crossref.org/works"

# 请求头（Crossref 要求提供联系邮箱以获得更好的服务 polite pool）
HEADERS = {
    "User-Agent": "LitSearchTool/1.0 (mailto:researcher@example.com)",
}

# 请求间隔（秒），避免触发限流
REQUEST_DELAY = 0.35


def search_pubmed(query: str, max_results: int = 30,
                  sort: str = "relevance",
                  min_year: Optional[int] = None,
                  max_year: Optional[int] = None,
                  verbose: bool = False) -> List[Paper]:
    """
    通过 PubMed E-utilities 检索文献。
    1) esearch 获取 PMID 列表
    2) efetch 获取详细信息 (XML)
    """
    papers: List[Paper] = []

    # ── Step 1: esearch ──
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": sort,       # "relevance" 或 "pub_date"
    }
    # 日期过滤
    if min_year:
        params["mindate"] = f"{min_year}/01/01"
        params["datetype"] = "pdat"
    if max_year:
        params["maxdate"] = f"{max_year}/12/31"
        params["datetype"] = "pdat"

    if verbose:
        print(f"  [PubMed] esearch: {query}")

    try:
        resp = requests.get(PUBMED_ESEARCH, params=params,
                            headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [PubMed] esearch 失败: {e}")
        return papers

    id_list = data.get("esearchresult", {}).get("idlist", [])
    total_count = data.get("esearchresult", {}).get("count", "0")

    if verbose:
        print(f"  [PubMed] 找到 {total_count} 条结果，获取前 {len(id_list)} 条")

    if not id_list:
        return papers

    # ── Step 2: efetch ──
    time.sleep(REQUEST_DELAY)

    fetch_params = {
        "db": "pubmed",
        "id": ",".join(id_list),
        "rettype": "xml",
        "retmode": "xml",
    }

    try:
        resp = requests.get(PUBMED_EFETCH, params=fetch_params,
                            headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [PubMed] efetch 失败: {e}")
        return papers

    # 解析 XML
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"  [PubMed] XML 解析失败: {e}")
        return papers

    for article in root.findall(".//PubmedArticle"):
        paper = _parse_pubmed_article(article)
        if paper:
            papers.append(paper)

    if verbose:
        print(f"  [PubMed] 成功解析 {len(papers)} 篇文献")

    return papers


def _parse_pubmed_article(article_elem) -> Optional[Paper]:
    """解析单篇 PubMed XML 文章"""
    try:
        medline = article_elem.find(".//MedlineCitation")
        article = medline.find(".//Article")
        if article is None:
            return None

        # PMID
        pmid_elem = medline.find("PMID")
        pmid = pmid_elem.text if pmid_elem is not None else ""

        # 标题
        title_elem = article.find(".//ArticleTitle")
        title = _get_text(title_elem)

        # 作者
        authors = []
        for author in article.findall(".//Author"):
            last = author.find("LastName")
            first = author.find("ForeName")
            if last is not None:
                name = last.text or ""
                if first is not None and first.text:
                    name += f" {first.text}"
                authors.append(name)
        authors_str = ", ".join(authors[:10])
        if len(authors) > 10:
            authors_str += " et al."

        # 期刊
        journal_elem = article.find(".//Journal/Title")
        journal = journal_elem.text if journal_elem is not None else ""
        if not journal:
            j_abbr = article.find(".//Journal/ISOAbbreviation")
            journal = j_abbr.text if j_abbr is not None else ""

        # 年份
        year = ""
        pub_date = article.find(".//Journal/JournalIssue/PubDate")
        if pub_date is not None:
            y_elem = pub_date.find("Year")
            if y_elem is not None:
                year = y_elem.text
            else:
                medline_date = pub_date.find("MedlineDate")
                if medline_date is not None and medline_date.text:
                    year = medline_date.text[:4]

        # DOI
        doi = ""
        for eid in article.findall(".//ELocationID"):
            if eid.get("EIdType") == "doi":
                doi = eid.text or ""
                break
        if not doi:
            pid = article_elem.find(".//PubmedData")
            if pid is not None:
                for aid in pid.findall(".//ArticleId"):
                    if aid.get("IdType") == "doi":
                        doi = aid.text or ""
                        break

        # 摘要
        abstract_parts = []
        for abs_text in article.findall(".//Abstract/AbstractText"):
            label = abs_text.get("Label", "")
            text = _get_text(abs_text)
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
        abstract = " ".join(abstract_parts)

        link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

        return Paper(
            title=title,
            authors=authors_str,
            journal=journal,
            year=year,
            doi=doi.strip(),
            pmid=pmid,
            link=link,
            abstract=abstract,
            source="PubMed",
        )
    except Exception:
        return None


def _get_text(elem) -> str:
    """递归获取 XML 元素的全部文本内容（含子元素）"""
    if elem is None:
        return ""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        parts.append(_get_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()


# ═══════════════════════════════════════════════════════
# Crossref API
# ═══════════════════════════════════════════════════════
def search_crossref(query: str, max_results: int = 30,
                    sort: str = "relevance",
                    min_year: Optional[int] = None,
                    max_year: Optional[int] = None,
                    verbose: bool = False) -> List[Paper]:
    """通过 Crossref API 检索文献"""
    papers: List[Paper] = []

    params = {
        "query": query,
        "rows": max_results,
        "select": "DOI,title,author,container-title,"
                  "published-print,published-online,"
                  "abstract,type,ISSN",
    }

    if sort == "pub_date":
        params["sort"] = "published"
        params["order"] = "desc"
    else:
        params["sort"] = "relevance"

    # 日期过滤
    filters = []
    if min_year:
        filters.append(f"from-pub-date:{min_year}")
    if max_year:
        filters.append(f"until-pub-date:{max_year}")
    # 只要期刊文章
    filters.append("type:journal-article")
    if filters:
        params["filter"] = ",".join(filters)

    if verbose:
        print(f"  [Crossref] 检索: {query}")

    try:
        resp = requests.get(CROSSREF_WORKS, params=params,
                            headers=HEADERS, timeout=25)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [Crossref] 检索失败: {e}")
        return papers

    items = data.get("message", {}).get("items", [])

    if verbose:
        total = data.get("message", {}).get("total-results", 0)
        print(f"  [Crossref] 找到 {total} 条结果，获取前 {len(items)} 条")

    for item in items:
        paper = _parse_crossref_item(item)
        if paper:
            papers.append(paper)

    if verbose:
        print(f"  [Crossref] 成功解析 {len(papers)} 篇文献")

    return papers


def _parse_crossref_item(item: dict) -> Optional[Paper]:
    """解析单条 Crossref 记录"""
    try:
        doi = item.get("DOI", "")
        if not doi:
            return None

        # 标题
        titles = item.get("title", [])
        title = titles[0] if titles else ""

        # 作者
        authors_list = item.get("author", [])
        author_names = []
        for a in authors_list[:10]:
            family = a.get("family", "")
            given = a.get("given", "")
            if family:
                name = f"{family} {given}".strip()
                author_names.append(name)
        authors = ", ".join(author_names)
        if len(authors_list) > 10:
            authors += " et al."

        # 期刊
        containers = item.get("container-title", [])
        journal = containers[0] if containers else ""

        # 年份
        year = ""
        for date_field in ["published-print", "published-online"]:
            date_parts = item.get(date_field, {}).get("date-parts", [[]])
            if date_parts and date_parts[0]:
                year = str(date_parts[0][0])
                break

        # 摘要（Crossref 有时返回带 JATS XML 标签的摘要）
        abstract = item.get("abstract", "")
        # 简单清理 XML 标签
        import re
        abstract = re.sub(r'<[^>]+>', '', abstract).strip()

        link = f"https://doi.org/{doi}"

        return Paper(
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            doi=doi,
            pmid="",
            link=link,
            abstract=abstract,
            source="Crossref",
        )
    except Exception:
        return None
