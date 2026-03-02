"""
LitSearch 文献检索 — Streamlit 网页版
部署到 Streamlit Community Cloud，任何浏览器即可使用
"""

import streamlit as st
import pandas as pd
import time
import os
import sys

# 确保能导入同目录的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Paper
from query_builder import build_query, describe_query, STUDY_TYPE_FILTERS
from api_client import search_pubmed, search_crossref
from doi_validator import validate_papers
from impact_factor import fetch_impact_factors, format_if, if_level
from relevance_analyzer import (compute_batch_relevance, generate_insights,
                                 relevance_level, extract_relevant_sentences)
from topic_guardrails import apply_topic_guardrails
from paper_tagger import tag_papers, get_tag_summary

# ─── 版本与联系信息 ─────────────────────────────────
APP_VERSION = "v1.2.0"
APP_NAME = "LitSearch 文献检索工具"
CONTACT_EMAIL = "arcbj045@gmail.com"
GITHUB_URL = "https://github.com/ArcanaJ045"

# ─── 页面配置 ──────────────────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME} {APP_VERSION}",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 自定义样式 ──────────────────────────────────────
st.markdown("""
<style>
    /* 顶部标题栏 */
    .main-header {
        background: linear-gradient(135deg, #1E3A5F 0%, #2563EB 100%);
        padding: 1rem 2rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        color: white;
    }
    .main-header h1 { color: white; margin: 0; font-size: 1.6rem; }
    .main-header p { color: #CBD5E1; margin: 0; font-size: 0.85rem; }

    /* 统计卡片 */
    .stat-card {
        background: white;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        border: 1px solid #E2E8F0;
        text-align: center;
    }
    .stat-card .value { font-size: 1.4rem; font-weight: bold; }
    .stat-card .label { font-size: 0.8rem; color: #64748B; }

    /* 文献卡片 */
    .paper-card {
        background: white;
        border-radius: 8px;
        padding: 1.2rem;
        border: 1px solid #E2E8F0;
        margin-bottom: 0.8rem;
        transition: box-shadow 0.2s;
    }
    .paper-card:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }

    /* 底部信息 */
    .footer {
        text-align: center;
        color: #64748B;
        font-size: 0.85rem;
        padding: 1.5rem 0;
        border-top: 1px solid #E2E8F0;
        margin-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════

def merge_papers(pubmed_papers, crossref_papers):
    """合并去重"""
    merged = {}
    for p in pubmed_papers:
        key = p.doi.lower().strip() if p.doi else f"t:{p.title.lower().strip()}"
        if key in merged:
            merged[key] = merged[key].merge(p)
        else:
            merged[key] = p
    for p in crossref_papers:
        key = p.doi.lower().strip() if p.doi else f"t:{p.title.lower().strip()}"
        if key in merged:
            merged[key] = merged[key].merge(p)
        else:
            merged[key] = p
    return list(merged.values())


def papers_to_dataframe(papers):
    """将文献列表转为 DataFrame"""
    rows = []
    for i, p in enumerate(papers, 1):
        if_str = f"{p.impact_factor:.2f}" if p.impact_factor else "N/A"
        rel_str = f"{p.relevance_score:.0f}%" if p.relevance_score > 0 else "-"
        rows.append({
            "#": i,
            "标题": p.title,
            "作者": p.authors[:80] + ("..." if len(p.authors) > 80 else ""),
            "期刊": p.journal,
            "年份": p.year,
            "IF": if_str,
            "相关度": rel_str,
            "研究类型": getattr(p, 'research_type', '') or '-',
            "污染物": getattr(p, 'pollutant_category', '') or '-',
            "暴露窗口": getattr(p, 'exposure_window', '') or '-',
            "DOI": p.doi,
            "DOI验证": "✓" if p.doi_verified else "✗",
            "来源": p.source,
        })
    return pd.DataFrame(rows)


def export_csv_bytes(papers, include_abstract=False):
    """生成 CSV 字节流供下载"""
    import csv
    import io
    output = io.StringIO()
    fieldnames = ["序号", "标题", "作者", "期刊", "年份",
                  "影响因子", "相关度",
                  "研究类型", "污染物类别", "暴露窗口",
                  "DOI", "DOI验证", "PMID", "链接", "来源"]
    if include_abstract:
        fieldnames.append("摘要")
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for i, p in enumerate(papers, 1):
        if_str = f"{p.impact_factor:.3f}" if p.impact_factor else "N/A"
        row = {
            "序号": i, "标题": p.title, "作者": p.authors,
            "期刊": p.journal, "年份": p.year,
            "影响因子": if_str, "相关度": f"{p.relevance_score}%",
            "研究类型": getattr(p, 'research_type', '') or '',
            "污染物类别": getattr(p, 'pollutant_category', '') or '',
            "暴露窗口": getattr(p, 'exposure_window', '') or '',
            "DOI": p.doi,
            "DOI验证": "通过" if p.doi_verified else "未通过",
            "PMID": p.pmid, "链接": p.display_link, "来源": p.source,
        }
        if include_abstract:
            row["摘要"] = p.abstract
        writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")


# ═══════════════════════════════════════════════════════
# 顶部标题
# ═══════════════════════════════════════════════════════
st.markdown(f"""
<div class="main-header">
    <h1>📚 {APP_NAME}</h1>
    <p>PubMed + Crossref 双源检索  |  {APP_VERSION}  |  Dev: ArcanaJ</p>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════
# 侧边栏 — 搜索参数
# ═══════════════════════════════════════════════════════
with st.sidebar:
    st.header("🔍 检索设置")

    # 检索关键词
    query_input = st.text_area(
        "关键词 / 自然语言描述",
        value="PFAS neurotoxicity pregnancy",
        height=100,
        help="输入英文关键词、中文描述或混合输入，系统会自动翻译和构建检索式",
    )

    st.divider()

    # 课题描述
    st.subheader("📝 我的课题")
    topic_input = st.text_area(
        "课题描述（用于相关性分析）",
        value="",
        height=80,
        help="输入您的课题描述，系统将自动计算每篇文献与课题的相关度",
        placeholder="例：孕期全氟化合物暴露对子代神经发育的影响",
    )
    if not topic_input.strip():
        st.caption("💡 留空则不计算相关度")

    st.divider()

    # 数据源
    st.subheader("⚙️ 参数")
    source = st.radio(
        "数据源",
        options=["both", "pubmed", "crossref"],
        format_func=lambda x: {"both": "PubMed + Crossref（推荐）",
                                "pubmed": "仅 PubMed",
                                "crossref": "仅 Crossref"}[x],
        index=0,
    )

    # 结果数量
    num_results = st.slider("结果数量", min_value=1, max_value=100,
                            value=30, step=5)

    # 排序
    sort_by = st.radio(
        "排序方式",
        options=["relevance", "pub_date"],
        format_func=lambda x: {"relevance": "🎯 相关性优先",
                                "pub_date": "📅 最新优先"}[x],
        horizontal=True,
    )

    # 年份范围
    col1, col2 = st.columns(2)
    with col1:
        min_year = st.number_input("起始年份", min_value=1900,
                                    max_value=2030, value=None,
                                    placeholder="不限")
    with col2:
        max_year = st.number_input("截止年份", min_value=1900,
                                    max_value=2030, value=None,
                                    placeholder="不限")

    st.divider()

    # 研究类型过滤
    st.subheader("🧪 研究类型过滤")
    study_filters = []
    for key, info in STUDY_TYPE_FILTERS.items():
        if st.checkbox(info["label"], key=f"filter_{key}"):
            study_filters.append(key)

    # 互斥处理
    if "animal_only" in study_filters and "human_only" in study_filters:
        st.warning("⚠️ 「仅动物实验」和「仅人群研究」互斥，已忽略「仅人群研究」")
        study_filters.remove("human_only")
    if "review_only" in study_filters and "exclude_review" in study_filters:
        st.warning("⚠️ 「仅综述」和「排除综述」互斥，已忽略「排除综述」")
        study_filters.remove("exclude_review")

    st.divider()

    # 高级选项
    st.subheader("🔧 高级选项")
    verify_doi = st.checkbox("在线验证 DOI（Crossref API）", value=False,
                              help="耗时较长，但更准确")
    keep_no_doi = st.checkbox("保留无 DOI 文献", value=False)
    fetch_if = st.checkbox("查询影响因子（OpenAlex）", value=True,
                            help="通过 OpenAlex API 获取期刊影响因子")
    include_abstract = st.checkbox("导出时包含摘要", value=False)

    st.divider()

    # 搜索按钮
    search_clicked = st.button("🔍  开始检索", type="primary",
                                use_container_width=True)


# ═══════════════════════════════════════════════════════
# 主内容区 — 搜索与结果
# ═══════════════════════════════════════════════════════

# 初始化 session state
if "papers" not in st.session_state:
    st.session_state.papers = []
if "search_done" not in st.session_state:
    st.session_state.search_done = False
if "query_info" not in st.session_state:
    st.session_state.query_info = ""

# 执行搜索
if search_clicked:
    query = query_input.strip()
    if not query:
        st.error("❌ 请先输入检索关键词")
    else:
        # 构建检索式
        pubmed_q, crossref_q = build_query(query,
                                            study_filters=study_filters or None)
        filter_labels = [STUDY_TYPE_FILTERS[k]["label"]
                         for k in study_filters
                         if k in STUDY_TYPE_FILTERS]
        filter_txt = f"  |  过滤: {', '.join(filter_labels)}" if filter_labels else ""
        st.session_state.query_info = (
            f"PubMed: `{pubmed_q}`  |  Crossref: `{crossref_q}`{filter_txt}")

        max_fetch = min(num_results + 20, 100)
        pubmed_papers = []
        crossref_papers = []

        progress = st.progress(0, text="正在检索...")

        # PubMed
        if source in ("both", "pubmed"):
            progress.progress(10, text="正在检索 PubMed ...")
            try:
                pubmed_papers = search_pubmed(
                    pubmed_q, max_results=max_fetch,
                    sort=sort_by,
                    min_year=int(min_year) if min_year else None,
                    max_year=int(max_year) if max_year else None)
            except Exception as e:
                st.warning(f"PubMed 检索出错: {e}")

        # Crossref
        if source in ("both", "crossref"):
            progress.progress(30, text="正在检索 Crossref ...")
            try:
                crossref_papers = search_crossref(
                    crossref_q, max_results=max_fetch,
                    sort=sort_by,
                    min_year=int(min_year) if min_year else None,
                    max_year=int(max_year) if max_year else None)
            except Exception as e:
                st.warning(f"Crossref 检索出错: {e}")

        # 合并去重
        progress.progress(50, text="正在合并去重...")
        papers = merge_papers(pubmed_papers, crossref_papers)

        # 过滤无 DOI
        if not keep_no_doi:
            papers = [p for p in papers if p.doi]

        # DOI 验证
        progress.progress(60, text="正在验证 DOI ...")
        if verify_doi:
            papers = validate_papers(papers, method="crossref")
        else:
            papers = validate_papers(papers, method="format")

        # 影响因子
        if fetch_if:
            progress.progress(70, text="正在查询影响因子（OpenAlex）...")
            papers = fetch_impact_factors(papers, max_workers=4)

        # 相关度
        user_topic = topic_input.strip()
        if user_topic:
            progress.progress(80, text="正在分析文献与课题的相关度...")
            papers = compute_batch_relevance(user_topic, papers)

        # 结构标签打标
        progress.progress(88, text="正在为文献打结构标签...")
        papers = tag_papers(papers)
        for p in papers:
            p.research_type = getattr(p, '_tag_research_type', '')
            p.pollutant_category = getattr(p, '_tag_pollutant_category', '')
            p.exposure_window = getattr(p, '_tag_exposure_window', '')

        # 课题防护栏
        if user_topic:
            progress.progress(93, text="正在应用课题防护栏...")
            papers = apply_topic_guardrails(papers, user_topic)

        # 排序
        if sort_by == "pub_date":
            papers.sort(key=lambda p: p.year or "0000", reverse=True)

        # 截取指定数量
        st.session_state.papers = papers[:num_results]
        st.session_state.all_papers = papers
        st.session_state.search_done = True
        st.session_state.user_topic = user_topic

        progress.progress(100, text="检索完成！")
        time.sleep(0.3)
        progress.empty()


# ═══════════════════════════════════════════════════════
# 结果展示
# ═══════════════════════════════════════════════════════

if st.session_state.search_done and st.session_state.papers:
    papers = st.session_state.papers
    all_papers = st.session_state.get("all_papers", papers)
    user_topic = st.session_state.get("user_topic", "")

    # 检索式信息
    if st.session_state.query_info:
        st.info(f"🔎 {st.session_state.query_info}")

    # ── 统计卡片 ──
    total = len(all_papers)
    pm_count = sum(1 for p in papers if "PubMed" in p.source)
    cr_count = sum(1 for p in papers if "Crossref" in p.source)
    doi_ok = sum(1 for p in papers if p.doi_verified)
    if_values = [p.impact_factor for p in papers if p.impact_factor]
    avg_if = sum(if_values) / len(if_values) if if_values else None
    rel_values = [p.relevance_score for p in papers if p.relevance_score > 0]
    avg_rel = sum(rel_values) / len(rel_values) if rel_values else None

    cols = st.columns(6)
    with cols[0]:
        st.metric("📊 总计", f"{total} 篇",
                  delta=f"显示 {len(papers)}" if len(papers) < total else None)
    with cols[1]:
        st.metric("🔬 PubMed", pm_count)
    with cols[2]:
        st.metric("🌐 Crossref", cr_count)
    with cols[3]:
        st.metric("✅ DOI验证", f"{doi_ok}/{len(papers)}")
    with cols[4]:
        st.metric("📈 IF均值", f"{avg_if:.2f}" if avg_if else "N/A")
    with cols[5]:
        st.metric("🎯 相关度", f"{avg_rel:.0f}%" if avg_rel else "N/A")

    # ── 导出按钮 ──
    col_export1, col_export2, _ = st.columns([1, 1, 4])
    with col_export1:
        csv_data = export_csv_bytes(papers, include_abstract)
        st.download_button(
            "📥 导出 CSV",
            data=csv_data,
            file_name=f"lit_search_{time.strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )
    with col_export2:
        # TXT 导出
        txt_lines = []
        for i, p in enumerate(papers, 1):
            verified = "✓" if p.doi_verified else "✗"
            if_str = f"{p.impact_factor:.3f}" if p.impact_factor else "N/A"
            txt_lines.append(f"[{i}] {p.title}")
            txt_lines.append(f"    {p.authors}")
            txt_lines.append(f"    {p.journal}, {p.year}  |  IF: {if_str}")
            txt_lines.append(f"    DOI: {p.doi} [验证: {verified}]")
            txt_lines.append(f"    相关度: {p.relevance_score}%")
            tags = []
            rt = getattr(p, 'research_type', '')
            pc = getattr(p, 'pollutant_category', '')
            ew = getattr(p, 'exposure_window', '')
            if rt: tags.append(f"研究类型: {rt}")
            if pc: tags.append(f"污染物: {pc}")
            if ew: tags.append(f"暴露窗口: {ew}")
            if tags:
                txt_lines.append(f"    {' | '.join(tags)}")
            if p.pmid:
                txt_lines.append(f"    PMID: {p.pmid}")
            txt_lines.append(f"    {p.display_link}")
            txt_lines.append("")
        st.download_button(
            "📄 导出 TXT",
            data="\n".join(txt_lines).encode("utf-8"),
            file_name=f"lit_search_{time.strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
        )

    st.divider()

    # ── 结果表格 ──
    df = papers_to_dataframe(papers)

    # 使用 tabs：表格视图 / 卡片视图
    tab_table, tab_cards = st.tabs(["📊 表格视图", "📋 卡片视图"])

    with tab_table:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "#": st.column_config.NumberColumn(width="small"),
                "标题": st.column_config.TextColumn(width="large"),
                "作者": st.column_config.TextColumn(width="medium"),
                "期刊": st.column_config.TextColumn(width="medium"),
                "年份": st.column_config.TextColumn(width="small"),
                "IF": st.column_config.TextColumn(width="small"),
                "相关度": st.column_config.TextColumn(width="small"),
                "研究类型": st.column_config.TextColumn(width="small"),
                "污染物": st.column_config.TextColumn(width="small"),
                "暴露窗口": st.column_config.TextColumn(width="small"),
                "DOI": st.column_config.TextColumn(width="medium"),
                "DOI验证": st.column_config.TextColumn(width="small"),
                "来源": st.column_config.TextColumn(width="small"),
            },
        )

    with tab_cards:
        for i, p in enumerate(papers):
            with st.expander(
                f"**{i+1}.** {p.title[:100]}{'...' if len(p.title) > 100 else ''}"
                f"  —  {p.journal}, {p.year}",
                expanded=False
            ):
                # 基本信息
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"**作者:** {p.authors}")
                    st.markdown(f"**期刊:** {p.journal}")
                    st.markdown(f"**年份:** {p.year}")
                    st.markdown(f"**来源:** {p.source}")
                with col_b:
                    if_str = format_if(p.impact_factor)
                    if_lvl = if_level(p.impact_factor)
                    st.markdown(f"**影响因子:** {if_str} {if_lvl}")

                    rel_str = f"{p.relevance_score:.1f}%"
                    rel_lvl = relevance_level(p.relevance_score)
                    st.markdown(f"**相关度:** {rel_str} {rel_lvl}")

                    verified_str = "✅ 通过" if p.doi_verified else "❌ 未通过"
                    st.markdown(f"**DOI验证:** {verified_str}")

                    # 结构标签
                    rt = getattr(p, 'research_type', '')
                    pc = getattr(p, 'pollutant_category', '')
                    ew = getattr(p, 'exposure_window', '')
                    if rt:
                        st.markdown(f"**研究类型:** {rt}")
                    if pc:
                        st.markdown(f"**污染物:** {pc}")
                    if ew:
                        st.markdown(f"**暴露窗口:** {ew}")

                    if p.doi:
                        st.markdown(f"**DOI:** [{p.doi}](https://doi.org/{p.doi})")
                    if p.pmid:
                        st.markdown(
                            f"**PMID:** [{p.pmid}]"
                            f"(https://pubmed.ncbi.nlm.nih.gov/{p.pmid}/)")

                # 摘要
                if p.abstract:
                    st.markdown("---")
                    st.markdown("**📄 摘要:**")
                    st.markdown(
                        f'<div style="background:#F8FAFC; padding:12px; '
                        f'border-radius:6px; font-size:0.9rem; '
                        f'line-height:1.6;">{p.abstract}</div>',
                        unsafe_allow_html=True)

                # 智能分析
                if user_topic and p.abstract:
                    st.markdown("---")
                    st.markdown("**📊 课题相关性分析:**")
                    insights = generate_insights(
                        user_topic, p.title, p.abstract,
                        p.relevance_score)
                    st.markdown(
                        f'<div style="background:#F0F9FF; padding:12px; '
                        f'border-radius:6px; font-size:0.9rem; '
                        f'line-height:1.6; white-space:pre-wrap;">'
                        f'{insights}</div>',
                        unsafe_allow_html=True)

                # 操作按钮
                btn_cols = st.columns(3)
                with btn_cols[0]:
                    if p.display_link:
                        st.link_button("🔗 打开链接", p.display_link)
                with btn_cols[1]:
                    if p.doi:
                        st.code(p.doi, language=None)
                with btn_cols[2]:
                    # 生成引用格式
                    citation = (f"{p.authors}. {p.title}. "
                                f"{p.journal}, {p.year}. "
                                f"DOI: {p.doi}")
                    st.code(citation, language=None)

elif st.session_state.search_done:
    st.warning("😔 未找到符合条件的文献，请调整关键词或搜索参数后重试")


# 如果还没有搜索，显示使用说明
if not st.session_state.search_done:
    st.markdown("""
    ### 👋 欢迎使用 LitSearch 文献检索工具

    **使用方法：**
    1. 在左侧 **检索设置** 中输入关键词（支持中英文）
    2. 可选：输入您的课题描述，系统将计算每篇文献的相关度
    3. 调整数据源、结果数量等参数
    4. 点击 **🔍 开始检索** 即可

    **功能亮点：**
    - 🔬 **双源检索** — 同时搜索 PubMed 和 Crossref，自动合并去重
    - 📈 **影响因子** — 通过 OpenAlex API 自动获取期刊影响因子
    - 🎯 **多维度相关性评分** — 6 维度规则评分（污染物/结局/暴露窗口/对象/机制/语义）
    - 🛡 **课题防护栏** — PFAS 课题自动降权非相关暴露物文献
    - 🏷 **结构标签** — 自动识别研究类型、污染物类别、暴露窗口
    - 📊 **智能摘选** — 自动提取与您课题最相关的句子，生成分析报告
    - 🌐 **跨平台** — 网页版，Mac / Windows / Linux / 手机直接使用
    - 📥 **导出** — 支持 CSV / TXT 格式导出

    **示例关键词：**
    - `PFAS neurotoxicity pregnancy`
    - `孕期重金属暴露 神经发育`
    - `microplastics reproductive toxicity mice`
    """)


# ─── 底部信息 ──────────────────────────────────────
st.markdown("---")
st.markdown(
    f'<div class="footer">'
    f'{APP_NAME} {APP_VERSION}  |  '
    f'Dev: <strong>ArcanaJ</strong>  |  '
    f'✉ <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>  |  '
    f'<a href="{GITHUB_URL}" target="_blank">GitHub</a>'
    f'</div>',
    unsafe_allow_html=True)
