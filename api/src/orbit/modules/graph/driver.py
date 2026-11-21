"""Neo4j driver and schema (task 6.1). The only place outside graph/service.py that touches it."""

from typing import Annotated

import structlog
from fastapi import Depends, Request
from neo4j import AsyncDriver, AsyncGraphDatabase

# Other modules type against this alias so only `graph` imports the neo4j package (rule 4).
GraphDriver = AsyncDriver

log = structlog.get_logger("orbit.graph")

SCHEMA = [
    "CREATE CONSTRAINT person_room_id IF NOT EXISTS "
    "FOR (p:Person) REQUIRE (p.room, p.id) IS UNIQUE",
    "CREATE CONSTRAINT place_room_city IF NOT EXISTS "
    "FOR (p:Place) REQUIRE (p.room, p.city) IS UNIQUE",
    "CREATE CONSTRAINT content_room_id IF NOT EXISTS "
    "FOR (c:Content) REQUIRE (c.room, c.id) IS UNIQUE",
    "CREATE INDEX person_room IF NOT EXISTS FOR (p:Person) ON (p.room)",
    "CREATE INDEX person_id IF NOT EXISTS FOR (p:Person) ON (p.id)",
]


def create_driver(uri: str, user: str, password: str) -> AsyncDriver:
    return AsyncGraphDatabase.driver(uri, auth=(user, password))


async def ensure_schema(driver: AsyncDriver) -> None:
    async with driver.session() as session:
        for statement in SCHEMA:
            await session.run(statement)


def get_driver(request: Request) -> AsyncDriver:
    return request.app.state.neo4j


Neo4jDep = Annotated[AsyncDriver, Depends(get_driver)]
