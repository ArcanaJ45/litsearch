"""
领域词表模块：集中管理环境毒理学领域的专业词汇

所有词表均为 set[str]（小写），供检索构造、相关度评分、结构化标签使用。
维护规则：新增词汇只需在此文件对应 set 中添加即可。
"""

# ═══════════════════════════════════════════════════════
# 1. 污染物词表
# ═══════════════════════════════════════════════════════

# PFAS 及其同义词 / 子类（用于 PubMed 同义词扩展 + guardrail 匹配）
PFAS_SYNONYMS = {
    "pfas", "pfos", "pfoa", "pfna", "pfda", "pfhxs", "pfhxa",
    "pfbs", "pfba", "pfhpa", "pfunda", "pfdoa",
    "perfluoro", "perfluoroalkyl", "perfluorinated",
    "polyfluoroalkyl", "polyfluorinated",
    "perfluorooctane", "perfluorooctanoic", "perfluorononanoic",
    "perfluorodecanoic", "perfluorohexane",
    "cl-pfesa", "f-53b", "6:2 cl-pfesa", "8:2 cl-pfesa",
    "genx", "hfpo-da", "adona",
    "chlorinated polyfluoroether", "fluorotelomer",
    "ftoh", "6:2 ftoh", "8:2 ftoh",
    "per- and polyfluoroalkyl",
}

# 非 PFAS 的已知暴露物（用于 guardrail 负例降权）
NON_PFAS_EXPOSURES = {
    # 药物/毒品
    "nicotine", "morphine", "cocaine", "methamphetamine", "cannabis",
    "marijuana", "opioid", "opioids", "heroin", "fentanyl",
    "antidepressant", "antidepressants", "ssri", "ssris",
    "fluoxetine", "sertraline", "paroxetine", "citalopram",
    "valproic", "valproate", "carbamazepine", "phenytoin",
    "thalidomide", "diethylstilbestrol", "des",
    # 烟酒
    "smoking", "tobacco", "cigarette", "alcohol", "ethanol",
    # 其他非 PFAS 污染物大类（当课题是 PFAS 时应降权）
    "aflatoxin", "acrylamide", "formaldehyde", "benzene", "toluene",
    "glyphosate", "atrazine", "chlorpyrifos", "ddt",
    "benzo[a]pyrene", "bap",
}

# 重金属（单独分类，可扩展为独立课题）
HEAVY_METALS = {
    "lead", "mercury", "cadmium", "arsenic", "chromium", "manganese",
    "pb", "hg", "cd", "as", "cr", "mn",
    "methylmercury", "mehg", "arsenite", "arsenate",
}

# 其他环境污染物大类
OTHER_POLLUTANTS = {
    "bisphenol", "bpa", "bps", "bpf",
    "phthalate", "phthalates", "dehp", "dbp", "bbp", "didp", "dinp",
    "pbde", "polybrominated", "decabromodiphenyl",
    "dioxin", "dioxins", "tcdd", "furan", "furans",
    "pcb", "pcbs", "polychlorinated",
    "pesticide", "pesticides", "insecticide", "herbicide", "fungicide",
    "organophosphate", "organophosphorus", "organochlorine",
    "microplastic", "microplastics", "nanoplastic",
    "nanoparticle", "nanoparticles",
    "particulate", "pm2.5", "pm10",
    "endocrine disruptor", "endocrine disrupting",
    "pahs", "polycyclic aromatic",
}


# ═══════════════════════════════════════════════════════
# 2. 暴露窗口词表
# ═══════════════════════════════════════════════════════

EXPOSURE_WINDOWS = {
    "prenatal": {
        "label": "孕期/产前",
        "terms": {
            "prenatal", "pregnancy", "pregnant", "maternal",
            "gestational", "gestation", "in utero", "intrauterine",
            "preconception", "periconceptional",
            "first trimester", "second trimester", "third trimester",
            "placenta", "placental", "transplacental",
            "cord blood", "umbilical",
            "embryo", "embryonic", "fetal", "fetus", "foetal", "foetus",
        },
    },
    "perinatal": {
        "label": "围产期",
        "terms": {
            "perinatal", "birth", "neonatal", "neonate", "newborn",
            "delivery", "parturition",
            "birth weight", "birth outcome", "birth defect",
            "preterm", "premature", "low birth weight", "lbw",
        },
    },
    "lactation": {
        "label": "哺乳期",
        "terms": {
            "lactation", "lactational", "breastfeeding", "breast milk",
            "breast-fed", "breastfed", "nursing",
            "postnatal", "postpartum",
        },
    },
    "childhood": {
        "label": "儿童期",
        "terms": {
            "child", "children", "childhood", "pediatric", "paediatric",
            "infant", "infancy", "toddler", "preschool",
            "school-age", "school age", "adolescent", "adolescence",
            "puberty", "pubertal",
        },
    },
    "adulthood": {
        "label": "成年期",
        "terms": {
            "adult", "adulthood", "occupational",
            "worker", "workers", "elderly", "aging",
        },
    },
}


# ═══════════════════════════════════════════════════════
# 3. 研究对象/模型词表
# ═══════════════════════════════════════════════════════

STUDY_SUBJECTS = {
    "human": {
        "label": "人群",
        "terms": {
            "human", "humans", "population", "cohort", "participant",
            "participants", "subject", "subjects", "patient", "patients",
            "women", "men", "mother", "mothers", "father",
            "epidemiologic", "epidemiological", "epidemiology",
            "cross-sectional", "longitudinal", "prospective", "retrospective",
            "case-control", "clinical", "trial",
        },
    },
    "animal": {
        "label": "动物",
        "terms": {
            "mouse", "mice", "rat", "rats", "rodent", "rodents",
            "zebrafish", "danio", "drosophila",
            "rabbit", "rabbits", "monkey", "primate", "primates",
            "pup", "pups", "dam", "dams", "sire",
            "offspring", "f1", "f2", "f0",
            "in vivo", "animal", "animals", "murine",
            "gavage", "intraperitoneal",
        },
    },
    "cell": {
        "label": "细胞",
        "terms": {
            "in vitro", "cell", "cells", "cell line", "culture",
            "cultured", "neuron", "neurons", "neuronal",
            "astrocyte", "astrocytes", "microglia", "oligodendrocyte",
            "hepg2", "hek293", "shsy5y", "sh-sy5y", "pc12",
            "primary cell", "stem cell", "ipsc",
            "cytotoxicity", "viability", "proliferation",
        },
    },
}


# ═══════════════════════════════════════════════════════
# 4. 健康结局/终点词表
# ═══════════════════════════════════════════════════════

NEURO_OUTCOMES = {
    "neurotoxicity", "neurotoxic", "neurodevelopment", "neurodevelopmental",
    "neurobehavioral", "neurological",
    "cognitive", "cognition", "iq", "intelligence",
    "behavior", "behaviour", "behavioral", "behavioural",
    "attention", "adhd", "attention deficit", "hyperactivity",
    "autism", "asd", "autistic",
    "learning", "memory", "executive function",
    "motor", "locomotor", "locomotion",
    "anxiety", "depression", "depressive",
    "brain", "cerebral", "cerebellum", "hippocampus", "hippocampal",
    "cortex", "cortical", "prefrontal",
    "synapse", "synaptic", "synaptogenesis",
    "myelination", "myelin", "demyelination",
    "neuroinflammation", "neurodegeneration", "neuroprotection",
    "blood-brain barrier", "bbb",
    "bayley", "wisc", "wppsi", "denver", "griffiths",
    "open field", "morris water maze", "elevated plus maze",
    "novel object recognition", "passive avoidance",
    "rotarod", "beam walking", "grip strength",
}

ENDOCRINE_OUTCOMES = {
    "thyroid", "hypothyroid", "hyperthyroid", "tsh", "t3", "t4", "ft3", "ft4",
    "thyroxine", "triiodothyronine", "thyroglobulin",
    "estrogen", "testosterone", "androgen", "progesterone",
    "endocrine", "hormone", "hormonal",
    "reproductive", "fertility", "infertility",
    "semen", "sperm", "ovary", "ovarian", "testicular", "testis",
    "puberty", "pubertal", "menarche",
}

IMMUNE_OUTCOMES = {
    "immune", "immunity", "immunotoxicity", "immunosuppression",
    "allergy", "allergic", "asthma", "atopy", "atopic",
    "cytokine", "interleukin", "tnf", "interferon",
    "antibody", "antibodies", "immunoglobulin", "ige", "igg",
    "vaccine", "vaccination", "infection",
    "inflammation", "inflammatory", "anti-inflammatory",
}

METABOLIC_OUTCOMES = {
    "obesity", "overweight", "adiposity", "bmi", "body mass",
    "diabetes", "diabetic", "insulin", "glucose", "glycemic",
    "metabolic syndrome", "metabolic", "lipid", "cholesterol",
    "triglyceride", "dyslipidemia",
    "liver", "hepatic", "hepatotoxicity", "nafld",
    "kidney", "renal", "nephrotoxicity",
    "cardiovascular", "hypertension", "blood pressure",
}

CANCER_OUTCOMES = {
    "cancer", "carcinogen", "carcinogenic", "carcinogenesis",
    "tumor", "tumour", "neoplasm", "malignant", "malignancy",
    "genotoxicity", "genotoxic", "mutagenicity", "mutagenic",
    "dna damage", "dna repair", "mutation",
}


# ═══════════════════════════════════════════════════════
# 5. 机制/方法词表
# ═══════════════════════════════════════════════════════

MECHANISM_TERMS = {
    "oxidative stress", "oxidative", "ros", "reactive oxygen",
    "antioxidant", "sod", "catalase", "glutathione", "gsh", "mda",
    "apoptosis", "apoptotic", "caspase", "bcl-2", "bax",
    "autophagy", "mitochondria", "mitochondrial",
    "epigenetic", "epigenetics", "methylation", "dna methylation",
    "histone", "mirna", "microrna", "noncoding rna",
    "gene expression", "transcription", "transcriptomic", "transcriptome",
    "proteomics", "proteomic", "metabolomics", "metabolomic",
    "receptor", "signaling", "pathway", "nrf2", "ahr",
    "ppar", "mapk", "nf-kb", "wnt", "notch", "bdnf", "ngf",
    "neurotrophin", "neurotransmitter", "dopamine", "serotonin",
    "gaba", "glutamate", "acetylcholine", "cholinergic",
    "calcium", "ca2+", "ion channel",
}

METHOD_TERMS = {
    # 流行病学/统计
    "dose-response", "dose response", "benchmark dose", "bmd",
    "odds ratio", "hazard ratio", "relative risk", "confidence interval",
    "regression", "logistic", "linear", "multivariate", "adjusted",
    "meta-analysis", "systematic review", "pooled analysis",
    "biomonitoring", "exposure assessment", "pharmacokinetic",
    "pbpk", "toxicokinetic",
    # 实验方法
    "qpcr", "rt-pcr", "western blot", "elisa", "immunohistochemistry",
    "ihc", "immunofluorescence", "flow cytometry",
    "rna-seq", "microarray", "chip-seq",
    "hplc", "gc-ms", "lc-ms", "mass spectrometry",
}


# ═══════════════════════════════════════════════════════
# 6. 研究类型识别词表
# ═══════════════════════════════════════════════════════

RESEARCH_TYPE_TERMS = {
    "animal_study": {
        "label": "动物实验",
        "terms": {
            "mice", "mouse", "rat", "rats", "rodent", "zebrafish",
            "in vivo", "animal model", "gavage", "intraperitoneal",
            "pup", "pups", "dam", "dams", "murine",
            "treated with", "administered", "exposed to",
        },
    },
    "human_study": {
        "label": "人群研究",
        "terms": {
            "cohort", "cross-sectional", "case-control", "longitudinal",
            "prospective", "retrospective", "epidemiologic",
            "population", "participants", "subjects", "patients",
            "birth cohort", "mother-child", "mother-infant",
            "biomonitoring", "nhanes", "survey",
        },
    },
    "cell_study": {
        "label": "细胞研究",
        "terms": {
            "in vitro", "cell line", "cell culture", "cultured cells",
            "primary cells", "hepg2", "shsy5y", "sh-sy5y", "pc12",
            "cytotoxicity", "cell viability", "proliferation",
            "neuron culture", "astrocyte culture",
        },
    },
    "review": {
        "label": "综述",
        "terms": {
            "review", "systematic review", "meta-analysis",
            "narrative review", "scoping review", "overview",
            "state of the art", "current knowledge",
            "literature review", "critical review",
        },
    },
}


# ═══════════════════════════════════════════════════════
# 7. PubMed 同义词扩展映射（关键词 → OR 组）
# ═══════════════════════════════════════════════════════

PUBMED_SYNONYM_GROUPS = {
    # 关键词（小写） → PubMed 检索用的 OR 组
    "pfas": (
        '("PFAS" OR "PFOS" OR "PFOA" OR "PFNA" OR "PFHxS" '
        'OR "perfluoroalkyl" OR "polyfluoroalkyl" '
        'OR "perfluorinated" OR "perfluorooctane" '
        'OR "perfluorooctanoic" OR "GenX" OR "HFPO-DA" '
        'OR "Cl-PFESA" OR "F-53B" OR "fluorotelomer")'
    ),
    "neurotoxicity": (
        '("neurotoxicity" OR "neurodevelopment" OR "neurodevelopmental" '
        'OR "neurobehavioral" OR "neurotoxic" OR "neurological")'
    ),
    "pregnancy": (
        '("pregnancy" OR "prenatal" OR "gestational" OR "maternal" '
        'OR "in utero" OR "intrauterine" OR "pregnant")'
    ),
    "offspring": (
        '("offspring" OR "child" OR "children" OR "fetal" OR "fetus" '
        'OR "neonatal" OR "neonate" OR "infant" OR "pup" OR "pups")'
    ),
    "exposure": (
        '("exposure" OR "exposed" OR "environmental exposure" '
        'OR "occupational exposure")'
    ),
    "cognition": (
        '("cognition" OR "cognitive" OR "intelligence" OR "IQ" '
        'OR "learning" OR "memory" OR "executive function")'
    ),
    "behavior": (
        '("behavior" OR "behaviour" OR "behavioral" OR "behavioural" '
        'OR "ADHD" OR "attention deficit" OR "hyperactivity" '
        'OR "autism" OR "ASD")'
    ),
    "thyroid": (
        '("thyroid" OR "TSH" OR "thyroxine" OR "T3" OR "T4" '
        'OR "hypothyroid" OR "thyroid hormone")'
    ),
    "oxidative stress": (
        '("oxidative stress" OR "ROS" OR "reactive oxygen species" '
        'OR "antioxidant" OR "MDA" OR "SOD" OR "glutathione")'
    ),
}


# ═══════════════════════════════════════════════════════
# 8. 工具函数
# ═══════════════════════════════════════════════════════

def match_terms_in_text(text: str, term_set: set) -> set:
    """在文本中匹配词表，返回命中的词（全部小写匹配）"""
    if not text:
        return set()
    text_lower = text.lower()
    matched = set()
    for term in term_set:
        if term in text_lower:
            matched.add(term)
    return matched


def identify_pollutant_category(text: str) -> str:
    """识别文本中的污染物类别"""
    text_lower = text.lower()
    has_pfas = any(t in text_lower for t in PFAS_SYNONYMS)
    has_metal = any(t in text_lower for t in HEAVY_METALS)
    has_other = any(t in text_lower for t in OTHER_POLLUTANTS)

    if has_pfas:
        return "PFAS"
    elif has_metal:
        return "重金属"
    elif has_other:
        return "其他环境污染物"
    else:
        return "未知"


def identify_exposure_window(text: str) -> str:
    """识别文本中的暴露窗口"""
    text_lower = text.lower()
    windows = []
    for key, info in EXPOSURE_WINDOWS.items():
        if any(t in text_lower for t in info["terms"]):
            windows.append(info["label"])
    return "/".join(windows) if windows else "未知"


def identify_research_type(text: str) -> str:
    """识别文本中的研究类型"""
    text_lower = text.lower()
    scores = {}
    for key, info in RESEARCH_TYPE_TERMS.items():
        count = sum(1 for t in info["terms"] if t in text_lower)
        if count > 0:
            scores[key] = count

    if not scores:
        return "其他"

    best = max(scores, key=scores.get)
    return RESEARCH_TYPE_TERMS[best]["label"]


def topic_contains_pfas(topic: str) -> bool:
    """判断用户课题描述是否涉及 PFAS"""
    if not topic:
        return False
    return bool(match_terms_in_text(topic, PFAS_SYNONYMS))
