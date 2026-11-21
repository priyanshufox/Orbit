"""Load test (task 10.4): N concurrent rooms x M players through the real stack.

Starts its own API (2 uvicorn workers, so events must cross processes via Redis) and an arq
worker against the local infra, signs player tokens with a throwaway key (served to the API as
a JWKS file), then for every room: create, join, open a WebSocket per player, start, answer the
whole deck, finish, and wait until every socket receives `reveal`.

  cd api && uv run python loadtest/run.py --rooms 20 --players 20

Creates users `load-*@orbit.test` and deletes everything it created at the end.
"""

import argparse
import asyncio
import functools
import http.server
import json
import os
import random
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx2
import jwt
import websockets
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import delete, insert, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from orbit.core.config import get_settings
from orbit.modules.accounts.models import User, auth_user
from orbit.modules.graph import service as graph
from orbit.modules.graph.driver import create_driver

ISSUER = "http://loadtest"
KEY = Ed25519PrivateKey.generate()


def token(user_id: UUID, email: str) -> str:
    now = int(time.time())
    claims = {
        "sub": str(user_id),
        "email": email,
        "iss": ISSUER,
        "aud": ISSUER,
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(claims, KEY, algorithm="EdDSA", headers={"kid": "load"})


def serve_jwks(folder: Path) -> str:
    """PyJWT fetches keys over HTTP only, so serve the throwaway JWKS from a local thread."""

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

    handler = functools.partial(Quiet, directory=str(folder))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}/jwks.json"


def write_jwks(folder: Path) -> Path:
    jwk = {
        **jwt.algorithms.OKPAlgorithm.to_jwk(KEY.public_key(), as_dict=True),
        "kid": "load",
        "alg": "EdDSA",
    }
    path = folder / "jwks.json"
    path.write_text(json.dumps({"keys": [jwk]}))
    return path


class Stats:
    def __init__(self) -> None:
        self.lat: dict[str, list[float]] = {}
        self.errors: dict[str, int] = {}

    def time(self, name: str, seconds: float) -> None:
        self.lat.setdefault(name, []).append(seconds * 1000)

    def error(self, name: str) -> None:
        self.errors[name] = self.errors.get(name, 0) + 1

    def report(self) -> str:
        lines = []
        for name, xs in sorted(self.lat.items()):
            xs = sorted(xs)
            p95 = xs[int(len(xs) * 0.95) - 1] if len(xs) > 1 else xs[0]
            lines.append(
                f"  {name:<18} n={len(xs):<6} p50={statistics.median(xs):7.1f} ms  p95={p95:7.1f} ms  max={xs[-1]:7.1f} ms"
            )
        if self.errors:
            lines.append(f"  errors: {self.errors}")
        return "\n".join(lines)


async def timed(stats: Stats, name: str, coro):
    start = time.perf_counter()
    try:
        res = await coro
    except Exception:
        stats.error(name)
        raise
    stats.time(name, time.perf_counter() - start)
    if getattr(res, "status_code", 200) >= 400:
        stats.error(f"{name}:{res.status_code}")
    return res


async def play_room(
    i: int, players: list[tuple[UUID, str]], http: httpx2.AsyncClient, ws_url: str, stats: Stats
) -> dict:
    headers = [{"Authorization": f"Bearer {token(uid, email)}"} for uid, email in players]
    host = headers[0]
    code = (await timed(stats, "create_room", http.post("/rooms", headers=host))).json()["code"]
    await asyncio.gather(
        *(timed(stats, "join", http.post(f"/rooms/{code}/join", headers=h)) for h in headers)
    )

    revealed = [asyncio.Event() for _ in players]
    deliveries = [0] * len(players)

    async def listen(n: int, ready: asyncio.Event) -> None:
        async with websockets.connect(f"{ws_url}/ws/rooms/{code}") as ws:
            await ws.send(json.dumps({"type": "auth", "token": headers[n]["Authorization"][7:]}))
            assert json.loads(await ws.recv())["type"] == "ready"
            ready.set()
            async for raw in ws:
                deliveries[n] += 1
                if json.loads(raw).get("type") == "reveal":
                    revealed[n].set()
                    return

    readies = [asyncio.Event() for _ in players]
    listeners = [asyncio.create_task(listen(n, readies[n])) for n in range(len(players))]
    await asyncio.wait_for(asyncio.gather(*(r.wait() for r in readies)), 30)

    await timed(stats, "start", http.post(f"/rooms/{code}/start", headers=host))
    deck = (await http.get(f"/rooms/{code}/deck", headers=host)).json()

    async def answer_all(h: dict) -> None:
        rng = random.Random(h["Authorization"][-12:])
        for c in deck["cards"]:
            if c["kind"] == "question":
                n_opts = len(c["options"].get("choices", []))
                kind = c["question_kind"]
                value = (
                    {"choice": rng.randrange(n_opts)}
                    if kind == "single"
                    else {"choices": [rng.randrange(n_opts)]}
                    if kind == "multi"
                    else {"value": round(rng.random(), 2)}
                )
                await timed(
                    stats,
                    "put_answer",
                    http.put(f"/rooms/{code}/answers/{c['id']}", json={"value": value}, headers=h),
                )
            else:
                reaction = rng.choice(["like", "laugh", "send", "skip"])
                await timed(
                    stats,
                    "put_reaction",
                    http.put(
                        f"/rooms/{code}/reactions/{c['id']}", json={"reaction": reaction}, headers=h
                    ),
                )
        await timed(stats, "finish", http.post(f"/rooms/{code}/finish", headers=h))

    await asyncio.gather(*(answer_all(h) for h in headers))
    last_finish = time.perf_counter()
    await asyncio.wait_for(asyncio.gather(*(e.wait() for e in revealed)), 120)
    stats.time("finish_to_reveal", time.perf_counter() - last_finish)
    for t in listeners:
        t.cancel()
    graph = (
        await timed(stats, "get_graph", http.get(f"/rooms/{code}/graph", headers=headers[1]))
    ).json()
    return {
        "room": i,
        "code": code,
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
        "events": sum(deliveries),
    }


def start_process(cmd: list[str], env: dict, log: Path) -> subprocess.Popen:
    return subprocess.Popen(
        cmd, env=env, stdout=log.open("w"), stderr=subprocess.STDOUT, start_new_session=True
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rooms", type=int, default=20)
    parser.add_argument("--players", type=int, default=20)
    parser.add_argument("--port", type=int, default=8100)
    args = parser.parse_args()
    settings = get_settings()
    tmp = Path(tempfile.mkdtemp(prefix="orbit-load-"))
    env = {
        **os.environ,
        "AUTH_JWKS_URL": (write_jwks(tmp), serve_jwks(tmp))[1],
        "AUTH_ISSUER": ISSUER,
        "JOINS_PER_MINUTE": "100000",
        "ROOMS_PER_HOST_PER_DAY": "100000",
        "ROOM_MEMBER_CAP": str(max(20, args.players)),
        "LOG_LEVEL": "WARNING",
    }
    base = f"http://127.0.0.1:{args.port}"

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    users: list[list[tuple[UUID, str]]] = [
        [(uuid4(), f"load-{r}-{p}-{uuid4().hex[:6]}@orbit.test") for p in range(args.players)]
        for r in range(args.rooms)
    ]
    flat = [u for room in users for u in room]
    async with engine.begin() as conn:
        await conn.execute(
            insert(auth_user),
            [{"id": u, "email": e, "name": e[:20], "emailVerified": True} for u, e in flat],
        )
        await conn.execute(
            insert(User),
            [
                {
                    "id": u,
                    "email": e,
                    "name": f"P{e.split('-')[2]}",
                    "birth_year": 1999,
                    "is_adult": True,
                    "consented_at": datetime.now(UTC),
                }
                for u, e in flat
            ],
        )

    api = start_process(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "orbit.main:app",
            "--port",
            str(args.port),
            "--workers",
            "2",
        ],
        env,
        tmp / "api.log",
    )
    worker = start_process(
        [sys.executable, "-m", "arq", "orbit.worker.WorkerSettings"], env, tmp / "worker.log"
    )
    stats = Stats()
    try:
        async with httpx2.AsyncClient(
            base_url=base, timeout=60, limits=httpx2.Limits(max_connections=400)
        ) as http:
            for _ in range(100):
                try:
                    if (await http.get("/health/ready")).status_code == 200:
                        break
                except httpx2.HTTPError:
                    pass
                await asyncio.sleep(0.2)
            started = time.perf_counter()
            results = await asyncio.gather(
                *(
                    play_room(i, users[i], http, base.replace("http", "ws"), stats)
                    for i in range(args.rooms)
                ),
                return_exceptions=True,
            )
            elapsed = time.perf_counter() - started
        ok = [r for r in results if isinstance(r, dict)]
        failed = [r for r in results if not isinstance(r, dict)]
        print(
            f"\n{args.rooms} rooms x {args.players} players, 2 API processes: {len(ok)} revealed, {len(failed)} failed, {elapsed:.1f} s total"
        )
        for f in failed[:5]:
            print("  failure:", repr(f))
        if ok:
            print(
                f"  graph sizes: nodes {min(r['nodes'] for r in ok)}-{max(r['nodes'] for r in ok)}, "
                f"edges {min(r['edges'] for r in ok)}-{max(r['edges'] for r in ok)}; WebSocket events delivered: {sum(r['events'] for r in ok)}"
            )
        print(stats.report())
        print(f"  logs: {tmp}")
    finally:
        for proc in (api, worker):
            os.killpg(proc.pid, signal.SIGTERM)
        async with engine.begin() as conn:
            ids = [u for u, _ in flat]
            await conn.execute(
                text(
                    "delete from rooms where host_id = any(:ids) or host_id is null and code in "
                    "(select room_code from room_members where user_id = any(:ids))"
                ),
                {"ids": ids},
            )
            await conn.execute(delete(auth_user).where(auth_user.c.id.in_(ids)))
        await engine.dispose()
        driver = create_driver(
            settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password.get_secret_value()
        )
        for r in results if "results" in locals() else []:
            if isinstance(r, dict):
                await graph.delete_room(driver, r["code"])
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
