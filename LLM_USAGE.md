# LLM Usage — Assignment 3B

## Tools used
- **Claude Code** (Anthropic), model Claude Opus 5.5, used inside VS Code as a coding agent. It read the assignment, wrote and ran the scripts, and I reviewed and ran every output myself.

The session was conversational. The prompts below are condensed versions of the turns that changed the implementation, in the order they happened. Each one shows what came back, what was checked, and how it was refined.

## Prompts and iterations

### Round 1 — Recommenders first, because they need no database
> "Implement B6 and B7 in recommend.py from u1.base only. Keep two separate sets per user: everything the user rated (excluded from candidates, whatever the rating) and everything the user liked (rating >= like_threshold). Method A counts DISTINCT supporting users. Method B uses Jaccard on liked sets, discards zero similarity, keeps the top `neighbors` by (Jaccard DESC, user_id ASC), and sums Jaccard. u1.test may be read only inside the evaluation function."

**Result:** runs in about 6 s for all 456 eligible users. Method B beats Method A (P@10 0.355 vs 0.247, R@10 0.209 vs 0.135).
**What I checked:** u1.test is opened in exactly one function, `evaluate()`, which is called only after both recommenders are fully defined. This rules out leakage.

### Round 2 — Verify independently, with non-default parameters
> "Write test_partB.py that does not reuse the ranking code being tested. Recompute Method A by brute force over all users, recompute every Jaccard value directly from the liked sets, and assert that no recommended movie is in the user's training ratings, for thresholds 4 and 5, several users, and different neighbors/topk. Also recompute Q1–Q4 in plain Python so the Neo4j CSVs can be compared row by row."

**Result:** all invariants pass. The Python versions of Q1–Q4 give the expected answers before Neo4j is even running (e.g. Q3 for user 1: Fargo, support 309; Q4: Fargo, support 302, shared_genres 3). They act as a reference for the database results.

### Round 3 — Neo4j loader and Cypher queries
> "Write load_neo4j.py: uniqueness constraints on User.id, Movie.id and Genre.id before any relationship; UNWIND batches of 1000 with MERGE so reruns create no duplicates; --reset deletes in chunks. Write Q1–Q4 as parameterized .cypher files ($target_user, $like_threshold, $topk), with ties broken exactly as specified. For Q3, exclude a candidate if the target rated it with any rating."

**Design point discussed:** support counts only DISTINCT supporters X, so Q3 reduces target → A ← X to `WITH DISTINCT u, x` before expanding X → B. This avoids carrying one row per (A, X, B) path into the aggregation, and gives the same result as the full three-hop pattern. Q4 keeps the full path, because its genre condition depends on which A connects X to B.

### Round 4 — Path growth experiment
> "Count exact-length undirected paths from target_user for L = 1..4, with every relationship's rating >= like_threshold. Report count(p) before DISTINCT and count(DISTINCT end vertex). Do one warm-up and then 5 runs timed with time.perf_counter_ns(), and report the median."

**Constraint found:** Cypher doesn't allow a parameter as a variable-length bound (`[*$L]`), so L is formatted into the query as an integer and every other value stays a parameter. This is documented in the README as a deviation.

### Round 5 — First end-to-end run with Docker and Neo4j
> "Docker is installed and `docker run hello-world` works in a new PowerShell, but run_all.ps1 in the VS Code terminal says 'docker is not recognized'."

**Diagnosis and fix:** the VS Code terminal was opened before Docker was installed, so it had a stale PATH. Docker Desktop had been installed per-user (`%LOCALAPPDATA%\Programs\DockerDesktop`), not in `Program Files` as the LLM first assumed. The script now reloads PATH from the registry and checks `docker info` before starting.
**Result:** all outputs were produced in about 6.6 min, 6 of them for the L=4 path count (70.6 M paths, about 60 s per run). Neo4j's Q1–Q4 matched the plain-Python recomputation for user 1 / threshold 4 / topk 10 and for user 50 / threshold 5 / topk 7. Rerunning the loader without `--reset` kept 80,000 RATED relationships (idempotent).

## Example where the LLM suggestion was wrong

When writing the README, the LLM explained `eligible_users = 456` as: "u1.test only contains users 1–462, and 6 of them have no test rating >= 4". That sounds plausible, and the arithmetic (462 − 6 = 456) looked consistent, but it was **not checked against the data**.

## How it was detected and fixed
The claim was then checked directly against u1.test. Counting distinct user IDs showed **459 users** (IDs range from 1 to 462, but some IDs in that range never appear), and **3** of them have no rating >= 4. The README was corrected. Lesson: numbers that an LLM writes into a report must be recomputed from the data, not inferred from other numbers.

**Second example: the first run_all.ps1.** It (a) hard-coded `C:\Program Files\Docker\...` as the Docker location, which was wrong on this machine, and (b) ran the Neo4j readiness probe with `$ErrorActionPreference = "Stop"`. In Windows PowerShell 5.1, any stderr from a native program is turned into a terminating error, so the expected "not ready yet" traceback aborted the script instead of retrying. Fixed by reading PATH from the registry and relaxing the error preference only around the polling loop.

## Concept that became clearer
Method A (the same definition as Q3) and Method B differ only in **how neighbors are weighted**. Method A gives every co-liker a weight of 1, so heavy raters and popular movies dominate. Method B weights each neighbor by Jaccard overlap and keeps only the 20 closest. That is user-user collaborative filtering with binary ratings, and it explains the 44% gain in precision. The next step, using the actual 1–5 ratings with mean-centring, is the formula in README answer B8.4.
