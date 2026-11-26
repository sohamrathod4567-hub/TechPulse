"""
Skill Extraction and Taxonomy Module for TechPulse.

Provides a structured, curated technical skill taxonomy and a pure-Python,
deterministic skill extraction engine with rigorous false-positive prevention.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class SkillDefinition:
    """
    Represents a canonical technical skill within the TechPulse taxonomy.

    Attributes:
        name: The canonical, standardized name of the skill (e.g. 'PostgreSQL', 'Go').
        category: The classification category (e.g. 'Databases', 'Programming Languages').
        patterns: Pre-compiled regular expression patterns used to detect the skill.
        aliases: Common variations, abbreviations, or framework names representing the skill.
    """

    name: str
    category: str
    patterns: Tuple[re.Pattern[str], ...]
    aliases: Tuple[str, ...] = field(default_factory=tuple)


# Supported Skill Taxonomy Categories in standard reporting order
TAXONOMY_CATEGORIES: Tuple[str, ...] = (
    "Programming Languages",
    "Frontend",
    "Backend",
    "Databases",
    "Cloud",
    "DevOps and Infrastructure",
    "Data Engineering",
    "Data Science and AI",
    "Version Control",
)

# Common verb prepositions and adverbs following the English verb "react"
_REACT_VERB_FOLLOWERS = (
    r"(?:to|against|on|calmly|quickly|promptly|under|with|fast|appropriately|"
    r"effectively|flexibly|positively|negatively|immediately|in\s+a|\w+ly)"
)

# Programming languages used to contextualize short acronyms (e.g. 'R')
_PROGRAMMING_LANG_LIST = (
    r"(?:Python|Java|C\+\+|C#|SQL|Rust|Ruby|TypeScript|JavaScript|Kotlin|Swift|PHP|Scala|Matlab|SAS|SPSS|Julia|Stata)"
)

# Big data tools used to contextualize Apache Spark and Delta Lake
_BIG_DATA_TOOLS = (
    r"(?:Hadoop|Kafka|Flink|Airflow|Hive|Databricks|PySpark|Presto|Delta(?:\s*Lake)?)"
)

# Curated Taxonomy of 66 Technical Skills across 9 Categories
SKILL_TAXONOMY: Dict[str, SkillDefinition] = {
    # =========================================================================
    # 1. Programming Languages (12 skills)
    # =========================================================================
    "Python": SkillDefinition(
        name="Python",
        category="Programming Languages",
        patterns=(
            re.compile(r"\b(?:python(?:3)?|py3)\b", re.IGNORECASE),
        ),
        aliases=("Python3", "py3"),
    ),
    "Java": SkillDefinition(
        name="Java",
        category="Programming Languages",
        patterns=(
            # Match Java as a distinct word, but never when followed by script/scripting/.js
            re.compile(r"\bjava\b(?!\s*[-\.\s]?(?:script|scripting|\.js))", re.IGNORECASE),
        ),
        aliases=("Core Java", "Java 8", "Java 11", "Java 17", "Java 21"),
    ),
    "JavaScript": SkillDefinition(
        name="JavaScript",
        category="Programming Languages",
        patterns=(
            re.compile(r"\b(?:java[\s\-_]*script|ecmascript|es6|es20\d\d)\b", re.IGNORECASE),
            re.compile(
                r"(?:\b(?:HTML|CSS|React|Node|Vue|Frontend|Vanilla)[/,]\s*JS\b|"
                r"\bJS\s*[/,]\s*(?:HTML|CSS|TS|Python|React)\b)"
            ),
            re.compile(r"(?i:(?:experience (?:with|in)|proficien(?:t in|cy with|cy in)|knowledge of))\s+JS\b"),
        ),
        aliases=("JS", "ES6", "ES2015", "ECMAScript"),
    ),
    "TypeScript": SkillDefinition(
        name="TypeScript",
        category="Programming Languages",
        patterns=(
            re.compile(r"\btypescript\b", re.IGNORECASE),
            re.compile(
                r"(?:\b(?:React|Node|Vue|JS|Angular)[/,]\s*TS\b|"
                r"\bTS\s*[/,]\s*(?:React|Node|Vue|JS|Python)\b)"
            ),
            re.compile(r"(?i:(?:experience (?:with|in)|proficien(?:t in|cy with|cy in)|knowledge of))\s+TS\b"),
        ),
        aliases=("TS",),
    ),
    "C#": SkillDefinition(
        name="C#",
        category="Programming Languages",
        patterns=(
            re.compile(r"(?<![a-zA-Z0-9])c\s*#(?![a-zA-Z0-9#])", re.IGNORECASE),
            re.compile(r"\bc[\s\-_]*sharp\b", re.IGNORECASE),
            re.compile(r"\bcsharp\b", re.IGNORECASE),
        ),
        aliases=("C Sharp", "csharp", "C#.NET"),
    ),
    "C++": SkillDefinition(
        name="C++",
        category="Programming Languages",
        patterns=(
            re.compile(r"(?<![a-zA-Z0-9])c\s*\+\+(?![a-zA-Z0-9\+])", re.IGNORECASE),
            re.compile(r"\bcpp\b", re.IGNORECASE),
            re.compile(r"\bc[\s\-_]*plus[\s\-_]*plus\b", re.IGNORECASE),
        ),
        aliases=("Cpp", "C Plus Plus", "cplusplus"),
    ),
    "Go": SkillDefinition(
        name="Go",
        category="Programming Languages",
        patterns=(
            # Unambiguous alias
            re.compile(r"\bgolang\b", re.IGNORECASE),
            # Case-sensitive Go in engineering context
            re.compile(
                r"\bGo\s+(?:lang(?:uage)?|developer|engineer|programmer|programming|"
                r"backend|stack|microservices?|services?|code|development|APIs?|SDK|1\.\d+)\b"
            ),
            # Go paired with another programming language via slash or comma
            re.compile(
                r"\b(?:Python|Java|C\+\+|C#|Rust|Ruby|TypeScript|JavaScript|Kotlin|Swift|PHP|Scala)\s*[/,]\s*Go\b"
            ),
            re.compile(
                r"\bGo\s*[/,]\s*(?:Python|Java|C\+\+|C#|Rust|Ruby|TypeScript|JavaScript|Kotlin|Swift|PHP|Scala)\b"
            ),
            # Go paired with another language via 'and' or 'or'
            re.compile(
                r"\b(?:Python|Java|C\+\+|C#|Rust|Ruby|TypeScript|JavaScript|Kotlin|Swift|PHP|Scala)\s+(?:and|or)\s+Go\b"
            ),
            re.compile(
                r"\bGo\s+(?:and|or)\s+(?:Python|Java|C\+\+|C#|Rust|Ruby|TypeScript|JavaScript|Kotlin|Swift|PHP|Scala)\b"
            ),
            # In tech skill qualification context, excluding English verb prepositions
            re.compile(
                r"(?i:(?:experience (?:with|in)|proficien(?:t in|cy with|cy in)|knowledge of|fluent in|using))\s+Go\b"
                r"(?!\s+(?:to|through|beyond|above|ahead|forward|over|into|out|back|off|under|by|together))"
            ),
            re.compile(
                r"(?:written|built|developed|coded|microservices|services|backend)\s+in\s+Go\b"
            ),
        ),
        aliases=("Golang", "Go language"),
    ),
    "PHP": SkillDefinition(
        name="PHP",
        category="Programming Languages",
        patterns=(
            re.compile(r"\bphp(?:[578])?\b", re.IGNORECASE),
        ),
        aliases=("PHP7", "PHP8"),
    ),
    "Ruby": SkillDefinition(
        name="Ruby",
        category="Programming Languages",
        patterns=(
            re.compile(r"\b(?:ruby(?:\s+on\s+rails)?|ror)\b", re.IGNORECASE),
        ),
        aliases=("Ruby on Rails", "RoR"),
    ),
    "Kotlin": SkillDefinition(
        name="Kotlin",
        category="Programming Languages",
        patterns=(
            re.compile(r"\bkotlin\b", re.IGNORECASE),
        ),
        aliases=(),
    ),
    "Swift": SkillDefinition(
        name="Swift",
        category="Programming Languages",
        patterns=(
            re.compile(r"\bswiftui\b", re.IGNORECASE),
            re.compile(
                r"\bSwift\s+(?:developer|engineer|programmer|programming|code|language|iOS|macOS|app|apps|development)\b"
            ),
            re.compile(
                r"(?:\b(?:iOS|macOS|Objective[\s\-_]*C|Kotlin|Xcode|Cocoa)\s*[/,]\s*Swift\b|"
                r"\bSwift\s*[/,]\s*(?:iOS|macOS|Objective[\s\-_]*C|Kotlin|Xcode|Cocoa)\b)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?i:(?:experience (?:with|in)|proficien(?:t in|cy with|cy in)|knowledge of|using))\s+Swift\b"
                r"(?!\s+(?:turnaround|response|action|manner|fashion|delivery|progress))"
            ),
        ),
        aliases=("SwiftUI",),
    ),
    "R": SkillDefinition(
        name="R",
        category="Programming Languages",
        patterns=(
            re.compile(r"\b(?:r[\s\-_]*lang(?:uage)?|rstudio|r[\s\-_]*project)\b", re.IGNORECASE),
            re.compile(r"\bR\s+(?:programming|scripting|packages?|developer|code)\b"),
            re.compile(
                rf"(?:\b{_PROGRAMMING_LANG_LIST}\s*[/,]\s*(?:and\s+)?R\b(?!\s*(?:&|/)\s*[dD]\b)|"
                rf"\bR\b(?!\s*(?:&|/)\s*[dD]\b)\s*[/,]\s*(?:and\s+)?{_PROGRAMMING_LANG_LIST}\b)"
            ),
            re.compile(
                rf"(?:\b{_PROGRAMMING_LANG_LIST}\s+(?:and|or)\s+R\b(?!\s*(?:&|/)\s*[dD]\b)|"
                rf"\bR\b(?!\s*(?:&|/)\s*[dD]\b)\s+(?:and|or)\s+{_PROGRAMMING_LANG_LIST}\b)"
            ),
            re.compile(
                r"(?i:(?:experience (?:with|in)|proficien(?:t in|cy with|cy in)|knowledge of))\s+R\b(?!\s*(?:&|/)\s*[dD]\b)"
            ),
        ),
        aliases=("R language", "RStudio", "R-project"),
    ),

    # =========================================================================
    # 2. Frontend (7 skills)
    # =========================================================================
    "React": SkillDefinition(
        name="React",
        category="Frontend",
        patterns=(
            re.compile(r"\b(?:react[\s\-_]*\.?js|reactjs|react[\s\-_]+native)\b", re.IGNORECASE),
            re.compile(rf"\bReact\b(?!\s+{_REACT_VERB_FOLLOWERS}\b)"),
        ),
        aliases=("React.js", "ReactJS", "React Native"),
    ),
    "Angular": SkillDefinition(
        name="Angular",
        category="Frontend",
        patterns=(
            re.compile(r"\bangular(?:\.js|js)?\b", re.IGNORECASE),
        ),
        aliases=("AngularJS", "Angular.js"),
    ),
    "Vue.js": SkillDefinition(
        name="Vue.js",
        category="Frontend",
        patterns=(
            re.compile(r"\b(?:vue[\s\-_]*\.?js|vuejs)\b", re.IGNORECASE),
            re.compile(r"\bVue\s*(?:2|3|framework|developer|components?|store|cli)?\b"),
            re.compile(r"(?:\b(?:React|Angular)\s*[/,]\s*Vue\b|\bVue\s*[/,]\s*(?:React|Angular)\b)", re.IGNORECASE),
        ),
        aliases=("Vue", "VueJS", "Vuejs", "Vue 2", "Vue 3"),
    ),
    "Next.js": SkillDefinition(
        name="Next.js",
        category="Frontend",
        patterns=(
            re.compile(r"\bnext[\s\-_]*\.?js\b|\bnextjs\b", re.IGNORECASE),
        ),
        aliases=("NextJS", "Next js", "Nextjs"),
    ),
    "HTML": SkillDefinition(
        name="HTML",
        category="Frontend",
        patterns=(
            re.compile(r"\bhtml(?:5)?\b", re.IGNORECASE),
        ),
        aliases=("HTML5",),
    ),
    "CSS": SkillDefinition(
        name="CSS",
        category="Frontend",
        patterns=(
            re.compile(r"\bcss(?:3)?\b", re.IGNORECASE),
        ),
        aliases=("CSS3",),
    ),
    "Tailwind CSS": SkillDefinition(
        name="Tailwind CSS",
        category="Frontend",
        patterns=(
            re.compile(r"\btailwind(?:[\s\-_]*css)?\b", re.IGNORECASE),
        ),
        aliases=("Tailwind", "TailwindCSS"),
    ),

    # =========================================================================
    # 3. Backend (8 skills)
    # =========================================================================
    "FastAPI": SkillDefinition(
        name="FastAPI",
        category="Backend",
        patterns=(
            re.compile(r"\bfast[\s\-_]*api\b", re.IGNORECASE),
        ),
        aliases=("Fast API",),
    ),
    "Django": SkillDefinition(
        name="Django",
        category="Backend",
        patterns=(
            re.compile(r"\bdjango\b", re.IGNORECASE),
            re.compile(r"\bdrf\b", re.IGNORECASE),
        ),
        aliases=("Django REST Framework", "DRF"),
    ),
    "Flask": SkillDefinition(
        name="Flask",
        category="Backend",
        patterns=(
            re.compile(r"\bflask\b", re.IGNORECASE),
        ),
        aliases=(),
    ),
    "Node.js": SkillDefinition(
        name="Node.js",
        category="Backend",
        patterns=(
            re.compile(r"\b(?:node[\s\-_]*\.?js|nodejs)\b", re.IGNORECASE),
            re.compile(r"\bNode\s+(?:developer|engineer|backend|server|runtime|ecosystem|API)\b"),
            re.compile(
                r"(?:\b(?:React|Angular|Vue|Express|TypeScript|JavaScript|Python)\s*[/,]\s*Node\b|"
                r"\bNode\s*[/,]\s*(?:React|Angular|Vue|Express|TypeScript|JavaScript|Python)\b)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?i:(?:experience (?:with|in)|proficien(?:t in|cy with|cy in)|knowledge of))\s+Node\b"
            ),
        ),
        aliases=("NodeJS", "Node js", "Node"),
    ),
    "Express.js": SkillDefinition(
        name="Express.js",
        category="Backend",
        patterns=(
            re.compile(r"\b(?:express[\s\-_]*\.?js|expressjs)\b", re.IGNORECASE),
            re.compile(r"\bexpress\s+(?:framework|server|backend|middleware)\b", re.IGNORECASE),
            re.compile(
                r"(?:\b(?:Node|Node\.js|React|Mongo|MongoDB)\s*[/,]\s*Express\b|"
                r"\bExpress\s*[/,]\s*(?:Node|Node\.js|React|Mongo|MongoDB)\b)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?i:(?:experience (?:with|in)|proficien(?:t in|cy with|cy in)|knowledge of|using))\s+Express\b"
                r"(?!\s+(?:gratitude|interest|concern|delivery|mail|opinions?))"
            ),
        ),
        aliases=("ExpressJS", "Express js", "Express"),
    ),
    "Spring Boot": SkillDefinition(
        name="Spring Boot",
        category="Backend",
        patterns=(
            re.compile(r"\bspring[\s\-_]*(?:boot|framework|mvc|cloud|data|security)\b", re.IGNORECASE),
        ),
        aliases=("SpringBoot", "Spring Framework"),
    ),
    ".NET": SkillDefinition(
        name=".NET",
        category="Backend",
        patterns=(
            re.compile(r"(?i)(?:(?<![@/\w])\.net\b(?![/\w])|\bdotnet\b|\bdot[\s\-_]*net\b|\basp\.net\b)"),
        ),
        aliases=(".NET Core", "ASP.NET", "dotnet", "dot-net"),
    ),
    "Symfony": SkillDefinition(
        name="Symfony",
        category="Backend",
        patterns=(
            re.compile(r"\bsymfony\b", re.IGNORECASE),
        ),
        aliases=(),
    ),

    # =========================================================================
    # 4. Databases (8 skills)
    # =========================================================================
    "SQL": SkillDefinition(
        name="SQL",
        category="Databases",
        patterns=(
            re.compile(
                r"(?<!no[\s\-_])(?<!postgre\s)(?<!my\s)\bsql\b(?!\s*server\b)",
                re.IGNORECASE,
            ),
        ),
        aliases=("Structured Query Language",),
    ),
    "PostgreSQL": SkillDefinition(
        name="PostgreSQL",
        category="Databases",
        patterns=(
            re.compile(r"\b(?:postgres(?:ql)?|postgre\s+sql|psql)\b", re.IGNORECASE),
        ),
        aliases=("Postgres", "Postgre SQL", "psql"),
    ),
    "MySQL": SkillDefinition(
        name="MySQL",
        category="Databases",
        patterns=(
            re.compile(r"\bmy[\s\-_]*sql\b", re.IGNORECASE),
        ),
        aliases=("My SQL",),
    ),
    "MongoDB": SkillDefinition(
        name="MongoDB",
        category="Databases",
        patterns=(
            re.compile(r"\bmongo(?:[\s\-_]*db)?\b", re.IGNORECASE),
        ),
        aliases=("Mongo DB", "Mongo"),
    ),
    "Redis": SkillDefinition(
        name="Redis",
        category="Databases",
        patterns=(
            re.compile(r"\bredis\b", re.IGNORECASE),
        ),
        aliases=(),
    ),
    "SQLite": SkillDefinition(
        name="SQLite",
        category="Databases",
        patterns=(
            re.compile(r"\bsqlite(?:3)?\b", re.IGNORECASE),
        ),
        aliases=("SQLite3",),
    ),
    "Microsoft SQL Server": SkillDefinition(
        name="Microsoft SQL Server",
        category="Databases",
        patterns=(
            re.compile(r"\b(?:ms[\s\-_]*sql(?:\s*server)?|sql\s*server|microsoft\s+sql(?:\s*server)?)\b", re.IGNORECASE),
        ),
        aliases=("SQL Server", "MSSQL", "MS SQL", "MS SQL Server"),
    ),
    "Elasticsearch": SkillDefinition(
        name="Elasticsearch",
        category="Databases",
        patterns=(
            re.compile(r"\b(?:elastic[\s\-_]*search|elastic\s+stack|elk(?:\s*stack)?)\b", re.IGNORECASE),
        ),
        aliases=("Elastic Search", "ELK", "Elastic Stack"),
    ),

    # =========================================================================
    # 5. Cloud (3 skills)
    # =========================================================================
    "AWS": SkillDefinition(
        name="AWS",
        category="Cloud",
        patterns=(
            re.compile(r"\b(?:aws|amazon\s+web\s+services)\b", re.IGNORECASE),
        ),
        aliases=("Amazon Web Services", "Amazon AWS"),
    ),
    "Microsoft Azure": SkillDefinition(
        name="Microsoft Azure",
        category="Cloud",
        patterns=(
            re.compile(r"\b(?:microsoft\s+azure|ms\s+azure|azure)\b", re.IGNORECASE),
        ),
        aliases=("Azure", "MS Azure"),
    ),
    "Google Cloud": SkillDefinition(
        name="Google Cloud",
        category="Cloud",
        patterns=(
            re.compile(r"\b(?:gcp|google\s+cloud(?:\s+platform)?)\b", re.IGNORECASE),
        ),
        aliases=("GCP", "Google Cloud Platform"),
    ),

    # =========================================================================
    # 6. DevOps and Infrastructure (7 skills)
    # =========================================================================
    "Docker": SkillDefinition(
        name="Docker",
        category="DevOps and Infrastructure",
        patterns=(
            re.compile(r"\bdocker(?:ized|file|\s+compose)?\b", re.IGNORECASE),
        ),
        aliases=("Docker Compose", "Dockerfile"),
    ),
    "Kubernetes": SkillDefinition(
        name="Kubernetes",
        category="DevOps and Infrastructure",
        patterns=(
            re.compile(r"\b(?:kubernetes|k8s)\b", re.IGNORECASE),
        ),
        aliases=("K8s", "k8s"),
    ),
    "Terraform": SkillDefinition(
        name="Terraform",
        category="DevOps and Infrastructure",
        patterns=(
            re.compile(r"\bterraform\b", re.IGNORECASE),
        ),
        aliases=(),
    ),
    "Linux": SkillDefinition(
        name="Linux",
        category="DevOps and Infrastructure",
        patterns=(
            re.compile(r"\b(?:linux|ubuntu|debian|centos|redhat|rhel)\b", re.IGNORECASE),
        ),
        aliases=("Ubuntu", "Debian", "CentOS", "RedHat", "RHEL"),
    ),
    "Jenkins": SkillDefinition(
        name="Jenkins",
        category="DevOps and Infrastructure",
        patterns=(
            re.compile(r"\bjenkins\b", re.IGNORECASE),
        ),
        aliases=(),
    ),
    "GitHub Actions": SkillDefinition(
        name="GitHub Actions",
        category="DevOps and Infrastructure",
        patterns=(
            re.compile(r"\bgithub\s+actions\b", re.IGNORECASE),
        ),
        aliases=("Github Actions",),
    ),
    "CI/CD": SkillDefinition(
        name="CI/CD",
        category="DevOps and Infrastructure",
        patterns=(
            re.compile(
                r"\b(?:ci[\s\-_/]+cd|continuous\s+(?:integration|deployment|delivery))\b",
                re.IGNORECASE,
            ),
        ),
        aliases=("CI-CD", "CI CD", "Continuous Integration", "Continuous Deployment", "Continuous Delivery"),
    ),

    # =========================================================================
    # 7. Data Engineering (8 skills)
    # =========================================================================
    "Apache Spark": SkillDefinition(
        name="Apache Spark",
        category="Data Engineering",
        patterns=(
            re.compile(r"\bapache\s+spark\b", re.IGNORECASE),
            re.compile(r"\bspark\s+(?:streaming|sql|dataframes?|rdd|cluster|jobs?|pipelines?|core|framework)\b", re.IGNORECASE),
            re.compile(
                rf"(?:\b{_BIG_DATA_TOOLS}\s*[/,]\s*Spark\b|"
                rf"\bSpark\s*[/,]\s*{_BIG_DATA_TOOLS}\b)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?i:(?:experience (?:with|in)|proficien(?:t in|cy with|cy in)|knowledge of))\s+Spark\b"
            ),
        ),
        aliases=("Spark", "Spark SQL"),
    ),
    "Delta Lake": SkillDefinition(
        name="Delta Lake",
        category="Data Engineering",
        patterns=(
            re.compile(r"\bdelta[\s\-_]*lake\b", re.IGNORECASE),
            re.compile(
                r"(?:\b(?:Spark|Databricks|PySpark|Kafka|Flink|Hadoop|Lakehouse|Parquet)\s*[/,]\s*Delta\b|"
                r"\bDelta\s*[/,]\s*(?:Spark|Databricks|PySpark|Kafka|Flink|Hadoop|Lakehouse|Parquet)\b)",
                re.IGNORECASE,
            ),
            re.compile(r"\bDelta\s+(?:tables?|format|storage|architecture)\b", re.IGNORECASE),
        ),
        aliases=("Delta", "DeltaLake"),
    ),
    "PySpark": SkillDefinition(
        name="PySpark",
        category="Data Engineering",
        patterns=(
            re.compile(r"\bpyspark\b", re.IGNORECASE),
        ),
        aliases=("pyspark",),
    ),
    "Apache Kafka": SkillDefinition(
        name="Apache Kafka",
        category="Data Engineering",
        patterns=(
            re.compile(r"\b(?:apache\s+kafka|kafka)\b", re.IGNORECASE),
        ),
        aliases=("Kafka",),
    ),
    "Airflow": SkillDefinition(
        name="Airflow",
        category="Data Engineering",
        patterns=(
            re.compile(r"\b(?:apache\s+airflow|airflow)\b", re.IGNORECASE),
        ),
        aliases=("Apache Airflow",),
    ),
    "Databricks": SkillDefinition(
        name="Databricks",
        category="Data Engineering",
        patterns=(
            re.compile(r"\bdata[\s\-_]*bricks\b", re.IGNORECASE),
        ),
        aliases=("Data bricks",),
    ),
    "Snowflake": SkillDefinition(
        name="Snowflake",
        category="Data Engineering",
        patterns=(
            re.compile(r"\bsnowflake(?:\s*(?:db|data\s*warehouse))?\b", re.IGNORECASE),
        ),
        aliases=("Snowflake DB", "Snowflake Data Warehouse"),
    ),
    "dbt": SkillDefinition(
        name="dbt",
        category="Data Engineering",
        patterns=(
            re.compile(r"\b(?:dbt|data\s+build\s+tool)\b", re.IGNORECASE),
        ),
        aliases=("data build tool",),
    ),

    # =========================================================================
    # 8. Data Science and AI (10 skills)
    # =========================================================================
    "Machine Learning": SkillDefinition(
        name="Machine Learning",
        category="Data Science and AI",
        patterns=(
            re.compile(r"\bmachine[\s\-_]+learning\b", re.IGNORECASE),
            re.compile(r"\b(?:ai/ml|ml/ai|automl|mlops)\b", re.IGNORECASE),
            re.compile(
                r"\bML\s+(?:models?|algorithms?|pipelines?|engineers?|ops|frameworks?|"
                r"systems?|solutions?|methods?|techniques?|lifecycle|platform)\b"
            ),
            re.compile(
                r"(?:\b(?:AI|DL|NLP|DS)\s*[/,]\s*ML\b|\bML\s*[/,]\s*(?:AI|DL|NLP|DS)\b)"
            ),
            re.compile(
                r"(?i:(?:experience (?:with|in)|proficien(?:t in|cy with|cy in)|knowledge of))\s+ML\b"
            ),
        ),
        aliases=("ML", "MLOps", "AutoML"),
    ),
    "Deep Learning": SkillDefinition(
        name="Deep Learning",
        category="Data Science and AI",
        patterns=(
            re.compile(r"\bdeep[\s\-_]+learning\b", re.IGNORECASE),
            re.compile(r"\b(?:ai/dl|dl/ai|ml/dl)\b", re.IGNORECASE),
            re.compile(r"\bDL\s+(?:models?|frameworks?|engineers?)\b"),
            re.compile(r"(?i:(?:experience (?:with|in)|proficien(?:t in|cy with|cy in)|knowledge of))\s+DL\b"),
        ),
        aliases=("DL",),
    ),
    "Pandas": SkillDefinition(
        name="Pandas",
        category="Data Science and AI",
        patterns=(
            re.compile(r"\bpandas\b", re.IGNORECASE),
        ),
        aliases=(),
    ),
    "NumPy": SkillDefinition(
        name="NumPy",
        category="Data Science and AI",
        patterns=(
            re.compile(r"\bnumpy\b", re.IGNORECASE),
        ),
        aliases=("Numpy",),
    ),
    "Scikit-learn": SkillDefinition(
        name="Scikit-learn",
        category="Data Science and AI",
        patterns=(
            re.compile(r"\b(?:scikit[\s\-_]*learn|sklearn)\b", re.IGNORECASE),
        ),
        aliases=("Scikit learn", "sklearn"),
    ),
    "TensorFlow": SkillDefinition(
        name="TensorFlow",
        category="Data Science and AI",
        patterns=(
            re.compile(r"\btensor[\s\-_]*flow\b", re.IGNORECASE),
            re.compile(r"(?i:(?:experience (?:with|in)|proficien(?:t in|cy with|cy in)|knowledge of))\s+TF\b"),
        ),
        aliases=("Tensor Flow", "TF"),
    ),
    "PyTorch": SkillDefinition(
        name="PyTorch",
        category="Data Science and AI",
        patterns=(
            re.compile(r"\bpytorch\b", re.IGNORECASE),
        ),
        aliases=("Pytorch", "Torch"),
    ),
    "NLP": SkillDefinition(
        name="NLP",
        category="Data Science and AI",
        patterns=(
            re.compile(r"\b(?:natural\s+language\s+processing|nlp)\b", re.IGNORECASE),
        ),
        aliases=("Natural Language Processing",),
    ),
    "Generative AI": SkillDefinition(
        name="Generative AI",
        category="Data Science and AI",
        patterns=(
            re.compile(r"\b(?:generative\s+ai|gen[\s\-_]*ai)\b", re.IGNORECASE),
        ),
        aliases=("GenAI", "Gen-AI", "Gen AI"),
    ),
    "Large Language Models": SkillDefinition(
        name="Large Language Models",
        category="Data Science and AI",
        patterns=(
            re.compile(r"\b(?:large\s+language\s+models?|llms?)\b", re.IGNORECASE),
        ),
        aliases=("LLM", "LLMs", "Large Language Model"),
    ),

    # =========================================================================
    # 9. Version Control (3 skills)
    # =========================================================================
    "Git": SkillDefinition(
        name="Git",
        category="Version Control",
        patterns=(
            # Match 'git' but never 'github' or 'gitlab'
            re.compile(r"\bgit\b(?!\s*[-\.\s]?(?:hub|lab))", re.IGNORECASE),
        ),
        aliases=(),
    ),
    "GitHub": SkillDefinition(
        name="GitHub",
        category="Version Control",
        patterns=(
            re.compile(r"\bgit[\s\-_]*hub\b(?!\s*actions\b)", re.IGNORECASE),
        ),
        aliases=("Git Hub",),
    ),
    "GitLab": SkillDefinition(
        name="GitLab",
        category="Version Control",
        patterns=(
            re.compile(r"\bgit[\s\-_]*lab\b", re.IGNORECASE),
        ),
        aliases=("Git Lab",),
    ),
}


def extract_skills(text: Optional[str]) -> List[str]:
    """
    Extracts canonical technical skill names from freeform text.

    Args:
        text: Freeform text string (e.g. job description, requirements list, or tags).
              Safely handles None, non-string, and empty input.

    Returns:
        A deduplicated, alphabetically sorted list of canonical skill names matched in the text.
        Returns an empty list if no skills are detected or if input is empty/invalid.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return []

    matched_skills: Set[str] = set()

    for skill in SKILL_TAXONOMY.values():
        for pattern in skill.patterns:
            if pattern.search(text):
                matched_skills.add(skill.name)
                break

    return sorted(matched_skills)


def extract_skills_by_category(text: Optional[str]) -> Dict[str, List[str]]:
    """
    Extracts canonical technical skill names grouped by taxonomy category.

    Args:
        text: Freeform text string to analyze.

    Returns:
        A dictionary mapping each taxonomy category to a list of matched canonical skills.
        Only categories with at least one matched skill are included.
    """
    skills = extract_skills(text)
    if not skills:
        return {}

    categorized: Dict[str, List[str]] = {}
    for skill_name in skills:
        category = SKILL_TAXONOMY[skill_name].category
        categorized.setdefault(category, []).append(skill_name)

    return categorized


def get_taxonomy() -> Dict[str, SkillDefinition]:
    """Returns the full dictionary of curated skill definitions."""
    return SKILL_TAXONOMY


def get_categories() -> List[str]:
    """Returns the list of all defined skill categories."""
    return list(TAXONOMY_CATEGORIES)


def get_all_canonical_skills() -> List[str]:
    """Returns an alphabetically sorted list of all 66 canonical skill names in the taxonomy."""
    return sorted(SKILL_TAXONOMY.keys())


def get_skills_for_category(category: str) -> List[str]:
    """
    Returns canonical skill names belonging to the specified category.

    Args:
        category: Exact category name from TAXONOMY_CATEGORIES.

    Returns:
        Sorted list of canonical skill names, or empty list if category does not exist.
    """
    return sorted([s.name for s in SKILL_TAXONOMY.values() if s.category == category])
