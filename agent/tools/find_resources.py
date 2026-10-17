from __future__ import annotations

from datetime import UTC, datetime

from agent.contracts import Resource, SkillLevel

_OFFICIAL_ROOTS = {
    "python": ("Python Tutorial", "https://docs.python.org/3/tutorial/", "documentation"),
    "javascript": ("MDN JavaScript Guide", "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide", "documentation"),
    "typescript": ("TypeScript Handbook", "https://www.typescriptlang.org/docs/handbook/intro.html", "documentation"),
    "react": ("React Documentation", "https://react.dev/learn", "documentation"),
    "fastapi": ("FastAPI Tutorial", "https://fastapi.tiangolo.com/tutorial/", "documentation"),
    "postgresql": ("PostgreSQL Tutorial", "https://www.postgresql.org/docs/current/tutorial.html", "documentation"),
    "docker": ("Docker Get Started", "https://docs.docker.com/get-started/", "documentation"),
    "kubernetes": ("Kubernetes Basics", "https://kubernetes.io/docs/tutorials/kubernetes-basics/", "documentation"),
    "machine-learning": ("Scikit-learn User Guide", "https://scikit-learn.org/stable/user_guide.html", "course"),
    "pytorch": ("PyTorch Tutorials", "https://pytorch.org/tutorials/", "documentation"),
    "large-language-models": ("Hugging Face NLP Course", "https://huggingface.co/learn/nlp-course/", "course"),
    "data-structures-and-algorithms": ("OpenDSA", "https://opendsa-server.cs.vt.edu/", "course"),
    "git": ("Pro Git Book", "https://git-scm.com/book/en/v2", "book"),
    "statistics": ("OpenIntro Statistics", "https://www.openintro.org/book/os/", "book"),
}


def find_resources(
    skill_id: str,
    from_level: SkillLevel,
    to_level: SkillLevel,
    budget: float = 0.0,
    max_n: int = 5,
) -> list[Resource]:
    del from_level, to_level
    row = _OFFICIAL_ROOTS.get(skill_id)
    if row is None:
        name = skill_id.replace("-", " ").title()
        row = (f"Official {name} documentation", f"https://www.google.com/search?q={skill_id}+official+documentation", "documentation")
    resources = [Resource(
        title=row[0], url=row[1], kind=row[2], estimated_cost_usd=0,
        checked_at=datetime.now(UTC).date().isoformat(), relevance=0.82,
    )]
    return [resource for resource in resources if resource.estimated_cost_usd <= budget or budget <= 0][:max_n]
