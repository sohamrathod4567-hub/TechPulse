"""
Unit tests for the Technical Skill Extraction and Taxonomy module.

Tests taxonomy completeness, canonical skill detection, alias normalization,
case-insensitivity, deduplication, deterministic output, error handling,
and rigorous false-positive prevention across all 9 categories.
"""

from __future__ import annotations

import unittest
from typing import List

from techpulse.etl.skill_extractor import (
    SKILL_TAXONOMY,
    TAXONOMY_CATEGORIES,
    extract_skills,
    extract_skills_by_category,
    get_all_canonical_skills,
    get_categories,
    get_skills_for_category,
    get_taxonomy,
)


class TestSkillTaxonomyStructure(unittest.TestCase):
    """Tests verifying the integrity and structure of the skill taxonomy."""

    def test_taxonomy_total_skills_count(self) -> None:
        """Verify the taxonomy contains exactly 66 skills."""
        self.assertEqual(len(SKILL_TAXONOMY), 66)

    def test_taxonomy_categories_count(self) -> None:
        """Verify the taxonomy defines exactly 9 distinct categories."""
        self.assertEqual(len(TAXONOMY_CATEGORIES), 9)

    def test_category_skill_distribution(self) -> None:
        """Verify each category contains the exact expected count of skills."""
        expected_counts = {
            "Programming Languages": 12,
            "Frontend": 7,
            "Backend": 8,
            "Databases": 8,
            "Cloud": 3,
            "DevOps and Infrastructure": 7,
            "Data Engineering": 8,
            "Data Science and AI": 10,
            "Version Control": 3,
        }
        actual_counts = {cat: 0 for cat in TAXONOMY_CATEGORIES}
        for skill in SKILL_TAXONOMY.values():
            self.assertIn(skill.category, actual_counts, f"Skill {skill.name} has unknown category {skill.category}")
            actual_counts[skill.category] += 1

        self.assertEqual(actual_counts, expected_counts)

    def test_skill_definition_fields(self) -> None:
        """Verify every skill has non-empty patterns and valid metadata."""
        for name, skill in SKILL_TAXONOMY.items():
            self.assertEqual(name, skill.name)
            self.assertIn(skill.category, TAXONOMY_CATEGORIES)
            self.assertGreater(len(skill.patterns), 0, f"{name} has no matching patterns")
            self.assertIsInstance(skill.aliases, tuple)

    def test_helper_get_taxonomy(self) -> None:
        """Verify get_taxonomy returns the taxonomy dictionary."""
        taxonomy = get_taxonomy()
        self.assertEqual(len(taxonomy), 66)
        self.assertIn("Python", taxonomy)
        self.assertIn("SQL", taxonomy)
        self.assertIn("Delta Lake", taxonomy)

    def test_helper_get_categories(self) -> None:
        """Verify get_categories returns the 9 categories."""
        categories = get_categories()
        self.assertEqual(len(categories), 9)
        self.assertIn("Programming Languages", categories)
        self.assertIn("Databases", categories)

    def test_helper_get_all_canonical_skills(self) -> None:
        """Verify get_all_canonical_skills returns sorted list of 66 skills."""
        all_skills = get_all_canonical_skills()
        self.assertEqual(len(all_skills), 66)
        self.assertEqual(all_skills, sorted(all_skills))
        self.assertIn("PostgreSQL", all_skills)
        self.assertIn("SQL", all_skills)
        self.assertIn("Delta Lake", all_skills)

    def test_helper_get_skills_for_category(self) -> None:
        """Verify get_skills_for_category filters correctly."""
        db_skills = get_skills_for_category("Databases")
        self.assertEqual(len(db_skills), 8)
        self.assertIn("PostgreSQL", db_skills)
        self.assertIn("MySQL", db_skills)
        self.assertIn("MongoDB", db_skills)
        self.assertIn("SQL", db_skills)

        de_skills = get_skills_for_category("Data Engineering")
        self.assertEqual(len(de_skills), 8)
        self.assertIn("Delta Lake", de_skills)
        self.assertIn("Apache Spark", de_skills)

        empty_skills = get_skills_for_category("NonExistentCategory")
        self.assertEqual(empty_skills, [])


class TestCanonicalSkillExtraction(unittest.TestCase):
    """Tests verifying extraction of skills from all 9 categories."""

    def test_programming_languages(self) -> None:
        """Verify all 12 programming languages are detected."""
        text = (
            "We use Python, Java, JavaScript, TypeScript, C#, C++, Go, "
            "PHP, Ruby, Kotlin, Swift, and R for our development."
        )
        skills = extract_skills(text)
        expected = [
            "C#", "C++", "Go", "Java", "JavaScript", "Kotlin",
            "PHP", "Python", "R", "Ruby", "Swift", "TypeScript"
        ]
        self.assertEqual(skills, sorted(expected))

    def test_frontend_skills(self) -> None:
        """Verify all 7 frontend skills are detected."""
        text = "Frontend stack includes React, Angular, Vue.js, Next.js, HTML, CSS, and Tailwind CSS."
        skills = extract_skills(text)
        expected = ["Angular", "CSS", "HTML", "Next.js", "React", "Tailwind CSS", "Vue.js"]
        self.assertEqual(skills, sorted(expected))

    def test_backend_skills(self) -> None:
        """Verify all 8 backend skills are detected."""
        text = "Backend services built with FastAPI, Django, Flask, Node.js, Express.js, Spring Boot, .NET, and Symfony."
        skills = extract_skills(text)
        expected = [".NET", "Django", "Express.js", "FastAPI", "Flask", "Node.js", "Spring Boot", "Symfony"]
        self.assertEqual(skills, sorted(expected))

    def test_database_skills(self) -> None:
        """Verify all 8 database skills are detected."""
        text = "Databases: PostgreSQL, MySQL, MongoDB, Redis, SQLite, Microsoft SQL Server, Elasticsearch, and SQL."
        skills = extract_skills(text)
        expected = ["Elasticsearch", "Microsoft SQL Server", "MongoDB", "MySQL", "PostgreSQL", "Redis", "SQL", "SQLite"]
        self.assertEqual(skills, sorted(expected))

    def test_cloud_skills(self) -> None:
        """Verify all 3 cloud platforms are detected."""
        text = "Cloud architecture spans AWS, Microsoft Azure, and Google Cloud."
        skills = extract_skills(text)
        expected = ["AWS", "Google Cloud", "Microsoft Azure"]
        self.assertEqual(skills, sorted(expected))

    def test_devops_and_infrastructure(self) -> None:
        """Verify all 7 DevOps skills are detected."""
        text = "Infrastructure with Docker, Kubernetes, Terraform, Linux, Jenkins, GitHub Actions, and CI/CD."
        skills = extract_skills(text)
        expected = ["CI/CD", "Docker", "GitHub Actions", "Jenkins", "Kubernetes", "Linux", "Terraform"]
        self.assertEqual(skills, sorted(expected))

    def test_data_engineering(self) -> None:
        """Verify all 8 Data Engineering skills are detected."""
        text = "Data pipelines built with Apache Spark, PySpark, Apache Kafka, Airflow, Databricks, Snowflake, dbt, and Delta Lake."
        skills = extract_skills(text)
        expected = ["Airflow", "Apache Kafka", "Apache Spark", "Databricks", "Delta Lake", "PySpark", "Snowflake", "dbt"]
        self.assertEqual(skills, sorted(expected))

    def test_data_science_and_ai(self) -> None:
        """Verify all 10 Data Science & AI skills are detected."""
        text = (
            "Experience with Machine Learning, Deep Learning, Pandas, NumPy, Scikit-learn, "
            "TensorFlow, PyTorch, NLP, Generative AI, and Large Language Models."
        )
        skills = extract_skills(text)
        expected = [
            "Deep Learning", "Generative AI", "Large Language Models", "Machine Learning",
            "NLP", "NumPy", "Pandas", "PyTorch", "Scikit-learn", "TensorFlow"
        ]
        self.assertEqual(skills, sorted(expected))

    def test_version_control(self) -> None:
        """Verify all 3 version control skills are detected."""
        text = "We manage source code using Git, GitHub, and GitLab."
        skills = extract_skills(text)
        expected = ["Git", "GitHub", "GitLab"]
        self.assertEqual(skills, sorted(expected))


class TestAliasNormalization(unittest.TestCase):
    """Tests verifying aliases and variants normalize to canonical skill names."""

    def test_database_aliases(self) -> None:
        """Verify Postgres, Postgre SQL, and psql map to PostgreSQL."""
        self.assertEqual(extract_skills("Proficiency with Postgres"), ["PostgreSQL"])
        self.assertEqual(extract_skills("Experience with Postgre SQL"), ["PostgreSQL"])
        self.assertEqual(extract_skills("Using psql CLI"), ["PostgreSQL"])

    def test_cloud_aliases(self) -> None:
        """Verify GCP and Azure abbreviations map to canonical names."""
        self.assertEqual(extract_skills("Deployed on GCP"), ["Google Cloud"])
        self.assertEqual(extract_skills("Azure cloud solutions"), ["Microsoft Azure"])
        self.assertEqual(extract_skills("Amazon Web Services architect"), ["AWS"])

    def test_devops_aliases(self) -> None:
        """Verify K8s maps to Kubernetes and Ubuntu maps to Linux."""
        self.assertEqual(extract_skills("Managing K8s clusters"), ["Kubernetes"])
        self.assertEqual(extract_skills("Linux administration on Ubuntu"), ["Linux"])
        self.assertEqual(extract_skills("CI/CD pipeline with continuous delivery"), ["CI/CD"])

    def test_programming_aliases(self) -> None:
        """Verify Golang, C#, and C++ aliases map correctly."""
        self.assertEqual(extract_skills("Senior Golang developer"), ["Go"])
        self.assertEqual(extract_skills("Backend in c-sharp"), ["C#"])
        self.assertEqual(extract_skills("Systems code in cpp"), ["C++"])
        self.assertEqual(extract_skills("Python3 scripting"), ["Python"])

    def test_frontend_backend_aliases(self) -> None:
        """Verify React.js, NextJS, VueJS, and .NET Core aliases."""
        self.assertEqual(extract_skills("React.js and NextJS"), ["Next.js", "React"])
        self.assertEqual(extract_skills("VueJS components with TailwindCSS"), ["Tailwind CSS", "Vue.js"])
        self.assertEqual(extract_skills("Backend service in .NET Core"), [".NET"])
        self.assertEqual(extract_skills("Fast API microservice"), ["FastAPI"])

    def test_data_and_ai_aliases(self) -> None:
        """Verify ML, LLMs, GenAI, and sklearn aliases."""
        self.assertEqual(extract_skills("MLOps engineer with AutoML"), ["Machine Learning"])
        self.assertEqual(extract_skills("Building with LLMs and GenAI"), ["Generative AI", "Large Language Models"])
        self.assertEqual(extract_skills("Using sklearn and Numpy"), ["NumPy", "Scikit-learn"])


class TestFalsePositivePrevention(unittest.TestCase):
    """Critical tests verifying prevention of common false positives."""

    def test_java_vs_javascript(self) -> None:
        """Verify JavaScript never matches Java."""
        self.assertEqual(extract_skills("JavaScript and TypeScript developer"), ["JavaScript", "TypeScript"])
        self.assertEqual(extract_skills("Looking for a Java and JavaScript developer"), ["Java", "JavaScript"])
        self.assertEqual(extract_skills("Java/JavaScript experience"), ["Java", "JavaScript"])
        self.assertEqual(extract_skills("Proficient in Java Script"), ["JavaScript"])

    def test_git_vs_github_and_gitlab(self) -> None:
        """Verify GitHub and GitLab never falsely trigger Git."""
        self.assertEqual(extract_skills("Experience with GitHub and GitLab"), ["GitHub", "GitLab"])
        self.assertEqual(extract_skills("Experience with Git and GitHub"), ["Git", "GitHub"])
        self.assertEqual(extract_skills("Daily use of git-hub and gitlab"), ["GitHub", "GitLab"])
        self.assertEqual(extract_skills("Proficiency with Git workflow"), ["Git"])

    def test_go_in_ordinary_english(self) -> None:
        """Verify English 'go' does not falsely trigger Go programming language."""
        english_sentences = [
            "Ready to go to the market",
            "On the go mobile solutions for field teams",
            "We go beyond what is expected",
            "Let us go forward together",
            "Where ideas go to grow",
            "You are a real go-getter",
            "Go above and beyond expectations",
            "Ready to go with the rest of the team",
            "How far would you go to solve a problem",
        ]
        for sentence in english_sentences:
            with self.subTest(sentence=sentence):
                self.assertNotIn("Go", extract_skills(sentence), f"False positive Go in: '{sentence}'")

        # Valid Go technical contexts
        self.assertIn("Go", extract_skills("Looking for a Go developer"))
        self.assertIn("Go", extract_skills("Golang backend engineer"))
        self.assertIn("Go", extract_skills("Python/Go experience"))
        self.assertIn("Go", extract_skills("Proficient in Go and Docker"))
        self.assertIn("Go", extract_skills("Microservices written in Go"))

    def test_react_as_english_verb(self) -> None:
        """Verify English verb 'react' does not trigger React framework."""
        verb_sentences = [
            "able to think on your feet and react quickly and calmly under pressure",
            "must react fast to customer complaints",
            "ability to react to changes in the market",
            "react promptly when incidents occur",
            "react appropriately in stressful situations",
            "how you react under tight deadlines",
            "ability to react positively to feedback",
        ]
        for sentence in verb_sentences:
            with self.subTest(sentence=sentence):
                self.assertNotIn("React", extract_skills(sentence), f"False positive React in: '{sentence}'")

        # Valid React technical contexts
        self.assertIn("React", extract_skills("Looking for a React developer"))
        self.assertIn("React", extract_skills("Frontend: React.js and TypeScript"))
        self.assertIn("React", extract_skills("Experience with React Native"))
        self.assertIn("React", extract_skills("React, Node.js, and PostgreSQL"))
        self.assertIn("React", extract_skills("• React\n• Python\n• Docker"))

    def test_machine_learning_vs_ml_units(self) -> None:
        """Verify 'ml' units of measurement do not trigger Machine Learning."""
        unit_sentences = [
            "Take 100 ml with water twice daily",
            "500ml bottle of liquid",
            "Document format is HTML and XML",
            "Dilute with 50 ml solution",
        ]
        for sentence in unit_sentences:
            with self.subTest(sentence=sentence):
                self.assertNotIn("Machine Learning", extract_skills(sentence))

        # Valid ML contexts
        self.assertIn("Machine Learning", extract_skills("Machine Learning engineer"))
        self.assertIn("Machine Learning", extract_skills("Developing AI/ML models"))
        self.assertIn("Machine Learning", extract_skills("Production ML pipelines"))

    def test_nextjs_vs_english_next(self) -> None:
        """Verify English word 'next' does not trigger Next.js."""
        english_sentences = [
            "The next step in the pipeline",
            "See what comes next week",
            "Take your career to the next level",
            "Next generation architecture",
        ]
        for sentence in english_sentences:
            with self.subTest(sentence=sentence):
                self.assertNotIn("Next.js", extract_skills(sentence))

        self.assertIn("Next.js", extract_skills("Fullstack app using Next.js"))
        self.assertIn("Next.js", extract_skills("NextJS with React and TypeScript"))

    def test_spring_boot_vs_english_spring(self) -> None:
        """Verify English word 'spring' does not trigger Spring Boot."""
        english_sentences = [
            "Starting in the spring of 2024",
            "Annual spring cleaning of legacy code",
            "A spring in your step",
        ]
        for sentence in english_sentences:
            with self.subTest(sentence=sentence):
                self.assertNotIn("Spring Boot", extract_skills(sentence))

        self.assertIn("Spring Boot", extract_skills("Java backend with Spring Boot"))
        self.assertIn("Spring Boot", extract_skills("Experience with Spring Framework"))

    def test_express_vs_english_express(self) -> None:
        """Verify English word 'express' does not trigger Express.js."""
        english_sentences = [
            "Please express your interest in this position",
            "Express delivery of high-quality products",
            "Express gratitude to teammates",
        ]
        for sentence in english_sentences:
            with self.subTest(sentence=sentence):
                self.assertNotIn("Express.js", extract_skills(sentence))

        self.assertIn("Express.js", extract_skills("Node.js and Express.js backend"))
        self.assertIn("Express.js", extract_skills("Node/Express REST APIs"))

    def test_r_vs_single_letters(self) -> None:
        """Verify single letter R in English and R&D do not trigger R language."""
        non_r_sentences = [
            "We bring extensive experience in R&D.",
            "Experience in R&D, technical innovation, and commercialisation.",
            "Experience in R & D operations",
            "Extensive experience in R/D",
            "Knowledge of R&D processes",
            "Member of our R&D team",
            "Toys R Us retail experience",
            "Dear Sir / Madam,",
        ]
        for sentence in non_r_sentences:
            with self.subTest(sentence=sentence):
                self.assertNotIn("R", extract_skills(sentence), f"False positive R on: '{sentence}'")

        # True positive cases for R
        self.assertIn("R", extract_skills("Experience with R programming for data analysis"))
        self.assertIn("R", extract_skills("Experience in R for data science"))
        self.assertIn("R", extract_skills("Knowledge of R language"))
        self.assertIn("R", extract_skills("Proficient in RStudio"))
        self.assertIn("R", extract_skills("Data analysis using Python, R, and SQL"))
        self.assertIn("R", extract_skills("R and Python data pipelines"))

    def test_standalone_sql_and_nosql(self) -> None:
        """Verify standalone SQL recognition while avoiding NoSQL and properly handling SQL Server."""
        # Standalone SQL mentions
        self.assertEqual(extract_skills("Experience with SQL required."), ["SQL"])
        self.assertEqual(extract_skills("Strong SQL queries and optimization."), ["SQL"])
        self.assertEqual(extract_skills("Python, SQL, and Tableau."), ["Python", "SQL"])
        self.assertEqual(extract_skills("Writing complex SQL."), ["SQL"])
        self.assertEqual(extract_skills("Knowledge of SQL databases."), ["SQL"])

        # NoSQL avoidance
        self.assertEqual(extract_skills("NoSQL database experience"), [])
        self.assertEqual(extract_skills("MongoDB and NoSQL systems"), ["MongoDB"])
        self.assertEqual(extract_skills("No-SQL data stores"), [])
        self.assertEqual(extract_skills("No SQL experience"), [])
        self.assertEqual(extract_skills("nosql technologies"), [])

        # SQL Server properly recognized as Microsoft SQL Server (not standalone SQL alone)
        self.assertEqual(extract_skills("Experience with SQL Server 2019"), ["Microsoft SQL Server"])
        self.assertEqual(extract_skills("MS SQL Server administration"), ["Microsoft SQL Server"])
        self.assertEqual(extract_skills("SQL Server and PostgreSQL"), ["Microsoft SQL Server", "PostgreSQL"])
        self.assertEqual(extract_skills("Experience with SQL Server and SQL queries"), ["Microsoft SQL Server", "SQL"])

        # PostgreSQL and MySQL (not triggering standalone SQL)
        self.assertEqual(extract_skills("PostgreSQL and MySQL developer"), ["MySQL", "PostgreSQL"])
        self.assertEqual(extract_skills("PostgreSQL, MySQL, and SQL"), ["MySQL", "PostgreSQL", "SQL"])

    def test_spark_and_delta_lake_french_and_english(self) -> None:
        """Verify Apache Spark and Delta Lake co-occurrence in French/English alongside ordinary spark protections."""
        # French phrasing from production data
        french_text = "Diffuser les bonnes pratiques Spark / Delta au sein de l'équipe et accompagner sa montée en compétences"
        french_skills = extract_skills(french_text)
        self.assertIn("Apache Spark", french_skills)
        self.assertIn("Delta Lake", french_skills)

        # Delta Lake pairings and variants
        self.assertEqual(extract_skills("Spark / Delta Lake architecture"), ["Apache Spark", "Delta Lake"])
        self.assertEqual(extract_skills("Building lakehouse with Delta Lake"), ["Delta Lake"])
        self.assertEqual(extract_skills("Using Delta tables with Databricks"), ["Databricks", "Delta Lake"])

        # Ordinary English uses of "spark" (should NOT trigger Apache Spark)
        spark_fp_sentences = [
            "Our diversity sparks curiosity, insight and openness",
            "The trade crisis sparked by tariffs",
            "Looking for candidates who spark innovation",
            "To spark an interest in technology",
            "Accounts at Sparkasse bank",
        ]
        for sentence in spark_fp_sentences:
            with self.subTest(sentence=sentence):
                self.assertNotIn("Apache Spark", extract_skills(sentence), f"False positive Apache Spark on: '{sentence}'")

    def test_dotnet_vs_domain_names(self) -> None:
        """Verify email and web addresses with .net do not trigger .NET."""
        domain_sentences = [
            "Send applications to careers@company.net",
            "Visit https://example.net/careers for info",
        ]
        for sentence in domain_sentences:
            with self.subTest(sentence=sentence):
                self.assertNotIn(".NET", extract_skills(sentence))

        self.assertIn(".NET", extract_skills("Enterprise software using C# and .NET Core"))

    def test_apache_spark_vs_spark_verb(self) -> None:
        """Verify English verb 'spark' does not trigger Apache Spark."""
        english_sentences = [
            "Looking for candidates who spark innovation",
            "To spark an interest in technology",
            "Accounts at Sparkasse bank",
        ]
        for sentence in english_sentences:
            with self.subTest(sentence=sentence):
                self.assertNotIn("Apache Spark", extract_skills(sentence))

        self.assertIn("Apache Spark", extract_skills("Big data processing with Apache Spark and PySpark"))
        self.assertIn("Apache Spark", extract_skills("Data pipelines using Kafka, Spark, and Hadoop"))

    def test_nodejs_vs_cluster_node(self) -> None:
        """Verify 'worker node' in clusters does not trigger Node.js."""
        self.assertNotIn("Node.js", extract_skills("Deploy pods across every worker node in Kubernetes"))
        self.assertIn("Node.js", extract_skills("Backend service with Node.js and TypeScript"))

    def test_swift_vs_swift_adjective(self) -> None:
        """Verify English adjective 'swift' does not trigger Swift programming."""
        self.assertNotIn("Swift", extract_skills("Swift turnaround time and prompt responses"))
        self.assertIn("Swift", extract_skills("iOS applications developed in Swift and SwiftUI"))


class TestEdgeCasesAndDeduplication(unittest.TestCase):
    """Tests verifying input handling, formatting resilience, and deduplication."""

    def test_empty_and_none_input(self) -> None:
        """Verify None, empty string, and whitespace return empty list."""
        self.assertEqual(extract_skills(None), [])
        self.assertEqual(extract_skills(""), [])
        self.assertEqual(extract_skills("   \n\t  "), [])
        self.assertEqual(extract_skills(123), [])  # type: ignore[arg-type]
        self.assertEqual(extract_skills([]), [])  # type: ignore[arg-type]

    def test_deduplication(self) -> None:
        """Verify multiple mentions of the same skill produce a single entry."""
        text = "Python is our primary language. We love Python. Python 3 all day. Pythonic Python."
        skills = extract_skills(text)
        self.assertEqual(skills, ["Python"])

    def test_case_insensitivity(self) -> None:
        """Verify skills are detected regardless of casing."""
        self.assertEqual(extract_skills("docker"), ["Docker"])
        self.assertEqual(extract_skills("DOCKER"), ["Docker"])
        self.assertEqual(extract_skills("DoCkEr"), ["Docker"])

    def test_punctuation_and_formatting(self) -> None:
        """Verify bullet points, slashes, and punctuation are handled cleanly."""
        text = "• Python/Django\n• PostgreSQL/Redis\n• Docker/Kubernetes\n• CI/CD"
        skills = extract_skills(text)
        expected = ["CI/CD", "Django", "Docker", "Kubernetes", "PostgreSQL", "Python", "Redis"]
        self.assertEqual(skills, sorted(expected))

    def test_extract_skills_by_category(self) -> None:
        """Verify extract_skills_by_category groups skills correctly."""
        text = "Building a React and FastAPI application on AWS with PostgreSQL."
        by_cat = extract_skills_by_category(text)
        expected = {
            "Frontend": ["React"],
            "Backend": ["FastAPI"],
            "Databases": ["PostgreSQL"],
            "Cloud": ["AWS"],
        }
        self.assertEqual(by_cat, expected)

    def test_extract_skills_by_category_empty(self) -> None:
        """Verify extract_skills_by_category on empty text returns empty dict."""
        self.assertEqual(extract_skills_by_category(None), {})
        self.assertEqual(extract_skills_by_category(""), {})
        self.assertEqual(extract_skills_by_category("No technical keywords here."), {})


if __name__ == "__main__":
    unittest.main()
