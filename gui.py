"""
LitSearch GUI - 文献检索工具图形界面
基于 tkinter，调用现有的 api_client / doi_validator / query_builder 模块

v1.1.0 - 新增影响因子查询、课题相关性分析、智能内容摘选
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import sys
import time

# 确保能导入同目录的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Paper
from query_builder import build_query, describe_query, STUDY_TYPE_FILTERS
from api_client import search_pubmed, search_crossref
from doi_validator import validate_papers
from exporter import export_csv, export_txt
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

# ─── 颜色主题 ──────────────────────────────────────
COLORS = {
    "bg":          "#F0F4F8",
    "sidebar":     "#1E3A5F",
    "sidebar_txt": "#CBD5E1",
    "accent":      "#3B82F6",
    "accent_h":    "#2563EB",
    "success":     "#22C55E",
    "warning":     "#F59E0B",
    "danger":      "#EF4444",
    "card":        "#FFFFFF",
    "text":        "#1E293B",
    "text2":       "#64748B",
    "border":      "#E2E8F0",
    "input_bg":    "#F8FAFC",
    "verified":    "#DCFCE7",
    "unverified":  "#FEE2E2",
    "row_alt":     "#F8FAFC",
    "highlight":   "#EFF6FF",
}

FONT        = ("Microsoft YaHei UI", 10)
FONT_B      = ("Microsoft YaHei UI", 10, "bold")
FONT_TITLE  = ("Microsoft YaHei UI", 16, "bold")
FONT_SMALL  = ("Microsoft YaHei UI", 9)
FONT_MONO   = ("Consolas", 9)


class LitSearchGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("1320x820")
        self.root.minsize(800, 550)
        self.root.configure(bg=COLORS["bg"])

        self.papers: list[Paper] = []
        self.searching = False
        self._user_topic = ""

        self._build_ui()

        # 窗口大小改变时更新布局
        self.root.bind("<Configure>", self._on_window_resize)

    # ═══════════════════════════════════════════════════
    # UI 构建
    # ═══════════════════════════════════════════════════
    def _build_ui(self):
        # ── 顶部标题栏 ──
        header = tk.Frame(self.root, bg=COLORS["sidebar"], height=52)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=f"📚 {APP_NAME}",
                 bg=COLORS["sidebar"], fg="white",
                 font=("Microsoft YaHei UI", 15, "bold")).pack(side=tk.LEFT, padx=20)
        tk.Label(header, text=f"PubMed + Crossref  |  {APP_VERSION}",
                 bg=COLORS["sidebar"], fg=COLORS["sidebar_txt"],
                 font=FONT_SMALL).pack(side=tk.LEFT, padx=10)

        # 右侧开发者 & 联系信息
        contact_frame = tk.Frame(header, bg=COLORS["sidebar"])
        contact_frame.pack(side=tk.RIGHT, padx=15)
        tk.Label(contact_frame, text="Dev: ArcanaJ  |",
                 bg=COLORS["sidebar"], fg=COLORS["accent"],
                 font=("Microsoft YaHei UI", 10, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        contact_lbl = tk.Label(contact_frame,
                               text=f"✉ {CONTACT_EMAIL}",
                               bg=COLORS["sidebar"], fg=COLORS["sidebar_txt"],
                               font=("Microsoft YaHei UI", 10), cursor="hand2")
        contact_lbl.pack(side=tk.LEFT)
        contact_lbl.bind("<Button-1>",
                         lambda e: self._copy_to_clipboard(CONTACT_EMAIL))

        # ── 主体区域（可拖拽分割） ──
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL,
                                    bg=COLORS["border"], sashwidth=5,
                                    sashrelief=tk.RAISED)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # 左侧控制面板容器
        left_container = tk.Frame(self.paned, bg=COLORS["card"])
        self._build_control_panel(left_container)
        self.paned.add(left_container, minsize=280, width=340)

        # 右侧结果区容器
        right_container = tk.Frame(self.paned, bg=COLORS["bg"])
        self._build_results_panel(right_container)
        self.paned.add(right_container, minsize=400)

        # ── 底部状态栏 ──
        footer = tk.Frame(self.root, bg=COLORS["sidebar"], height=34)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        tk.Label(footer,
                 text=f"Developed by ArcanaJ  |  {APP_NAME} {APP_VERSION}",
                 bg=COLORS["sidebar"], fg=COLORS["accent"],
                 font=("Microsoft YaHei UI", 10, "bold")).pack(side=tk.LEFT, padx=15)
        tk.Label(footer,
                 text=f"✉ {CONTACT_EMAIL}  |  GitHub: {GITHUB_URL}",
                 bg=COLORS["sidebar"], fg=COLORS["sidebar_txt"],
                 font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=5)

        about_btn = tk.Label(footer, text="关于 / 更新日志",
                             bg=COLORS["sidebar"], fg=COLORS["accent"],
                             font=("Microsoft YaHei UI", 10, "underline"),
                             cursor="hand2")
        about_btn.pack(side=tk.RIGHT, padx=15)
        about_btn.bind("<Button-1>", lambda e: self._show_about())

    # ─── 左侧控制面板 ─────────────────────────────────
    def _build_control_panel(self, parent):
        panel = tk.Frame(parent, bg=COLORS["card"],
                         relief="flat", bd=0)
        panel.pack(fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)

        # 可滚动画布（当窗口较小时依然能看到所有选项）
        self._ctrl_canvas = tk.Canvas(panel, bg=COLORS["card"],
                                      highlightthickness=0)
        panel_scroll = ttk.Scrollbar(panel, orient=tk.VERTICAL,
                                     command=self._ctrl_canvas.yview)
        inner = tk.Frame(self._ctrl_canvas, bg=COLORS["card"],
                         padx=14, pady=12)

        inner.bind("<Configure>",
                   lambda e: self._ctrl_canvas.configure(
                       scrollregion=self._ctrl_canvas.bbox("all")))
        self._ctrl_inner_id = self._ctrl_canvas.create_window(
            (0, 0), window=inner, anchor="nw")
        self._ctrl_canvas.configure(yscrollcommand=panel_scroll.set)

        self._ctrl_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        panel_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 画布宽度自适应
        def _resize_inner(event):
            self._ctrl_canvas.itemconfig(self._ctrl_inner_id,
                                        width=event.width)
        self._ctrl_canvas.bind("<Configure>", _resize_inner)

        # 鼠标滚轮支持（仅当光标在控制面板上时）
        def _on_panel_enter(event):
            self._ctrl_canvas.bind_all("<MouseWheel>",
                            lambda e: self._ctrl_canvas.yview_scroll(
                                int(-1 * (e.delta / 120)), "units"))
        def _on_panel_leave(event):
            self._ctrl_canvas.unbind_all("<MouseWheel>")
        self._ctrl_canvas.bind("<Enter>", _on_panel_enter)
        self._ctrl_canvas.bind("<Leave>", _on_panel_leave)

        # ━━ 检索输入 ━━
        self._section_label(inner, "🔍 检索输入")

        tk.Label(inner, text="关键词 / 自然语言描述:",
                 bg=COLORS["card"], fg=COLORS["text"],
                 font=FONT, anchor="w").pack(fill=tk.X, pady=(5, 3))

        # 预览标签（点击弹出编辑对话框）
        self._query_value = "PFAS neurotoxicity pregnancy"
        self.query_preview = tk.Label(
            inner, text=self._query_value,
            bg=COLORS["input_bg"], fg=COLORS["text"], font=FONT,
            anchor="w", justify=tk.LEFT, wraplength=270,
            relief="solid", bd=1, padx=8, pady=8, cursor="hand2")
        self.query_preview.pack(fill=tk.X)
        self.query_preview.bind("<Button-1>",
                                lambda e: self._open_input_dialog(
                                    "检索输入", "请输入关键词或自然语言描述：",
                                    self._query_value, self._on_query_set))

        ttk.Separator(inner).pack(fill=tk.X, pady=12)

        # ━━ 我的课题描述（用于相关性分析）━━
        self._section_label(inner, "📝 我的课题")

        tk.Label(inner, text="点击输入课题描述（用于相关性分析）:",
                 bg=COLORS["card"], fg=COLORS["text"],
                 font=FONT_SMALL, anchor="w").pack(fill=tk.X, pady=(3, 2))

        self._topic_value = ""
        self.topic_preview = tk.Label(
            inner, text="（点击此处输入课题描述）",
            bg=COLORS["input_bg"], fg=COLORS["text2"], font=FONT,
            anchor="w", justify=tk.LEFT, wraplength=270,
            relief="solid", bd=1, padx=8, pady=8, cursor="hand2")
        self.topic_preview.pack(fill=tk.X)
        self.topic_preview.bind("<Button-1>",
                                lambda e: self._open_input_dialog(
                                    "课题描述", "请输入您的课题描述（用于计算文献相关度）：",
                                    self._topic_value, self._on_topic_set))

        tk.Label(inner, text="留空则不计算相关度",
                 bg=COLORS["card"], fg=COLORS["text2"],
                 font=("Microsoft YaHei UI", 8)).pack(anchor="w")

        ttk.Separator(inner).pack(fill=tk.X, pady=12)

        # ━━ 检索选项 ━━
        self._section_label(inner, "⚙ 检索选项")

        # 数据源
        tk.Label(inner, text="数据源:",
                 bg=COLORS["card"], fg=COLORS["text"],
                 font=FONT, anchor="w").pack(fill=tk.X, pady=(4, 2))
        self.source_var = tk.StringVar(value="both")
        for text, val in [("PubMed + Crossref", "both"),
                          ("仅 PubMed", "pubmed"),
                          ("仅 Crossref", "crossref")]:
            tk.Radiobutton(inner, text=text, variable=self.source_var,
                           value=val, bg=COLORS["card"], fg=COLORS["text"],
                           font=FONT_SMALL, activebackground=COLORS["card"],
                           selectcolor=COLORS["card"],
                           anchor="w").pack(fill=tk.X, padx=(20, 0))

        # 结果数量
        tk.Label(inner, text="结果数量:",
                 bg=COLORS["card"], fg=COLORS["text"],
                 font=FONT, anchor="w").pack(fill=tk.X, pady=(8, 2))

        num_quick_frame = tk.Frame(inner, bg=COLORS["card"])
        num_quick_frame.pack(fill=tk.X, padx=(20, 0), pady=2)
        self.num_var = tk.StringVar(value="20")
        for n in ["10", "20", "30", "50", "100"]:
            tk.Radiobutton(num_quick_frame, text=n, variable=self.num_var,
                           value=n, bg=COLORS["card"], fg=COLORS["text"],
                           font=FONT_SMALL, activebackground=COLORS["card"],
                           selectcolor=COLORS["card"]
                           ).pack(side=tk.LEFT, padx=2)

        # 自定义数量输入
        custom_num_frame = tk.Frame(inner, bg=COLORS["card"])
        custom_num_frame.pack(fill=tk.X, padx=(20, 0), pady=2)
        tk.Label(custom_num_frame, text="自定义:",
                 bg=COLORS["card"], fg=COLORS["text2"],
                 font=FONT_SMALL).pack(side=tk.LEFT)
        self.num_spinbox = tk.Spinbox(
            custom_num_frame, from_=1, to=100, width=5,
            font=FONT_SMALL, bg=COLORS["input_bg"],
            textvariable=self.num_var, command=self._on_num_spin)
        self.num_spinbox.pack(side=tk.LEFT, padx=5)
        tk.Label(custom_num_frame, text="(1-100)",
                 bg=COLORS["card"], fg=COLORS["text2"],
                 font=("Microsoft YaHei UI", 8)).pack(side=tk.LEFT)

        # 排序
        sort_frame = self._option_row(inner, "排序方式:")
        self.sort_var = tk.StringVar(value="year")
        ttk.Combobox(sort_frame, textvariable=self.sort_var,
                     values=["year", "relevance"],
                     state="readonly", width=12, font=FONT_SMALL).pack(side=tk.LEFT)

        # 年份范围
        yr_frame = self._option_row(inner, "年份范围:")
        self.min_year_var = tk.StringVar(value="")
        self.max_year_var = tk.StringVar(value="")
        tk.Entry(yr_frame, textvariable=self.min_year_var, width=6,
                 font=FONT_SMALL, bg=COLORS["input_bg"]).pack(side=tk.LEFT)
        tk.Label(yr_frame, text=" ~ ", bg=COLORS["card"],
                 font=FONT_SMALL).pack(side=tk.LEFT)
        tk.Entry(yr_frame, textvariable=self.max_year_var, width=6,
                 font=FONT_SMALL, bg=COLORS["input_bg"]).pack(side=tk.LEFT)

        ttk.Separator(inner).pack(fill=tk.X, pady=12)

        # ━━ 研究类型过滤 ━━
        self._section_label(inner, "🧬 研究类型")

        self.study_filter_vars: dict[str, tk.BooleanVar] = {}
        filter_items = [
            ("animal_only",    "仅动物实验（排除人群研究）"),
            ("human_only",     "仅人群研究（排除动物实验）"),
            ("exclude_review", "排除综述文献"),
            ("review_only",    "仅综述文献"),
        ]
        for fkey, flabel in filter_items:
            var = tk.BooleanVar(value=False)
            self.study_filter_vars[fkey] = var
            tk.Checkbutton(inner, text=flabel,
                           variable=var, bg=COLORS["card"],
                           fg=COLORS["text"], font=FONT_SMALL,
                           activebackground=COLORS["card"],
                           selectcolor=COLORS["card"]).pack(anchor="w", pady=1)

        # 互斥提示
        tk.Label(inner, text="提示: 动物/人群、综述/排除综述 互斥",
                 bg=COLORS["card"], fg=COLORS["text2"],
                 font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(0, 2))

        ttk.Separator(inner).pack(fill=tk.X, pady=12)

        # ━━ 过滤与验证 ━━
        self._section_label(inner, "🛡 过滤与验证")

        self.verify_var = tk.BooleanVar(value=False)
        tk.Checkbutton(inner, text="DOI 在线验证（较慢，通过 Crossref API）",
                       variable=self.verify_var, bg=COLORS["card"],
                       fg=COLORS["text"], font=FONT_SMALL,
                       activebackground=COLORS["card"],
                       selectcolor=COLORS["card"]).pack(anchor="w", pady=2)

        self.keep_no_doi_var = tk.BooleanVar(value=False)
        tk.Checkbutton(inner, text="保留无 DOI 的文献",
                       variable=self.keep_no_doi_var, bg=COLORS["card"],
                       fg=COLORS["text"], font=FONT_SMALL,
                       activebackground=COLORS["card"],
                       selectcolor=COLORS["card"]).pack(anchor="w", pady=2)

        self.abstract_var = tk.BooleanVar(value=True)
        tk.Checkbutton(inner, text="导出 CSV 时包含摘要",
                       variable=self.abstract_var, bg=COLORS["card"],
                       fg=COLORS["text"], font=FONT_SMALL,
                       activebackground=COLORS["card"],
                       selectcolor=COLORS["card"]).pack(anchor="w", pady=2)

        self.fetch_if_var = tk.BooleanVar(value=True)
        tk.Checkbutton(inner, text="查询期刊影响因子（OpenAlex API）",
                       variable=self.fetch_if_var, bg=COLORS["card"],
                       fg=COLORS["text"], font=FONT_SMALL,
                       activebackground=COLORS["card"],
                       selectcolor=COLORS["card"]).pack(anchor="w", pady=2)

        ttk.Separator(inner).pack(fill=tk.X, pady=12)

        # ━━ 操作按钮 ━━
        self.search_btn = tk.Button(
            inner, text="🔍  开始检索", bg=COLORS["accent"], fg="white",
            font=("Microsoft YaHei UI", 13, "bold"), bd=0,
            padx=20, pady=10, cursor="hand2", activebackground=COLORS["accent_h"],
            command=self._on_search)
        self.search_btn.pack(fill=tk.X, pady=(5, 8))

        btn_row = tk.Frame(inner, bg=COLORS["card"])
        btn_row.pack(fill=tk.X, pady=3)

        self.csv_btn = tk.Button(
            btn_row, text="📊 导出 CSV", bg=COLORS["success"], fg="white",
            font=FONT_B, bd=0, padx=12, pady=6, cursor="hand2",
            command=self._export_csv, state=tk.DISABLED)
        self.csv_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.txt_btn = tk.Button(
            btn_row, text="📄 导出 TXT", bg="#8B5CF6", fg="white",
            font=FONT_B, bd=0, padx=12, pady=6, cursor="hand2",
            command=self._export_txt, state=tk.DISABLED)
        self.txt_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        # ━━ 状态栏 ━━
        self.status_var = tk.StringVar(value="就绪")
        self.status_label = tk.Label(
            inner, textvariable=self.status_var, bg=COLORS["card"],
            fg=COLORS["text2"], font=FONT_SMALL, anchor="w")
        self.status_label.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        # 进度条
        self.progress = ttk.Progressbar(inner, mode="indeterminate", length=280)
        self.progress.pack(fill=tk.X, side=tk.BOTTOM, pady=(5, 0))

    # ─── 右侧结果区 ───────────────────────────────────
    def _build_results_panel(self, parent):
        panel = tk.Frame(parent, bg=COLORS["bg"])
        panel.pack(fill=tk.BOTH, expand=True, padx=(8, 8), pady=8)

        # 查询信息栏
        self.query_info_frame = tk.Frame(panel, bg=COLORS["highlight"],
                                         padx=12, pady=8)
        self.query_info_frame.pack(fill=tk.X, pady=(0, 8))
        self.query_info_var = tk.StringVar(value="输入关键词后点击「开始检索」")
        tk.Label(self.query_info_frame, textvariable=self.query_info_var,
                 bg=COLORS["highlight"], fg=COLORS["text"],
                 font=FONT_SMALL, anchor="w", justify=tk.LEFT).pack(fill=tk.X)

        # 统计栏
        stats_frame = tk.Frame(panel, bg=COLORS["card"], padx=10, pady=6)
        stats_frame.pack(fill=tk.X, pady=(0, 8))

        self.stat_labels = {}
        for key, text, color in [
            ("total",    "总计: 0",       COLORS["text"]),
            ("pubmed",   "PubMed: 0",     COLORS["accent"]),
            ("crossref", "Crossref: 0",   COLORS["success"]),
            ("doi_ok",   "DOI验证: 0/0",  "#8B5CF6"),
            ("avg_if",   "IF均值: N/A",   COLORS["warning"]),
            ("avg_rel",  "相关度: N/A",   COLORS["danger"]),
        ]:
            lbl = tk.Label(stats_frame, text=text, bg=COLORS["card"],
                           fg=color, font=FONT_B, padx=10)
            lbl.pack(side=tk.LEFT)
            self.stat_labels[key] = lbl

        # 结果表格
        tree_frame = tk.Frame(panel, bg=COLORS["card"], relief="solid", bd=1)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("idx", "title", "authors", "journal", "year",
                   "impact_factor", "relevance",
                   "research_type", "pollutant", "window",
                   "doi", "doi_ok", "source")
        self.tree = ttk.Treeview(tree_frame, columns=columns,
                                 show="headings", selectmode="browse")

        col_config = [
            ("idx",            "#",      40),
            ("title",          "标题",   240),
            ("authors",        "作者",   130),
            ("journal",        "期刊",   110),
            ("year",           "年份",   50),
            ("impact_factor",  "IF",     55),
            ("relevance",      "相关度", 55),
            ("research_type",  "研究类型", 70),
            ("pollutant",      "污染物",  65),
            ("window",         "暴露窗口", 65),
            ("doi",            "DOI",    140),
            ("doi_ok",         "DOI验证", 50),
            ("source",         "来源",   70),
        ]
        for col_id, heading, width in col_config:
            self.tree.heading(col_id, text=heading,
                              command=lambda c=col_id: self._sort_column(c))
            anchor = "center" if col_id in ("idx", "year", "doi_ok", "source") else "w"
            stretch = col_id in ("title", "authors", "journal", "doi")
            self.tree.column(col_id, width=width, anchor=anchor,
                             minwidth=35, stretch=stretch)

        # 滚动条
        vs = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hs = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side=tk.RIGHT, fill=tk.Y)
        hs.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 双击查看详情
        self.tree.bind("<Double-1>", self._on_paper_detail)
        # 右键菜单
        self.ctx_menu = tk.Menu(self.root, tearoff=0)
        self.ctx_menu.add_command(label="查看详情", command=self._view_selected)
        self.ctx_menu.add_command(label="复制 DOI", command=self._copy_doi)
        self.ctx_menu.add_command(label="在浏览器中打开", command=self._open_link)
        self.tree.bind("<Button-3>", self._show_ctx_menu)

    # ═══════════════════════════════════════════════════
    # 检索逻辑
    # ═══════════════════════════════════════════════════
    def _on_search(self):
        query = self._query_value.strip()
        if not query:
            messagebox.showwarning("提示", "请先点击「检索输入」区域输入关键词")
            return
        if self.searching:
            return

        self.searching = True
        self.search_btn.config(state=tk.DISABLED, text="检索中...")
        self.csv_btn.config(state=tk.DISABLED)
        self.txt_btn.config(state=tk.DISABLED)
        self.progress.start(12)
        self.status_var.set("正在检索文献...")

        # 在后台线程执行检索
        thread = threading.Thread(target=self._do_search, args=(query,),
                                  daemon=True)
        thread.start()

    def _do_search(self, query: str):
        try:
            source = self.source_var.get()
            num = int(self.num_var.get())
            sort = self.sort_var.get()
            min_yr = self._parse_int(self.min_year_var.get())
            max_yr = self._parse_int(self.max_year_var.get())
            verify_online = self.verify_var.get()
            keep_no_doi = self.keep_no_doi_var.get()
            fetch_if = self.fetch_if_var.get()
            user_topic = self._topic_value.strip()
            max_fetch = min(num + 20, 100)

            # 获取研究类型过滤器
            study_filters = self._get_study_filters()

            # 构建检索式
            pubmed_q, crossref_q = build_query(query, study_filters=study_filters)
            filter_labels = [STUDY_TYPE_FILTERS[k]["label"]
                             for k in study_filters
                             if k in STUDY_TYPE_FILTERS] if study_filters else []
            filter_txt = f"  |  过滤: {', '.join(filter_labels)}" if filter_labels else ""
            info = (f"检索式 — PubMed: {pubmed_q}  |  Crossref: {crossref_q}{filter_txt}")
            self.root.after(0, lambda: self.query_info_var.set(info))

            pubmed_papers = []
            crossref_papers = []

            # PubMed
            if source in ("both", "pubmed"):
                self.root.after(0, lambda: self.status_var.set(
                    "正在检索 PubMed ..."))
                try:
                    pubmed_papers = search_pubmed(
                        pubmed_q, max_results=max_fetch,
                        sort=sort, min_year=min_yr, max_year=max_yr)
                except Exception as e:
                    self.root.after(0, lambda: self.status_var.set(
                        f"PubMed 检索出错: {e}"))

            # Crossref
            if source in ("both", "crossref"):
                self.root.after(0, lambda: self.status_var.set(
                    "正在检索 Crossref ..."))
                try:
                    crossref_papers = search_crossref(
                        crossref_q, max_results=max_fetch,
                        sort=sort, min_year=min_yr, max_year=max_yr)
                except Exception as e:
                    self.root.after(0, lambda: self.status_var.set(
                        f"Crossref 检索出错: {e}"))

            # 合并去重
            self.root.after(0, lambda: self.status_var.set("正在合并去重..."))
            papers = self._merge(pubmed_papers, crossref_papers)

            # 过滤无 DOI
            if not keep_no_doi:
                papers = [p for p in papers if p.doi]

            # DOI 验证
            if verify_online:
                self.root.after(0, lambda: self.status_var.set(
                    f"正在验证 {len(papers)} 个 DOI（Crossref API）..."))
                papers = validate_papers(papers, method="crossref")
            else:
                papers = validate_papers(papers, method="format")

            # 查询影响因子
            if fetch_if:
                self.root.after(0, lambda: self.status_var.set(
                    f"正在查询 {len(papers)} 篇文献的影响因子（OpenAlex）..."))
                papers = fetch_impact_factors(papers, max_workers=4)

            # 计算相关度
            if user_topic:
                self.root.after(0, lambda: self.status_var.set(
                    "正在分析文献与课题的相关度..."))
                papers = compute_batch_relevance(user_topic, papers)

            # 结构标签打标
            self.root.after(0, lambda: self.status_var.set(
                "正在为文献打结构标签..."))
            papers = tag_papers(papers)
            # 将 _tag_* 写入正式字段
            for p in papers:
                p.research_type = getattr(p, '_tag_research_type', '')
                p.pollutant_category = getattr(p, '_tag_pollutant_category', '')
                p.exposure_window = getattr(p, '_tag_exposure_window', '')

            # 课题防护栏（重排序 + 降权非相关文献）
            if user_topic:
                self.root.after(0, lambda: self.status_var.set(
                    "正在应用课题防护栏..."))
                papers = apply_topic_guardrails(papers, user_topic)

            # 保存用户课题描述，供详情窗口使用
            self._user_topic = user_topic

            # 排序
            if sort == "year":
                papers.sort(key=lambda p: p.year or "0000", reverse=True)

            self.papers = papers

            # 统计
            pm_count = sum(1 for p in papers if "PubMed" in p.source)
            cr_count = sum(1 for p in papers if "Crossref" in p.source)
            doi_ok = sum(1 for p in papers if p.doi_verified)
            total = len(papers)

            # 影响因子均值
            if_values = [p.impact_factor for p in papers if p.impact_factor]
            avg_if = sum(if_values) / len(if_values) if if_values else None

            # 相关度均值
            rel_values = [p.relevance_score for p in papers
                          if p.relevance_score > 0]
            avg_rel = sum(rel_values) / len(rel_values) if rel_values else None

            # 更新 UI（在主线程）
            self.root.after(0, lambda: self._show_results(
                papers[:num], total, pm_count, cr_count, doi_ok,
                avg_if, avg_rel))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(
                "检索错误", str(e)))
        finally:
            self.root.after(0, self._search_done)

    def _search_done(self):
        self.searching = False
        self.search_btn.config(state=tk.NORMAL, text="🔍  开始检索")
        self.progress.stop()
        if self.papers:
            self.csv_btn.config(state=tk.NORMAL)
            self.txt_btn.config(state=tk.NORMAL)
            self.status_var.set(
                f"检索完成，共 {len(self.papers)} 篇文献")
        else:
            self.status_var.set("未找到符合条件的文献")

    def _show_results(self, papers, total, pm, cr, doi_ok,
                      avg_if=None, avg_rel=None):
        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 插入数据
        for i, p in enumerate(papers, 1):
            verified = "✓" if p.doi_verified else "✗"
            if_str = f"{p.impact_factor:.2f}" if p.impact_factor else "N/A"
            rel_str = f"{p.relevance_score:.0f}%" if p.relevance_score > 0 else "-"
            rt_str = getattr(p, 'research_type', '') or '-'
            pc_str = getattr(p, 'pollutant_category', '') or '-'
            ew_str = getattr(p, 'exposure_window', '') or '-'
            values = (i, p.title, p.authors[:60], p.journal,
                      p.year, if_str, rel_str,
                      rt_str, pc_str, ew_str,
                      p.doi, verified, p.source)
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", tk.END, iid=str(i - 1), values=values,
                             tags=(tag,))

        # 行交替色
        self.tree.tag_configure("even", background=COLORS["row_alt"])
        self.tree.tag_configure("odd", background=COLORS["card"])

        # 更新统计
        self.stat_labels["total"].config(text=f"总计: {total}")
        self.stat_labels["pubmed"].config(text=f"PubMed: {pm}")
        self.stat_labels["crossref"].config(text=f"Crossref: {cr}")
        self.stat_labels["doi_ok"].config(text=f"DOI验证: {doi_ok}/{total}")
        if avg_if is not None:
            self.stat_labels["avg_if"].config(text=f"IF均值: {avg_if:.2f}")
        else:
            self.stat_labels["avg_if"].config(text="IF均值: N/A")
        if avg_rel is not None:
            self.stat_labels["avg_rel"].config(text=f"相关度: {avg_rel:.0f}%")
        else:
            self.stat_labels["avg_rel"].config(text="相关度: N/A")

    # ═══════════════════════════════════════════════════
    # 文献详情
    # ═══════════════════════════════════════════════════
    def _on_paper_detail(self, event):
        self._view_selected()

    def _view_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self.papers):
            return
        paper = self.papers[idx]
        self._show_detail_window(paper, idx + 1)

    def _show_detail_window(self, paper: Paper, index: int):
        win = tk.Toplevel(self.root)
        win.title(f"文献详情 #{index}")
        win.geometry("780x820")
        win.resizable(True, True)
        win.configure(bg=COLORS["card"])
        win.transient(self.root)
        win.grab_set()

        # 可滚动画布
        canvas = tk.Canvas(win, bg=COLORS["card"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(win, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=COLORS["card"])

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 鼠标滚轮支持
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        content = scroll_frame

        # 标题
        tk.Label(content, text=paper.title, bg=COLORS["card"], fg=COLORS["text"],
                 font=("Microsoft YaHei UI", 13, "bold"),
                 wraplength=720, justify=tk.LEFT).pack(
            fill=tk.X, padx=20, pady=(18, 10))

        # 信息网格
        info_frame = tk.Frame(content, bg=COLORS["card"])
        info_frame.pack(fill=tk.X, padx=20)

        # 影响因子格式化
        if_str = format_if(paper.impact_factor)
        if_lvl = if_level(paper.impact_factor)
        if_display = f"{if_str}  {if_lvl}" if if_lvl else if_str

        # 相关度
        rel_str = f"{paper.relevance_score:.1f}%"
        rel_lvl = relevance_level(paper.relevance_score)
        rel_display = f"{rel_str}  {rel_lvl}"

        # 结构标签
        rt_str = getattr(paper, 'research_type', '') or "未标注"
        pc_str = getattr(paper, 'pollutant_category', '') or "未标注"
        ew_str = getattr(paper, 'exposure_window', '') or "未标注"

        fields = [
            ("作者",     paper.authors),
            ("期刊",     paper.journal),
            ("年份",     paper.year),
            ("影响因子", if_display),
            ("相关度",   rel_display),
            ("研究类型", rt_str),
            ("污染物",   pc_str),
            ("暴露窗口", ew_str),
            ("DOI",      paper.doi),
            ("DOI验证",  "✓ 通过" if paper.doi_verified else "✗ 未通过"),
            ("PMID",     paper.pmid or "无"),
            ("来源",     paper.source),
            ("链接",     paper.display_link),
        ]
        for i, (label, value) in enumerate(fields):
            tk.Label(info_frame, text=f"{label}:", bg=COLORS["card"],
                     fg=COLORS["text2"], font=FONT_B, width=8,
                     anchor="e").grid(row=i, column=0, sticky="ne",
                                      padx=(0, 8), pady=3)
            val_label = tk.Label(info_frame, text=value, bg=COLORS["card"],
                                 fg=COLORS["text"], font=FONT,
                                 wraplength=620, justify=tk.LEFT,
                                 anchor="w")
            val_label.grid(row=i, column=1, sticky="w", pady=3)

            # 链接可点击
            if label == "链接" and value:
                val_label.config(fg=COLORS["accent"], cursor="hand2",
                                 font=("Microsoft YaHei UI", 10, "underline"))
                val_label.bind("<Button-1>",
                               lambda e, url=value: self._open_url(url))

        # 摘要
        tk.Label(content, text="摘要:", bg=COLORS["card"], fg=COLORS["text2"],
                 font=FONT_B, anchor="w").pack(fill=tk.X, padx=20, pady=(15, 3))

        abs_text = tk.Text(content, height=8, font=FONT, bg=COLORS["input_bg"],
                           fg=COLORS["text"], wrap=tk.WORD, relief="solid",
                           bd=1, padx=8, pady=8)
        abs_text.pack(fill=tk.X, padx=20, pady=(0, 10))
        abs_text.insert("1.0", paper.abstract or "（无摘要）")
        abs_text.config(state=tk.DISABLED)

        # ━━ 智能分析报告 ━━
        user_topic = getattr(self, '_user_topic', '')
        if user_topic and paper.abstract:
            tk.Label(content, text="📊 课题相关性分析:", bg=COLORS["card"],
                     fg=COLORS["accent"], font=("Microsoft YaHei UI", 12, "bold"),
                     anchor="w").pack(fill=tk.X, padx=20, pady=(10, 3))

            insights = generate_insights(
                user_topic, paper.title, paper.abstract,
                paper.relevance_score)

            analysis_text = tk.Text(content, height=12, font=FONT,
                                    bg="#F0F9FF", fg=COLORS["text"],
                                    wrap=tk.WORD, relief="solid",
                                    bd=1, padx=10, pady=10)
            analysis_text.pack(fill=tk.X, padx=20, pady=(0, 10))
            analysis_text.insert("1.0", insights)
            analysis_text.config(state=tk.DISABLED)

        # 底部按钮
        btn_frame = tk.Frame(content, bg=COLORS["card"])
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 15))

        tk.Button(btn_frame, text="复制 DOI", bg=COLORS["accent"], fg="white",
                  font=FONT, bd=0, padx=14, pady=5, cursor="hand2",
                  command=lambda: self._copy_to_clipboard(
                      paper.doi)).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="复制引用", bg=COLORS["success"], fg="white",
                  font=FONT, bd=0, padx=14, pady=5, cursor="hand2",
                  command=lambda: self._copy_to_clipboard(
                      self._format_citation(paper))).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="浏览器打开", bg="#8B5CF6", fg="white",
                  font=FONT, bd=0, padx=14, pady=5, cursor="hand2",
                  command=lambda: self._open_url(
                      paper.display_link)).pack(side=tk.LEFT, padx=4)
        if user_topic and paper.abstract:
            tk.Button(btn_frame, text="复制分析报告", bg=COLORS["warning"],
                      fg="white", font=FONT, bd=0, padx=14, pady=5,
                      cursor="hand2",
                      command=lambda: self._copy_to_clipboard(
                          insights)).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="关闭", bg=COLORS["border"], fg=COLORS["text"],
                  font=FONT, bd=0, padx=14, pady=5, cursor="hand2",
                  command=win.destroy).pack(side=tk.RIGHT, padx=4)

    # ═══════════════════════════════════════════════════
    # 导出
    # ═══════════════════════════════════════════════════
    def _export_csv(self):
        if not self.papers:
            messagebox.showinfo("提示", "没有可导出的结果")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile=f"lit_search_{time.strftime('%Y%m%d_%H%M%S')}.csv",
            title="导出 CSV")
        if not filepath:
            return
        try:
            path = export_csv(self.papers, filepath,
                              include_abstract=self.abstract_var.get())
            messagebox.showinfo("导出成功",
                                f"已导出 {len(self.papers)} 篇文献\n{path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _export_txt(self):
        if not self.papers:
            messagebox.showinfo("提示", "没有可导出的结果")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt")],
            initialfile=f"lit_search_{time.strftime('%Y%m%d_%H%M%S')}.txt",
            title="导出 TXT")
        if not filepath:
            return
        try:
            path = export_txt(self.papers, filepath)
            messagebox.showinfo("导出成功",
                                f"已导出 {len(self.papers)} 篇文献\n{path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    # ═══════════════════════════════════════════════════
    # 表格排序
    # ═══════════════════════════════════════════════════
    def _sort_column(self, col):
        """点击表头排序"""
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children()]

        # 数字列用数字排序
        if col in ("idx", "year"):
            try:
                items.sort(key=lambda t: int(t[0]) if t[0] else 0,
                           reverse=True)
            except ValueError:
                items.sort(reverse=True)
        elif col in ("impact_factor", "relevance"):
            # IF 和相关度列：按浮点数排序
            def _parse_float(s):
                try:
                    return float(s.replace("%", ""))
                except (ValueError, AttributeError):
                    return -1.0
            items.sort(key=lambda t: _parse_float(t[0]), reverse=True)
        else:
            items.sort()

        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)

    # ═══════════════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════════════
    def _get_study_filters(self) -> list[str]:
        """获取已勾选的研究类型过滤器，并处理互斥"""
        selected = [k for k, v in self.study_filter_vars.items() if v.get()]
        # 互斥处理：animal_only 和 human_only 不能同时选
        if "animal_only" in selected and "human_only" in selected:
            selected.remove("human_only")
        # review_only 和 exclude_review 不能同时选
        if "review_only" in selected and "exclude_review" in selected:
            selected.remove("exclude_review")
        return selected

    def _merge(self, pubmed_papers, crossref_papers):
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

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, bg=COLORS["card"], fg=COLORS["text"],
                 font=("Microsoft YaHei UI", 12, "bold"),
                 anchor="w").pack(fill=tk.X, pady=(8, 2))

    def _option_row(self, parent, label_text):
        row = tk.Frame(parent, bg=COLORS["card"])
        row.pack(fill=tk.X, pady=4)
        tk.Label(row, text=label_text, width=10, anchor="e",
                 bg=COLORS["card"], fg=COLORS["text"],
                 font=FONT).pack(side=tk.LEFT)
        return row

    def _on_num_spin(self):
        """Spinbox 值变化时验证范围"""
        try:
            val = int(self.num_var.get())
            if val < 1:
                self.num_var.set("1")
            elif val > 100:
                self.num_var.set("100")
        except ValueError:
            self.num_var.set("20")

    def _on_window_resize(self, event):
        """窗口大小改变时自适应调整"""
        # 仅响应根窗口的 Configure 事件
        if event.widget != self.root:
            return
        # 更新预览标签的 wraplength
        try:
            panel_w = self.paned.sash_coord(0)[0]
            wrap_w = max(150, panel_w - 60)
            self.query_preview.config(wraplength=wrap_w)
            self.topic_preview.config(wraplength=wrap_w)
        except Exception:
            pass

    def _set_query(self, text):
        self._query_value = text
        self._update_preview(self.query_preview, text, "点击此处输入检索关键词")

    def _on_query_set(self, text):
        """检索输入对话框确认后回调"""
        self._query_value = text
        self._update_preview(self.query_preview, text, "点击此处输入检索关键词")

    def _on_topic_set(self, text):
        """课题描述对话框确认后回调"""
        self._topic_value = text
        self._update_preview(self.topic_preview, text, "点击此处输入课题描述")

    def _update_preview(self, label, text, placeholder):
        """更新预览标签显示"""
        if text.strip():
            # 截断显示，最多显示 3 行
            display = text.strip()
            if len(display) > 120:
                display = display[:120] + "..."
            label.config(text=display, fg=COLORS["text"])
        else:
            label.config(text=f"（{placeholder}）", fg=COLORS["text2"])

    def _open_input_dialog(self, title, prompt, current_value, callback):
        """弹出文本输入对话框"""
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("600x420")
        win.resizable(True, True)
        win.configure(bg=COLORS["card"])
        win.transient(self.root)
        win.grab_set()

        # ── 先 pack 底部固定元素，确保始终可见 ──

        # 按钮区（底部）
        btn_frame = tk.Frame(win, bg=COLORS["card"])
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(5, 15))

        # 字数统计（按钮上方）
        char_var = tk.StringVar(value=f"字数: {len(current_value)}")
        tk.Label(win, textvariable=char_var, bg=COLORS["card"],
                 fg=COLORS["text2"], font=FONT_SMALL,
                 anchor="w").pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(4, 0))

        # ── 再 pack 顶部和中间的可扩展元素 ──

        # 提示文字（顶部）
        tk.Label(win, text=prompt, bg=COLORS["card"], fg=COLORS["text"],
                 font=FONT_B, anchor="w").pack(side=tk.TOP, fill=tk.X,
                                               padx=20, pady=(20, 8))

        # 快捷提示
        tk.Label(win, text="提示: Ctrl+Enter 快速确认",
                 bg=COLORS["card"], fg=COLORS["text2"],
                 font=("Microsoft YaHei UI", 8),
                 anchor="w").pack(side=tk.TOP, fill=tk.X, padx=20, pady=(0, 6))

        # 文本输入区（中间，自动填充剩余空间）
        text_frame = tk.Frame(win, bg=COLORS["card"])
        text_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True,
                        padx=20, pady=(0, 6))

        text_widget = tk.Text(text_frame, font=("Microsoft YaHei UI", 11),
                              bg=COLORS["input_bg"], fg=COLORS["text"],
                              wrap=tk.WORD, relief="solid", bd=1,
                              padx=10, pady=10, undo=True,
                              insertbackground=COLORS["text"])
        scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL,
                               command=text_widget.yview)
        text_widget.configure(yscrollcommand=scroll.set)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 填入当前值
        if current_value:
            text_widget.insert("1.0", current_value)

        # 自动聚焦并将光标移到末尾
        text_widget.focus_set()
        text_widget.mark_set(tk.INSERT, tk.END)
        text_widget.see(tk.END)

        def _update_count(event=None):
            content = text_widget.get("1.0", tk.END).strip()
            char_var.set(f"字数: {len(content)}")
        text_widget.bind("<KeyRelease>", _update_count)

        # ── 按钮 ──
        def _confirm():
            value = text_widget.get("1.0", tk.END).strip()
            callback(value)
            win.destroy()

        def _clear():
            text_widget.delete("1.0", tk.END)
            _update_count()

        tk.Button(btn_frame, text="✅ 确认保存", bg=COLORS["accent"], fg="white",
                  font=FONT_B, bd=0, padx=24, pady=8, cursor="hand2",
                  command=_confirm).pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(btn_frame, text="🗑 清空", bg=COLORS["warning"], fg="white",
                  font=FONT, bd=0, padx=14, pady=8, cursor="hand2",
                  command=_clear).pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(btn_frame, text="取消", bg=COLORS["border"], fg=COLORS["text"],
                  font=FONT, bd=0, padx=14, pady=8, cursor="hand2",
                  command=win.destroy).pack(side=tk.RIGHT)

        # Ctrl+Enter 快捷确认
        text_widget.bind("<Control-Return>", lambda e: _confirm())

        # 窗口居中显示
        win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 600) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 420) // 2
        win.geometry(f"+{max(0,x)}+{max(0,y)}")

    def _parse_int(self, s):
        try:
            return int(s.strip())
        except (ValueError, AttributeError):
            return None

    def _show_ctx_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.ctx_menu.post(event.x_root, event.y_root)

    def _copy_doi(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx < len(self.papers):
            self._copy_to_clipboard(self.papers[idx].doi)

    def _open_link(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx < len(self.papers):
            self._open_url(self.papers[idx].display_link)

    def _copy_to_clipboard(self, text):
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set(f"已复制: {text[:50]}...")

    def _open_url(self, url):
        if url:
            import webbrowser
            webbrowser.open(url)

    def _format_citation(self, p: Paper) -> str:
        """生成简单引用格式"""
        parts = []
        if p.authors:
            parts.append(p.authors)
        if p.title:
            parts.append(f"({p.year})" if p.year else "")
            parts.append(p.title + ".")
        if p.journal:
            parts.append(p.journal + ".")
        if p.doi:
            parts.append(f"https://doi.org/{p.doi}")
        return " ".join(parts)

    def _show_about(self):
        """显示关于/更新日志窗口"""
        win = tk.Toplevel(self.root)
        win.title("关于 LitSearch")
        win.geometry("600x520")
        win.resizable(True, True)
        win.configure(bg=COLORS["card"])
        win.transient(self.root)
        win.grab_set()

        # 标题
        tk.Label(win, text=f"📚 {APP_NAME}",
                 bg=COLORS["card"], fg=COLORS["text"],
                 font=("Microsoft YaHei UI", 18, "bold")).pack(pady=(20, 5))
        tk.Label(win, text=f"版本 {APP_VERSION}",
                 bg=COLORS["card"], fg=COLORS["accent"],
                 font=("Microsoft YaHei UI", 12)).pack(pady=(0, 5))

        # 联系信息
        contact_frame = tk.Frame(win, bg=COLORS["highlight"], padx=15, pady=10)
        contact_frame.pack(fill=tk.X, padx=20, pady=10)
        tk.Label(contact_frame,
                 text="为研究生设计的文献检索与智能分析工具",
                 bg=COLORS["highlight"], fg=COLORS["text"],
                 font=FONT_B).pack(anchor="w")
        tk.Label(contact_frame,
                 text=f"✉ 联系邮箱: {CONTACT_EMAIL}",
                 bg=COLORS["highlight"], fg=COLORS["text"],
                 font=FONT).pack(anchor="w", pady=(5, 0))

        github_lbl = tk.Label(contact_frame,
                              text=f"🔗 GitHub: {GITHUB_URL}",
                              bg=COLORS["highlight"], fg=COLORS["accent"],
                              font=FONT, cursor="hand2")
        github_lbl.pack(anchor="w", pady=(2, 0))
        github_lbl.bind("<Button-1>",
                        lambda e: self._open_url(GITHUB_URL))

        # 更新日志
        tk.Label(win, text="📋 更新日志", bg=COLORS["card"],
                 fg=COLORS["text"], font=FONT_B,
                 anchor="w").pack(fill=tk.X, padx=20, pady=(10, 5))

        log_text = tk.Text(win, font=FONT_SMALL, bg=COLORS["input_bg"],
                           fg=COLORS["text"], wrap=tk.WORD, relief="solid",
                           bd=1, padx=10, pady=10)
        log_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        # 读取 CHANGELOG.md
        changelog_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "CHANGELOG.md")
        try:
            with open(changelog_path, "r", encoding="utf-8") as f:
                changelog = f.read()
        except FileNotFoundError:
            changelog = ("暂无更新日志。\n\n"
                         f"版本: {APP_VERSION}\n"
                         f"联系: {CONTACT_EMAIL}")
        log_text.insert("1.0", changelog)
        log_text.config(state=tk.DISABLED)

        # 关闭按钮
        tk.Button(win, text="关闭", bg=COLORS["accent"], fg="white",
                  font=FONT, bd=0, padx=20, pady=6, cursor="hand2",
                  command=win.destroy).pack(pady=(0, 15))


# ═══════════════════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()

    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Treeview", font=FONT, rowheight=28)
    style.configure("Treeview.Heading", font=FONT_B)
    style.map("Treeview", background=[("selected", COLORS["accent"])],
              foreground=[("selected", "white")])

    app = LitSearchGUI(root)
    root.mainloop()
