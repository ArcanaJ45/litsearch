# LitSearch - 文献检索工具

面向环境毒理学 / 环境流行病学研究的命令行文献检索工具，支持同时检索 **PubMed** 和 **Crossref**，自动去重、DOI 验证、CSV 导出。

## 功能特性

- 支持 **英文关键词** 和 **中文自然语言描述** 输入
- 同时检索 PubMed E-utilities + Crossref API
- 按 DOI 自动去重，合并两个来源的信息
- DOI 有效性验证（格式校验 + Crossref API 在线验证）
- 默认过滤无 DOI 文献，确保结果可追溯
- 按年份或相关性排序
- 导出 CSV（可含摘要）/ TXT
- 内置中英文环境毒理学术语映射表

## 环境要求

- Python 3.10+
- 网络连接（需访问 PubMed / Crossref API）

## 安装

```bash
cd lit_search
pip install -r requirements.txt
```

## 使用方法

### 基本用法

```bash
# 英文关键词检索
python main.py "PFAS neurotoxicity pregnancy"

# 中文自然语言描述（自动翻译为英文检索词）
python main.py "孕期暴露PFAS对子代神经发育影响"

# 多关键词
python main.py "heavy metals oxidative stress children"
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 检索关键词或自然语言描述 | （必填） |
| `-n, --num` | 显示结果数量 | 20 |
| `--max-fetch` | 每个数据源最大获取数量 | 40 |
| `--source` | 检索来源: `both` / `pubmed` / `crossref` | both |
| `--sort` | 排序: `year` (年份降序) / `relevance` | year |
| `--csv FILE` | 导出为 CSV 文件 | - |
| `--txt FILE` | 导出为 TXT 文件 | - |
| `--abstract` | CSV 中包含摘要 | 否 |
| `--keep-no-doi` | 保留无 DOI 的文献 | 否（默认过滤） |
| `--no-verify` | 跳过 DOI 在线验证（仅格式校验） | 否 |
| `--min-year YEAR` | 最早年份过滤 | - |
| `--max-year YEAR` | 最晚年份过滤 | - |
| `-v, --verbose` | 显示详细过程信息 | 否 |

### 使用示例

```bash
# 检索 PFAS 相关文献，返回 30 条，导出 CSV（含摘要）
python main.py "PFAS exposure birth weight" -n 30 --csv results.csv --abstract

# 仅检索 PubMed，2020 年后的文献，快速模式（不在线验证 DOI）
python main.py "bisphenol A endocrine disruption" --source pubmed --min-year 2020 --no-verify

# 中文输入，详细模式
python main.py "重金属暴露对儿童认知发育的影响" -v --csv 检索结果.csv

# 按相关性排序，保留无 DOI 文献
python main.py "air pollution asthma children cohort" --sort relevance --keep-no-doi
```

### 输出字段

每条结果包含：
- 标题 (title)
- 作者 (authors)
- 期刊 (journal)
- 发表年份 (year)
- DOI + 验证状态
- PubMed ID（如有）
- 链接
- 摘要（如有）
- 数据来源

## 项目结构

```
lit_search/
├── main.py              # CLI 入口，参数解析与主流程
├── api_client.py        # PubMed E-utilities + Crossref API 客户端
├── doi_validator.py     # DOI 格式校验 + 在线验证
├── query_builder.py     # 关键词/中文自然语言 → 检索式转换
├── models.py            # Paper 数据模型
├── exporter.py          # CSV / TXT 导出
├── requirements.txt     # Python 依赖
└── README.md            # 本文件
```

## 注意事项

- PubMed E-utilities 免费使用，无需 API Key（每秒 3 次请求限制）
- Crossref API 免费，建议在 `api_client.py` 中替换为你的邮箱以获得 polite pool 优先级
- DOI 在线验证需要网络，如需加速可使用 `--no-verify` 仅做格式校验
- 中文术语映射表 (`query_builder.py`) 可根据你的研究方向自行扩展
