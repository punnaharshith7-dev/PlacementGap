from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).parent / "data"
CATEGORIES: dict[str, str] = {
    "programming": """
Python Java JavaScript TypeScript C C++ C# Go Rust Kotlin Swift PHP Ruby Scala R MATLAB Bash PowerShell SQL HTML CSS Solidity Lua Dart Elixir Haskell Julia Perl Assembly Groovy Objective-C F# Fortran COBOL WebAssembly
""",
    "computer_science": """
Data Structures Algorithms Data Structures and Algorithms Object-Oriented Programming Functional Programming Programming Paradigms Discrete Mathematics Logic and Proofs Linear Algebra Calculus Operating Systems Computer Architecture Computer Networks Distributed Systems Compilers Programming Languages Theory of Computation Complexity Analysis Concurrency Parallel Computing Memory Management File Systems Cryptography Graph Theory Combinatorics Information Theory
""",
    "software_engineering": """
Software Design System Design Domain-Driven Design Design Patterns Clean Code Refactoring Code Review Version Control Git GitHub GitLab Agile Scrum Kanban Requirements Engineering Technical Writing API Design Microservices Monolith Architecture Event-Driven Architecture Message Queues Reliability Engineering Site Reliability Engineering Observability Capacity Planning Performance Engineering Feature Flags Backward Compatibility
""",
    "web_frontend": """
React Angular Vue Svelte Next.js Remix Astro Vite Web Components DOM Accessibility Responsive Design Browser APIs Progressive Web Apps Web Performance State Management Redux Zustand TanStack Query Tailwind CSS Sass CSS Grid Flexbox Webpack JavaScript Testing Storybook
""",
    "backend_api": """
FastAPI Django Flask Node.js Express NestJS Spring Boot ASP.NET Core Ruby on Rails Laravel REST APIs GraphQL gRPC Authentication Authorization OAuth OpenID Connect WebSockets Server-Sent Events API Security Rate Limiting Input Validation Background Jobs Caching Redis API Documentation OpenAPI
""",
    "database_data_engineering": """
PostgreSQL MySQL SQLite Microsoft SQL Server Oracle Database MongoDB DynamoDB Cassandra Elasticsearch Redis Neo4j Database Design Database Indexing Query Optimization Transactions Data Modeling Data Warehousing ETL ELT Apache Spark Apache Kafka Apache Airflow dbt Data Lakes Data Quality Data Governance Stream Processing
""",
    "cloud_devops": """
Amazon Web Services Microsoft Azure Google Cloud Platform Docker Kubernetes Helm Terraform Pulumi Ansible Linux Nginx GitHub Actions GitLab CI Jenkins Continuous Integration Continuous Delivery Infrastructure as Code Cloud Networking Serverless Computing AWS Lambda Azure Functions Google Cloud Run Prometheus Grafana OpenTelemetry Jaeger Logging Monitoring Alerting Secrets Management Container Security
""",
    "data_science_analytics": """
Statistics Probability Hypothesis Testing Experimental Design A/B Testing Regression Analysis Time Series Analysis Bayesian Statistics Causal Inference Data Visualization Tableau Power BI Looker Matplotlib Seaborn Plotly Pandas NumPy Jupyter Notebooks Feature Engineering Data Cleaning Exploratory Data Analysis Business Intelligence Data Storytelling Forecasting
""",
    "machine_learning": """
Machine Learning Deep Learning Supervised Learning Unsupervised Learning Reinforcement Learning Neural Networks Convolutional Neural Networks Recurrent Neural Networks Transformers Natural Language Processing Computer Vision Recommendation Systems Information Retrieval Search Ranking Model Evaluation Model Selection Hyperparameter Tuning Scikit-learn PyTorch TensorFlow XGBoost LightGBM MLflow Model Serving MLOps Data Labeling Transfer Learning Graph Neural Networks
""",
    "generative_ai": """
Large Language Models Prompt Engineering Retrieval-Augmented Generation Vector Databases Embeddings Semantic Search AI Agents Tool Calling Fine-Tuning LoRA Quantization Evaluation of Language Models Guardrails Responsible AI Multimodal AI Speech Recognition Text-to-Speech Document Parsing OCR LangChain LangGraph LiteLLM Hugging Face Diffusion Models
""",
    "security_networking": """
Application Security Threat Modeling Secure Coding Vulnerability Management Penetration Testing OWASP Top 10 Web Security Network Security Identity and Access Management Public Key Infrastructure TLS Security Auditing Incident Response Digital Forensics Security Operations Zero Trust Privacy Engineering Data Protection Malware Analysis Static Analysis Dynamic Analysis Software Supply Chain Security SAST DAST Secrets Scanning Firewall Configuration
""",
    "mobile_embedded": """
Android Development iOS Development React Native Flutter SwiftUI Jetpack Compose Mobile UX Mobile App Security Embedded Systems Firmware Development Internet of Things Microcontrollers Arduino Raspberry Pi Real-Time Systems Robotics Computer Vision Edge Computing Bluetooth Low Energy
""",
    "quality_tooling": """
Unit Testing Integration Testing End-to-End Testing Property-Based Testing Mutation Testing Test-Driven Development Behavior-Driven Development Pytest Jest Vitest Playwright Cypress Selenium Contract Testing Load Testing Chaos Engineering Test Automation Debugging Profiling Static Type Checking Mypy Ruff ESLint Prettier
""",
    "product_communication": """
Technical Leadership Mentoring Stakeholder Communication Product Thinking Project Management Prioritization Estimation Problem Solving Collaboration Written Communication Presentation Skills User Research Product Analytics UX Research Human-Computer Interaction Ethics in Technology Accessibility Engineering
""",
}

CURATED = {
    "Data Structures and Algorithms": ["DSA", "algos", "data structures & algorithms"],
    "Data Structures": ["CS201 Data Structures", "data structure"],
    "Machine Learning": ["ML", "statistical learning"],
    "Natural Language Processing": ["NLP", "computational linguistics", "language processing"],
    "Computer Vision": ["CV", "image understanding"],
    "Large Language Models": ["LLM", "LLMs", "foundation models"],
    "Retrieval-Augmented Generation": ["RAG", "retrieval augmented generation"],
    "Amazon Web Services": ["AWS", "amazon cloud", "amazon web services cloud"],
    "Microsoft Azure": ["Azure", "MS Azure"],
    "Google Cloud Platform": ["GCP", "Google Cloud"],
    "Continuous Integration": ["CI", "build integration"],
    "Continuous Delivery": ["CD", "continuous deployment"],
    "Object-Oriented Programming": ["OOP", "object oriented programming"],
    "Application Programming Interfaces": ["API", "APIs"],
    "REST APIs": ["REST", "RESTful APIs"],
    "Artificial Intelligence Agents": ["AI agents", "agentic workflows"],
    "PostgreSQL": ["Postgres", "psql"],
    "JavaScript": ["JS", "ECMAScript"],
    "TypeScript": ["TS"],
    "C++": ["cpp", "cplusplus"],
    "C#": ["C sharp", "dotnet C sharp"],
}

MULTIWORD = """
Data Structures and Algorithms; Data Structures; Object-Oriented Programming; Functional Programming; Programming Paradigms; Discrete Mathematics; Logic and Proofs; Linear Algebra; Computer Architecture; Computer Networks; Distributed Systems; Theory of Computation; Complexity Analysis; Parallel Computing; Memory Management; File Systems; Information Theory; Software Design; System Design; Domain-Driven Design; Design Patterns; Clean Code; Code Review; Version Control; Requirements Engineering; Technical Writing; API Design; Monolith Architecture; Event-Driven Architecture; Message Queues; Reliability Engineering; Site Reliability Engineering; Capacity Planning; Performance Engineering; Feature Flags; Backward Compatibility; Web Components; Responsive Design; Browser APIs; Progressive Web Apps; Web Performance; State Management; CSS Grid; Spring Boot; ASP.NET Core; Ruby on Rails; REST APIs; OpenID Connect; Server-Sent Events; Input Validation; Background Jobs; API Documentation; Database Design; Database Indexing; Query Optimization; Data Modeling; Data Warehousing; Apache Spark; Apache Kafka; Apache Airflow; Data Lakes; Data Quality; Data Governance; Stream Processing; Microsoft SQL Server; Oracle Database; Amazon Web Services; Microsoft Azure; Google Cloud Platform; GitHub Actions; GitLab CI; Continuous Integration; Continuous Delivery; Infrastructure as Code; Cloud Networking; Serverless Computing; Azure Functions; Google Cloud Run; Secrets Management; Container Security; Hypothesis Testing; Experimental Design; A/B Testing; Regression Analysis; Time Series Analysis; Bayesian Statistics; Causal Inference; Data Visualization; Power BI; Jupyter Notebooks; Feature Engineering; Data Cleaning; Exploratory Data Analysis; Business Intelligence; Data Storytelling; Machine Learning; Deep Learning; Supervised Learning; Unsupervised Learning; Reinforcement Learning; Neural Networks; Convolutional Neural Networks; Recurrent Neural Networks; Natural Language Processing; Computer Vision; Recommendation Systems; Information Retrieval; Search Ranking; Model Evaluation; Model Selection; Hyperparameter Tuning; Model Serving; Graph Neural Networks; Large Language Models; Prompt Engineering; Retrieval-Augmented Generation; Vector Databases; Semantic Search; AI Agents; Tool Calling; Fine-Tuning; Responsible AI; Multimodal AI; Speech Recognition; Text-to-Speech; Document Parsing; Diffusion Models; Threat Modeling; Secure Coding; Vulnerability Management; Penetration Testing; Application Security; Web Security; Network Security; Identity and Access Management; Public Key Infrastructure; Security Auditing; Incident Response; Digital Forensics; Security Operations; Zero Trust; Privacy Engineering; Data Protection; Malware Analysis; Static Analysis; Dynamic Analysis; Software Supply Chain Security; Secrets Scanning; Firewall Configuration; OWASP Top 10; Android Development; iOS Development; React Native; Jetpack Compose; Mobile UX; Mobile App Security; Embedded Systems; Firmware Development; Internet of Things; Real-Time Systems; Edge Computing; Bluetooth Low Energy; Unit Testing; Integration Testing; End-to-End Testing; Property-Based Testing; Mutation Testing; Test-Driven Development; Behavior-Driven Development; Test Automation; Chaos Engineering; Static Type Checking; Technical Leadership; Stakeholder Communication; Product Thinking; Project Management; Problem Solving; Written Communication; Presentation Skills; User Research; Product Analytics; UX Research; Human-Computer Interaction; Ethics in Technology; Accessibility Engineering
"""


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def build() -> None:
    skills: list[dict[str, object]] = []
    alias_map: dict[str, str] = {}
    for category, raw_names in CATEGORIES.items():
        names = _split_compact(raw_names)
        for name in names:
            skill_id = slug(name)
            tokens = re.findall(r"[A-Za-z0-9+#.-]+", name)
            aliases = list(dict.fromkeys([
                name.lower(),
                "".join(tokens).lower(),
                " ".join(tokens).lower(),
            ]))
            if len(tokens) > 1:
                aliases.append("".join(token[0] for token in tokens).lower())
            aliases.extend(alias.lower() for alias in CURATED.get(name, []))
            aliases = list(dict.fromkeys(aliases))
            aliases = [alias for alias in aliases if alias]
            demand = 0.45 + ((sum(ord(char) for char in skill_id) % 55) / 100)
            skills.append({
                "id": skill_id,
                "canonical_name": name,
                "category": category,
                "aliases": aliases,
                "description": f"Practical knowledge and application of {name}.",
                "market_demand_weight": round(min(demand, 1.0), 2),
            })
            for alias in aliases:
                alias_map.setdefault(alias, skill_id)
    # Merge repeated mentions across categories into one canonical node.
    merged: dict[str, dict[str, object]] = {}
    for skill in skills:
        current = merged.get(str(skill["id"]))
        if current is None:
            merged[str(skill["id"])] = skill
        else:
            current_aliases = cast(list[str], current["aliases"])
            incoming_aliases = cast(list[str], skill["aliases"])
            current["aliases"] = list(dict.fromkeys([*current_aliases, *incoming_aliases]))
    skills = list(merged.values())
    # Explicit expected mappings always override compact-name collisions.
    by_name = {str(row["canonical_name"]): str(row["id"]) for row in skills}
    for name, aliases in CURATED.items():
        if name in by_name:
            for alias in aliases:
                alias_map[alias.casefold()] = by_name[name]
    tests: list[dict[str, str]] = []
    test_aliases = [
        ("DSA", "data-structures-and-algorithms"),
        ("Data Structures & Algorithms", "data-structures-and-algorithms"),
        ("CS201 Data Structures", "data-structures"),
        ("algos", "data-structures-and-algorithms"),
    ]
    tests.extend({"text": text, "expected_skill_id": skill_id} for text, skill_id in test_aliases)
    for skill in skills[:120]:
        tests.append({"text": str(skill["canonical_name"]), "expected_skill_id": str(skill["id"])})
    while len(tests) < 128:
        skill = skills[len(tests) % len(skills)]
        aliases_for_test = cast(list[str], skill["aliases"])
        tests.append({"text": aliases_for_test[0], "expected_skill_id": str(skill["id"])})
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "skills.yaml").write_text(yaml.safe_dump({"skills": skills}, sort_keys=False, allow_unicode=True), encoding="utf-8")
    (ROOT / "aliases.yaml").write_text(yaml.safe_dump({"aliases": alias_map}, sort_keys=True, allow_unicode=True), encoding="utf-8")
    (ROOT / "alias_tests.yaml").write_text(yaml.safe_dump({"cases": tests}, sort_keys=False, allow_unicode=True), encoding="utf-8")
    prereqs = {
        "data-structures-and-algorithms": ["data-structures", "algorithms"],
        "machine-learning": ["statistics", "probability", "linear-algebra", "python", "numpy"],
        "deep-learning": ["machine-learning", "linear-algebra", "probability", "neural-networks"],
        "natural-language-processing": ["machine-learning", "statistics"],
        "computer-vision": ["machine-learning", "linear-algebra"],
        "large-language-models": ["deep-learning", "natural-language-processing", "transformers"],
        "retrieval-augmented-generation": ["large-language-models", "embeddings", "vector-databases"],
        "kubernetes": ["docker", "linux", "network-security"],
        "terraform": ["infrastructure-as-code", "linux"],
        "system-design": ["data-structures", "distributed-systems", "database-design"],
        "distributed-systems": ["computer-networks", "operating-systems"],
        "model-serving": ["machine-learning", "docker", "rest-apis"],
        "mlops": ["machine-learning", "continuous-integration", "docker"],
    }
    known = {str(row["id"]) for row in skills}
    prereqs = {key: [value for value in values if value in known] for key, values in prereqs.items() if key in known}
    adjacent = {
        "react": ["typescript", "javascript", "next-js", "web-performance"],
        "django": ["python", "rest-apis", "postgresql"],
        "fastapi": ["python", "rest-apis", "openapi"],
        "machine-learning": ["statistics", "pytorch", "scikit-learn", "feature-engineering"],
        "large-language-models": ["prompt-engineering", "retrieval-augmented-generation", "transformers"],
        "docker": ["kubernetes", "container-security", "linux"],
        "postgresql": ["database-design", "database-indexing", "query-optimization"],
        "application-security": ["secure-coding", "threat-modeling", "owasp-top-10"],
    }
    specializes = {
        "next-js": ["react"],
        "react-native": ["react"],
        "convolutional-neural-networks": ["neural-networks"],
        "recurrent-neural-networks": ["neural-networks"],
        "graph-neural-networks": ["neural-networks"],
        "site-reliability-engineering": ["reliability-engineering"],
    }
    adjacent_edges = {
        key: [{"skill_id": value, "similarity_weight": 0.72} for value in values if value in known]
        for key, values in adjacent.items()
        if key in known
    }
    edges = {
        "prerequisites": prereqs,
        "adjacent": adjacent_edges,
        "specializes": {key: [value for value in values if value in known] for key, values in specializes.items() if key in known},
    }
    (ROOT / "prereqs.yaml").write_text(yaml.safe_dump(edges, sort_keys=True), encoding="utf-8")
    print(f"Wrote {len(skills)} skills, {len(alias_map)} unique aliases, {len(tests)} alias cases")


def _split_compact(value: str) -> list[str]:
    """Split compact category rows by greedily recognizing curated multiword names."""
    tokens = re.findall(r"[A-Za-z0-9+#.-]+", value)
    phrases = {
        tuple(re.findall(r"[A-Za-z0-9+#.-]+", phrase.casefold())): phrase
        for phrase in MULTIWORD.split(";")
        if phrase.strip()
    }
    ordered_phrases = sorted(phrases, key=len, reverse=True)
    output: list[str] = []
    index = 0
    while index < len(tokens):
        selected: tuple[str, ...] | None = None
        lowered = [token.casefold() for token in tokens]
        for phrase in ordered_phrases:
            if tuple(lowered[index : index + len(phrase)]) == phrase:
                selected = phrase
                break
        if selected is None:
            output.append(tokens[index])
            index += 1
        else:
            output.append(" ".join(tokens[index : index + len(selected)]))
            index += len(selected)
    return output


if __name__ == "__main__":
    build()
