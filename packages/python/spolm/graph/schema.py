CONSTRAINTS = [
    "CREATE CONSTRAINT run_id IF NOT EXISTS FOR (r:Run) REQUIRE r.id IS UNIQUE",
    "CREATE CONSTRAINT memory_id IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE",
    "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE",
    "CREATE CONSTRAINT agent_id IF NOT EXISTS FOR (a:Agent) REQUIRE a.agent_id IS UNIQUE",
]

INDEXES = [
    """CREATE VECTOR INDEX memory_embedding IF NOT EXISTS
       FOR (m:Memory) ON (m.embedding)
       OPTIONS { indexConfig: { `vector.dimensions`: 1536, `vector.similarity_function`: 'cosine' }}""",
    """CREATE VECTOR INDEX run_embedding IF NOT EXISTS
       FOR (r:Run) ON (r.embedding)
       OPTIONS { indexConfig: { `vector.dimensions`: 1536, `vector.similarity_function`: 'cosine' }}""",
]


def apply(driver) -> None:
    with driver.session() as session:
        for stmt in CONSTRAINTS + INDEXES:
            try:
                session.run(stmt)
            except Exception:
                pass  # Index/constraint already exists
