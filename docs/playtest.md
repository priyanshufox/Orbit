# Playtests and tuning (task 10.6)

Goal: 3–5 real rooms of 5–15 friends, then tune the scoring knobs with what you see. Every knob is an environment variable on the API **and** worker, so tuning needs no code change.

| Knob | Default | What it changes |
|---|---|---|
| `EDGE_THRESHOLD` | `0.4` | Pairs at or above this get an edge on the graph |
| `EDGES_ALWAYS_SHOWN` | `3` | Each player's strongest N pairs are always drawn, so nobody is alone |
| `REACTION_VALUES` | `{"like": 1, "laugh": 1, "send": 1.5, "skip": -1}` | How reactions count in reaction similarity |
| `ROUND_SECONDS` | `300` | Round length |
| `ROOM_MEMBER_CAP` | `20` | Players per room |

Signal weights (35/35/15/15) and minimum shared items live in `api/src/orbit/modules/scoring/domain/`; change them there with tests.

## Run a session

1. Before: deploy, load the banks, and have one person host on a TV.
2. During: note anything confusing (the join flow, a question, a card that fell flat).
3. Right after the reveal, ask each player:
   - "Does your closest person look right?" (yes / roughly / no)
   - "Is anyone missing from your top 3 who should be there?"
   - "Was any reason on an edge wrong or awkward?"
4. Afterwards, read the scores (`GET /rooms/{code}/graph` before the room expires) next to the answers above.

## How to tune

- **Graph too busy** (everyone connected): raise `EDGE_THRESHOLD` by 0.05 at a time.
- **Graph too sparse or split**: lower it, or keep it and rely on `EDGES_ALWAYS_SHOWN`.
- **Reactions dominate** (people who skip a lot all cluster): soften `skip`, e.g. -0.5.
- **"Send" feels meaningless**: drop it to 1.0.
- **Answers feel random**: look at which questions everyone answers the same way and replace them in `api/src/orbit/modules/game/data/questions.json` (questions that split the room are the useful ones).

Record each change and the room it was tested in, so the next session can tell whether it helped.

## Load test

`cd api && uv run python loadtest/run.py --rooms 20 --players 20` runs the full stack locally. Result on a laptop (15 Nov 2026): 20/20 rooms revealed, 0 failures, 9,200 WebSocket events delivered across 2 API processes, reveal 0.8 s median after the last player finished. Request latencies (p95 about 1.7 s) reflect one process firing 10,000 answers at once with no thinking time, which is far heavier than real play. Re-run it against staging before launch.
