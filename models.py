"""
数据模型：文献条目
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List


@dataclass
class Paper:
    """单篇文献记录"""
    title: str = ""
    authors: str = ""
    journal: str = ""
    year: str = ""
    doi: str = ""
    pmid: str = ""
    link: str = ""
    abstract: str = ""
    source: str = ""          # "PubMed" / "Crossref" / "PubMed+Crossref"
    doi_verified: bool = False
    # v1.1 新增
    impact_factor: Optional[float] = None    # 期刊影响因子 (2yr_mean_citedness)
    relevance_score: float = 0.0             # 与用户课题的相关度 (0-100)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def display_link(self) -> str:
        if self.pmid:
            return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"
        if self.doi:
            return f"https://doi.org/{self.doi}"
        return self.link or ""

    def merge(self, other: "Paper") -> "Paper":
        """合并两个来源的同一篇文献，优先保留更完整的字段"""
        merged = Paper(
            title=self.title or other.title,
            authors=self.authors or other.authors,
            journal=self.journal or other.journal,
            year=self.year or other.year,
            doi=self.doi or other.doi,
            pmid=self.pmid or other.pmid,
            link=self.link or other.link,
            abstract=self.abstract or other.abstract,
            source=f"{self.source}+{other.source}",
            doi_verified=self.doi_verified or other.doi_verified,
            impact_factor=self.impact_factor or other.impact_factor,
            relevance_score=max(self.relevance_score, other.relevance_score),
        )
        return merged

    def short_str(self, index: int = 0) -> str:
        """终端显示用的简短格式"""
        verified = "✓" if self.doi_verified else "✗"
        if_str = f"{self.impact_factor:.3f}" if self.impact_factor else "N/A"
        lines = [
            f"  [{index}] {self.title}",
            f"      作者: {self.authors[:80]}{'...' if len(self.authors) > 80 else ''}",
            f"      期刊: {self.journal}  |  年份: {self.year}  |  IF: {if_str}",
            f"      DOI: {self.doi}  [验证: {verified}]",
            f"      相关度: {self.relevance_score}%",
        ]
        if self.pmid:
            lines.append(f"      PMID: {self.pmid}")
        lines.append(f"      来源: {self.source}  |  链接: {self.display_link}")
        return "\n".join(lines)
