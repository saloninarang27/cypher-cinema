# Assignment 3B — Interactive Graph Queries and Recommendation

## 1. Student

- Name: Saloni
- Roll number: MT25081

## 2. Hardware

| Item | Value |
|---|---|
| OS | Microsoft Windows 11 Home Single Language (10.0.26300) |
| CPU | 11th Gen Intel(R) Core(TM) i5-1155G7 @ 2.50GHz |
| Logical CPUs | 8 |
| RAM | 15.8 GB |

## 3. Software versions

Full output is in [environment.txt](environment.txt).

```
Python 3.14.2
Neo4j Community 2026.10.1 (Docker image neo4j:2026.10.1)
graphframes-py==0.12.3
matplotlib==3.11.2
neo4j==6.4.1
networkx==3.7
pandas==3.1.0
pyspark==4.2.0
```

## 4. Dataset

- MovieLens 100K: https://files.grouplens.org/datasets/movielens/ml-100k.zip
- Archive MD5 checked: `0e33842e24a9c977be4e0107933c0723` (matches the expected value)
- Row-count checks: `u1.base` has 80,000 rows, `u1.test` 20,000, `u.item` 1,682, `u.genre` 19, `u.user` 943
- Path assumption: the archive is extracted outside the submission at `../data/ml-100k`. Scripts take `--data-dir`, and no dataset files are included.
- **Training only:** `load_neo4j.py`, `run_queries.py` and the recommenders in `recommend.py` read only `u1.base` (plus `u.item`, `u.genre`, `u.user`). `u1.test` is read in exactly one place: `evaluate()` in [recommend.py](partB/recommend.py), after the recommenders are fully defined.

## 5. How to run

### 5.1 One-time setup (Windows PowerShell)

```powershell
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

docker volume create bda-neo4j-data
docker run -d --name bda-neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/bdaGraph2026 -v bda-neo4j-data:/data neo4j:2026.10.1
```

To reset Neo4j completely, run `docker rm -f bda-neo4j` and `docker volume rm bda-neo4j-data`, then run the two commands above again.

**Quickest way (Windows):** run `.\run_all.ps1`. It starts or creates the container, waits for Neo4j, then runs every command in 5.2 plus the self-check.

### 5.2 Commands used to produce every file in `partB/output/`

Run from the submission root with the venv active. Here `<D>` = `../data/ml-100k`.

```bash
python partB/load_neo4j.py --data-dir <D> --uri bolt://localhost:7687 --user neo4j --password bdaGraph2026 --reset
python partB/run_queries.py --uri bolt://localhost:7687 --user neo4j --password bdaGraph2026 --target-user 1 --like-threshold 4 --topk 10 --output-dir partB/output
python partB/recommend.py --data-dir <D> --users 1 50 100 --like-threshold 4 --neighbors 20 --topk 10 --output-dir partB/output
python partB/test_partB.py --data-dir <D>
```

| Command | Output files |
|---|---|
| `load_neo4j.py` | `db_counts.csv` |
| `run_queries.py` | `q1.csv`–`q4.csv`, `path_growth.csv`, `q3_profile_plan.txt` (text copy of the PROFILE plan) |
| `recommend.py` | `recommendations.csv`, `evaluation.csv` |
| Neo4j Browser (manual) | `q3_profile.png` |
| `test_partB.py` | none. It recomputes Q1–Q4 in plain Python and checks that the CSVs match, and checks the recommender invariants. Pass the same `--target-user/--like-threshold/--topk` you gave `run_queries.py`. |

**q3_profile.png:** open http://localhost:7474 and log in as neo4j / bdaGraph2026. Set the parameters with `:param target_user => 1`, `:param like_threshold => 4` and `:param topk => 10`. Then run `PROFILE` followed by the text of [q3_candidates.cypher](partB/queries/q3_candidates.cypher), switch to plan view and take a screenshot.

**Parameter changes the TA can try:** `--target-user 50 --like-threshold 5` for the queries, and `--users 7 13 --neighbors 5 --topk 15` for `recommend.py`. Nothing is hard-coded in the `.cypher` files.

## 6. Results and answers

### B1 — Load

`db_counts.csv`: users 943, movies 1682, genres 19, rated_relationships 80000, in_genre_relationships **2893** (the number of genre flags equal to 1 in `u.item`).
Idempotency was verified: running the loader again without `--reset` still reports 943 / 1682 / 19 / 80000 / 2893.
Uniqueness constraints on `User.id`, `Movie.id` and `Genre.id` are created before any relationship is loaded. All writes use `UNWIND $rows` in batches of 1000 with `MERGE`, so running the loader again without `--reset` creates no duplicates.

### B3 — Queries (target_user=1, like_threshold=4, topk=10)

| Query | Top 3 rows |
|---|---|
| Q1 liked movies | 1 Toy Story (5), 9 Dead Man Walking (5), 13 Mighty Aphrodite (5). User 1 has 84 liked movies; 10 are returned |
| Q2 similar users | 592 (53 common likes), 474 (44), 864 (44) |
| Q3 candidates | 100 Fargo (support 309), 174 Raiders of the Lost Ark (285), 98 Silence of the Lambs (260) |
| Q4 genre-aware | 100 Fargo (302, 3 genres), 174 Raiders (283, 2), 98 Silence of the Lambs (257, 2) |

All four CSVs match an independent plain-Python recomputation from u1.base (`test_partB.py`). They also match for target_user=50, like_threshold=5, topk=7. Q3 is the same definition as Method A, so `q3.csv` equals Method A's top 10 for user 1. In Q4 the genre requirement lowers some support values (e.g. Contact drops from 251 to 236) and changes the order of movies 286, 318 and 313.

**Q3 design note.** The query first reduces the paths target → A ← X to `DISTINCT x` and only then expands X → B. This gives the same result as the full three-hop pattern, because support counts distinct X. But it avoids carrying one row per (A, X) pair into the third hop.

### B4 — Path growth and PROFILE

| L | matched_paths | distinct_end_vertices | median_ms |
|---|---|---|---|
| 1 | 84 | 84 | 7.4 |
| 2 | 8,625 | 856 | 16.0 |
| 3 | 734,937 | 1,401 | 522.8 |
| 4 | 70,572,032 | 942 | 63,849.2 |

The number of paths grows about 85–100× per hop: roughly the average liked-degree on each side of the bipartite graph. Time follows the path count, not the result: L=4 enumerates 70.6 million paths but reaches only 942 distinct vertices, because there are just 943 users. Distinct end vertices saturate (856 users at L=2, 1,401 movies at L=3) while paths keep exploding. This is why the interactive Q3 collapses to `DISTINCT x` early, and why deeper traversals need aggregation or pruning instead of path enumeration.

Q3 PROFILE (default parameters; full text in `q3_profile_plan.txt`): **final result rows = 10** (`ProduceResults`). There are 1,266 candidate movies before `Top`.
Two operators that dominate:
1. **`Expand(Into)` (u)-[:RATED]->(b)**, the `NOT EXISTS` anti-join that removes already-rated movies: **3,962,035 DB hits**, by far the largest. It runs once for each of the 43,255 (x, b) rows and scans the target user's rating list each time.
2. **`Expand(All)` (x)-[r3:RATED]->(b)** followed by `Filter r3.rating >= $like_threshold`: **78,165 rows** expanded (79,491 DB hits), then 156,330 DB hits to read `rating`. This is the third-hop fan-out from 856 distinct supporters.
(`Distinct u, x` cuts 8,625 rows to 856 before that fan-out.)

Neo4j Browser totals (Cypher 25, planner COST, runtime SLOTTED): **4,296,659 total DB accesses**, 1,872,176 bytes of allocated memory, 995 ms. The `NOT EXISTS` anti-join alone accounts for 92% of the DB accesses. Screenshot: [q3_profile.png](partB/output/q3_profile.png).

### B5 — Interactive query vs global computation (≤120 words)

| Property | Q3 interactive recommendation query | Global PageRank |
|---|---|---|
| Starting scope | One target user (an index lookup on `User.id`) | Every vertex at once |
| Graph portion touched | Only the 3-hop liked neighborhood of that user | The whole training graph, every edge, every iteration |
| Iterative global synchronization? | No. One traversal, answered in milliseconds | Yes. Each iteration needs every rank from the previous one (barrier) |
| Natural system | Graph database (Neo4j, Cypher, index-free adjacency) | Bulk-synchronous engine (Pregel, GraphFrames, Spark) |
| Typical use | Online, per-request recommendations or lookups | Offline batch scoring of global importance |

### B6/B7 — Recommenders and evaluation

`evaluation.csv` (K=10, like_threshold=4, neighbors=20; 456 eligible users, since u1.test only covers 459 users with IDs 1–462):

| method | mean P@10 | mean R@10 | users with ≥1 hit |
|---|---|---|---|
| A_common_neighbor | 0.2471 | 0.1347 | 376 |
| B_jaccard_weighted | 0.3553 | 0.2088 | 406 |

Method B is about 44% better on precision. Method A counts every co-liker equally, so popular movies liked by many weakly similar users rank first. Method B listens only to the 20 most similar users.

### B8 — Bridge to collaborative filtering (≤220 words)

1. **What is a neighbor in Method B?** It is a user whose set of liked movies overlaps most with the target's: one of the top-20 users by Jaccard similarity. A neighbor is a user with similar taste, which is the "user" in user-user collaborative filtering.
2. **Why does 0.8 count more than 0.1?** At 0.8 the two users agree on most of their likes, so that user's other likes are strong evidence. At 0.1 the overlap could be chance or just popular movies. Weighting by similarity turns the sum into a confidence-weighted vote, so a few close neighbors outweigh many distant ones.
3. **What is lost by thresholding?** The strength of a preference (a 5 counts the same as a 4), and all negative information (a 1 is treated the same as "not rated"). It also loses each user's rating scale: a harsh user's 3 may mean what a generous user's 4 means.
4. **How could ratings predict a numeric score?** Use mean-centred, similarity-weighted averaging:
   `r̂(u,m) = r̄_u + Σ_{v∈N(u,m)} sim(u,v)·(r_{v,m} − r̄_v) / Σ_{v∈N(u,m)} |sim(u,v)|`
   Here N(u,m) is the set of u's nearest neighbors who rated m. `sim` would be Pearson or cosine similarity on the actual ratings instead of Jaccard on likes.

## 7. Known limitations / deviations

1. **Python 3.14.2 instead of 3.14.10.** This is the 3.14 build installed here; major and minor match.
2. **Path-length bound.** Variable-length bounds cannot be Cypher parameters, so `run_queries.py` formats the integer L into the path-growth query. All other values are passed as `$target_user` / `$like_threshold`. Neo4j counts trails: a relationship is never reused within one path.
3. **Eligible users.** `eligible_users` = 456: u1.test contains 459 users (IDs 1–462), and 3 of them have no test rating ≥ 4.
4. **Precision denominator.** If a user had fewer than K candidates, Precision@K would still divide by K. This never happens at K=10.
5. **Method labels.** In the CSVs they are `A_common_neighbor` and `B_jaccard_weighted`.
