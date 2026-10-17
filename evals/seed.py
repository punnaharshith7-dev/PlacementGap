from __future__ import annotations

import asyncio

from agent.contracts import RunState
from agent.nodes.profile_normalize import profile_normalize_node
from agent.nodes.profile_parse import profile_parse_node


async def main() -> None:
    state = RunState(
        run_id="seed-profile",
        student_id="placementgap-demo",
        profile_text=(
            "B.Tech Computer Science, CGPA 8.4\n"
            "Coursework: Python, Data Structures, Algorithms, Statistics, Databases\n"
            "Projects:\nBuilt and deployed a REST API using Python and PostgreSQL.\n"
            "Software Engineering Intern — implemented automated tests and Docker deployment."
        ),
        source_doc_id="profile:placementgap-demo",
    )
    parsed = await profile_parse_node(state.model_dump(mode="python"))
    normalized = await profile_normalize_node(parsed)
    result = RunState.model_validate(normalized)
    print(f"Seeded profile {result.student_id}: {len(result.profile.demonstrated_skills if result.profile else {})} demonstrated skills")
    print("Frozen job corpus: evals/datasets/job_corpus.yaml")


if __name__ == "__main__":
    asyncio.run(main())
