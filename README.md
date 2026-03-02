# LitSearch - 文献检索工具

LitSearch 是一个面向研究生课题场景的文献检索与筛选工具，适用于生物医学、环境毒理学与环境健康等方向。它支持从 PubMed 和 Crossref 检索真实文献、校验 DOI、显示期刊影响因子，并根据课题描述对文献进行多维度相关性评分和课题防护栏过滤，从而提升文献综述与课题设计效率。

## 功能特性

### 核心检索
- 支持 **英文关键词** 和 **中文自然语言描述** 输入
- 同时检索 **PubMed E-utilities + Crossref API**，自动去重合并
- **PubMed 同义词扩展**：自动将关键词扩展为 OR 概念组（如 PFAS → PFOS/PFOA/PFNA/...），避免过于严格的 AND 查询

### 智能分析（v1.2.0）
- **多维度相关性评分**：6 维度规则评分（污染物 30 + 健康结局 25 + 暴露窗口 15 + 研究对象 10 + 机制方法 10 + TF-IDF 语义 10 = 100 分）
- **课题防护栏**：针对 PFAS 等课题自动启用专项规则，降权非目标暴露物（如 nicotine/morphine）文献
- **结构化标签**：自动识别研究类型（流行病学/动物实验/体外实验/综述）、污染物类别、暴露窗口
- **影响因子**：通过 OpenAlex API 自动获取期刊 2 年平均被引次数

### 其他
- DOI 有效性验证（格式校验 + Crossref API 在线验证）
- 研究类型过滤（仅动物实验/仅人群研究/仅综述/排除综述）
- 导出 CSV（可含摘要）/ TXT，含影响因子、相关度、结构标签
- 内置中英文环境毒理学术语映射表（100+ 术语）

## 环境要求

- Python 3.10+
- 网络连接（需访问 PubMed / Crossref / OpenAlex API）

## 安装

```bash
cd lit_search
pip install -r requirements.txt
```

## 使用方法

### GUI 图形界面（推荐）

```bash
python src/gui.py
```

或直接运行打包好的 `LitSearch文献检索.exe`（Windows）/ `LitSearch文献检索.app`（macOS）。

### Streamlit 网页版

```bash
streamlit run src/streamlit_app.py
```

在线版本部署于 Streamlit Community Cloud，任何浏览器即可访问。

### CLI 命令行

```bash
# 英文关键词检索
python src/main.py "PFAS neurotoxicity pregnancy"

# 中文自然语言描述（自动翻译为英文检索词）
python src/main.py "孕期暴露PFAS对子代神经发育影响"

# 导出 CSV（含摘要），30 条结果
python src/main.py "PFAS exposure birth weight" -n 30 --csv results.csv --abstract
```

### CLI 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 检索关键词或自然语言描述 | （必填） |
| `-n, --num` | 显示结果数量 | 20 |
| `--max-fetch` | 每个数据源最大获取数量 | 40 |
| `--source` | 检索来源: `both` / `pubmed` / `crossref` | both |
| `--sort` | 排序: `year` / `relevance` | year |
| `--csv FILE` | 导出为 CSV 文件 | - |
| `--txt FILE` | 导出为 TXT 文件 | - |
| `--abstract` | CSV 中包含摘要 | 否 |
| `--keep-no-doi` | 保留无 DOI 的文献 | 否 |
| `--no-verify` | 跳过 DOI 在线验证 | 否 |
| `--min-year YEAR` | 最早年份过滤 | - |
| `--max-year YEAR` | 最晚年份过滤 | - |

## 项目结构

```
lit_search/
├── src/                          # 源代码
│   ├── gui.py                    # GUI 入口（tkinter）
│   ├── streamlit_app.py          # Streamlit 网页版入口
│   ├── main.py                   # CLI 入口
│   ├── models.py                 # Paper 数据模型
│   ├── api_client.py             # PubMed + Crossref API 客户端
│   ├── query_builder.py          # 查询构建 + PubMed 同义词扩展
│   ├── doi_validator.py          # DOI 格式校验 + 在线验证
│   ├── exporter.py               # CSV / TXT 导出
│   ├── impact_factor.py          # OpenAlex 影响因子查询
│   ├── relevance_analyzer.py     # 多维度相关性评分引擎 (v2)
│   ├── domain_vocab.py           # 领域词典（PFAS 同义词、结局、暴露窗口等）
│   ├── topic_guardrails.py       # 课题防护栏（PFAS 专项规则）
│   └── paper_tagger.py           # 文献结构打标
├── .streamlit/                   # Streamlit 主题配置
├── .github/workflows/            # GitHub Actions（macOS/Win 自动构建）
├── LitSearch文献检索.spec         # PyInstaller Windows 打包配置
├── LitSearch_macOS.spec          # PyInstaller macOS 打包配置
├── requirements.txt              # Python 依赖
├── CHANGELOG.md                  # 更新日志
├── LICENSE
└── README.md
```

## 输出字段

每条结果包含：
- 标题、作者、期刊、年份
- 影响因子（IF）+ 等级标识
- 相关度评分（0-100）+ 6 维度明细
- 研究类型 / 污染物类别 / 暴露窗口（结构标签）
- DOI + 验证状态、PMID、链接
- 摘要（如有）

## 注意事项

- PubMed E-utilities 免费使用，无需 API Key（每秒 3 次请求限制）
- Crossref API 免费，建议在 `api_client.py` 中替换为你的邮箱以获得 polite pool 优先级
- OpenAlex API 免费，无需注册
- 中文术语映射表（`query_builder.py`）和领域词典（`domain_vocab.py`）可根据研究方向自行扩展

## 联系方式

- 开发者：**ArcanaJ**
- 邮箱：arcbj045@gmail.com
- GitHub：https://github.com/ArcanaJ045
