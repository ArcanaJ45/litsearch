"""
API 客户端：PubMed E-utilities + Crossref REST API + Semantic Scholar + OpenAlex
"""

import re
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

# ─── Semantic Scholar ───────────────────────────────
S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"

# ─── OpenAlex ───────────────────────────────────────
OPENALEX_WORKS = "https://api.openalex.org/works"

# 请求头
HEADERS = {
    "User-Agent": "LitSearchTool/1.2 (mailto:researcher@example.com)",
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


# ═══════════════════════════════════════════════════════
# Semantic Scholar API
# ═══════════════════════════════════════════════════════
def search_semantic_scholar(query: str, max_results: int = 30,
                            sort: str = "relevance",
                            min_year: Optional[int] = None,
                            max_year: Optional[int] = None,
                            verbose: bool = False) -> List[Paper]:
    """
    通过 Semantic Scholar Graph API 检索文献。
    免费，无需 API Key，覆盖 2 亿+ 论文（CS/工程/生物医学/交叉学科）。
    速率限制：100 次/5 分钟（无 API Key）。
    """
    papers: List[Paper] = []

    fields = ("title,authors,year,externalIds,abstract,"
              "venue,publicationTypes,citationCount")
    params = {
        "query": query,
        "limit": min(max_results, 100),  # S2 API 单次最多 100
        "fields": fields,
    }

    # 年份过滤
    if min_year and max_year:
        params["year"] = f"{min_year}-{max_year}"
    elif min_year:
        params["year"] = f"{min_year}-"
    elif max_year:
        params["year"] = f"-{max_year}"

    if verbose:
        print(f"  [Semantic Scholar] 检索: {query}")

    try:
        time.sleep(1.0)  # S2 免费版速率较严格，多等一下
        resp = requests.get(S2_SEARCH, params=params,
                            headers=HEADERS, timeout=20)
        # 429 重试一次
        if resp.status_code == 429:
            if verbose:
                print("  [Semantic Scholar] 速率限制，等待 3 秒后重试...")
            time.sleep(3)
            resp = requests.get(S2_SEARCH, params=params,
                                headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        if verbose:
            print(f"  [Semantic Scholar] 检索失败: {e}")
        return papers

    items = data.get("data", [])
    total = data.get("total", 0)

    if verbose:
        print(f"  [Semantic Scholar] 找到 {total} 条结果，获取 {len(items)} 条")

    for item in items:
        paper = _parse_s2_item(item)
        if paper:
            papers.append(paper)

    if verbose:
        print(f"  [Semantic Scholar] 成功解析 {len(papers)} 篇文献")

    return papers


def _parse_s2_item(item: dict) -> Optional[Paper]:
    """解析单条 Semantic Scholar 记录"""
    try:
        title = item.get("title", "")
        if not title:
            return None

        # 作者
        authors_list = item.get("authors", [])
        author_names = [a.get("name", "") for a in authors_list[:10] if a.get("name")]
        authors = ", ".join(author_names)
        if len(authors_list) > 10:
            authors += " et al."

        # 年份
        year = str(item.get("year", "")) if item.get("year") else ""

        # DOI
        ext_ids = item.get("externalIds", {}) or {}
        doi = ext_ids.get("DOI", "") or ""
        pmid = ext_ids.get("PubMed", "") or ""

        # 期刊
        journal = item.get("venue", "") or ""

        # 摘要
        abstract = item.get("abstract", "") or ""

        # 链接
        if doi:
            link = f"https://doi.org/{doi}"
        elif pmid:
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        else:
            s2_id = item.get("paperId", "")
            link = f"https://www.semanticscholar.org/paper/{s2_id}" if s2_id else ""

        return Paper(
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            doi=doi,
            pmid=str(pmid),
            link=link,
            abstract=abstract,
            source="SemanticScholar",
        )
    except Exception:
        return None


# ═══════════════════════════════════════════════════════
# OpenAlex API (搜索)
# ═══════════════════════════════════════════════════════
def search_openalex(query: str, max_results: int = 30,
                    sort: str = "relevance",
                    min_year: Optional[int] = None,
                    max_year: Optional[int] = None,
                    verbose: bool = False) -> List[Paper]:
    """
    通过 OpenAlex API 检索文献。
    免费，无需 API Key，覆盖 2.5 亿+ 学术作品（全学科最全面的开放数据源）。
    包含引用数据、开放获取信息、概念标签等。
    """
    papers: List[Paper] = []

    params = {
        "search": query,
        "per_page": min(max_results, 200),    # OpenAlex 单页最多 200
        "select": ("id,doi,title,authorships,publication_year,"
                   "primary_location,abstract_inverted_index,type,"
                   "cited_by_count,open_access"),
    }

    # 排序
    if sort == "pub_date":
        params["sort"] = "publication_year:desc"
    else:
        params["sort"] = "relevance_score:desc"

    # 过滤
    filters = []
    if min_year:
        filters.append(f"from_publication_date:{min_year}-01-01")
    if max_year:
        filters.append(f"to_publication_date:{max_year}-12-31")
    # 只要期刊文章
    filters.append("type:article")
    if filters:
        params["filter"] = ",".join(filters)

    if verbose:
        print(f"  [OpenAlex] 检索: {query}")

    try:
        time.sleep(REQUEST_DELAY)
        resp = requests.get(OPENALEX_WORKS, params=params,
                            headers={**HEADERS, "Accept": "application/json"},
                            timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        if verbose:
            print(f"  [OpenAlex] 检索失败: {e}")
        return papers

    results = data.get("results", [])
    total = data.get("meta", {}).get("count", 0)

    if verbose:
        print(f"  [OpenAlex] 找到 {total} 条结果，获取 {len(results)} 条")

    for item in results:
        paper = _parse_openalex_item(item)
        if paper:
            papers.append(paper)

    if verbose:
        print(f"  [OpenAlex] 成功解析 {len(papers)} 篇文献")

    return papers


def _parse_openalex_item(item: dict) -> Optional[Paper]:
    """解析单条 OpenAlex 记录"""
    try:
        title = item.get("title", "") or ""
        if not title:
            return None

        # DOI
        doi_url = item.get("doi", "") or ""
        doi = doi_url.replace("https://doi.org/", "") if doi_url else ""

        # 作者
        authorships = item.get("authorships", [])
        author_names = []
        for a in authorships[:10]:
            name = a.get("author", {}).get("display_name", "")
            if name:
                author_names.append(name)
        authors = ", ".join(author_names)
        if len(authorships) > 10:
            authors += " et al."

        # 年份
        year = str(item.get("publication_year", "")) if item.get("publication_year") else ""

        # 期刊
        journal = ""
        primary = item.get("primary_location", {}) or {}
        source_info = primary.get("source", {}) or {}
        journal = source_info.get("display_name", "") or ""

        # 摘要（OpenAlex 使用 inverted index 格式）
        abstract = _reconstruct_abstract(item.get("abstract_inverted_index"))

        # 链接
        link = f"https://doi.org/{doi}" if doi else ""

        return Paper(
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            doi=doi,
            pmid="",
            link=link,
            abstract=abstract,
            source="OpenAlex",
        )
    except Exception:
        return None


def _reconstruct_abstract(inverted_index: Optional[dict]) -> str:
    """
    从 OpenAlex 的 abstract_inverted_index 还原摘要文本。
    格式: {"word1": [0, 5], "word2": [1], ...} → 按位置重建句子
    """
    if not inverted_index:
        return ""
    try:
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort(key=lambda x: x[0])
        return " ".join(w for _, w in word_positions)
    except Exception:
        return ""
