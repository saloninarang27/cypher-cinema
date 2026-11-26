"""B3/B4: run Q1-Q4 (parameterized .cypher files) and the path-growth experiment.

Writes q1.csv..q4.csv, path_growth.csv and q3_profile_plan.txt (text dump of the
PROFILE plan, to help read the Neo4j Browser screenshot q3_profile.png).
"""
import argparse
import os
import statistics
import time

from neo4j import GraphDatabase

from data import write_csv

HERE = os.path.dirname(os.path.abspath(__file__))
QUERIES = [("q1", "q1_liked_movies.cypher"), ("q2", "q2_similar_users.cypher"),
           ("q3", "q3_candidates.cypher"), ("q4", "q4_genre_aware.cypher")]

# Variable-length bounds cannot be Cypher parameters, so L is formatted in as an int.
PATH_QUERY = """
MATCH p = (u:User {{id: $target_user}})-[rs:RATED*{L}]-(n)
WHERE all(r IN rs WHERE r.rating >= $like_threshold)
RETURN count(p) AS matched_paths, count(DISTINCT n) AS distinct_end_vertices
"""


def read_query(name):
    with open(os.path.join(HERE, "queries", name), encoding="utf-8") as f:
        return f.read()


def profile_text(plan, depth=0):
    args = plan.get("args", {})
    line = (f"{'  ' * depth}{plan['operatorType']}: rows={plan.get('rows')} "
            f"dbHits={plan.get('dbHits')}  {args.get('Details', '')}")
    return [line] + [l for c in plan.get("children", []) for l in profile_text(c, depth + 1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uri", default="bolt://localhost:7687")
    ap.add_argument("--user", default="neo4j")
    ap.add_argument("--password", default="bdaGraph2026")
    ap.add_argument("--target-user", type=int, default=1)
    ap.add_argument("--like-threshold", type=int, default=4)
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--output-dir", default="partB/output")
    ap.add_argument("--max-path-length", type=int, default=4)
    ap.add_argument("--runs", type=int, default=5, help="measured runs after 1 warm-up")
    a = ap.parse_args()
    params = {"target_user": a.target_user, "like_threshold": a.like_threshold, "topk": a.topk}

    with GraphDatabase.driver(a.uri, auth=(a.user, a.password)) as driver:
        driver.verify_connectivity()

        for out, fname in QUERIES:
            q = read_query(fname)
            recs, _, keys = driver.execute_query(q, params, database_="neo4j")
            rows = [[r[k] for k in keys] for r in recs]
            write_csv(os.path.join(a.output_dir, f"{out}.csv"), keys, rows)
            print(f"{out}: {len(rows)} rows -> {keys}")
            for r in rows:
                print("   ", r)

        # PROFILE of Q3 (text version of what Neo4j Browser shows)
        with driver.session(database="neo4j") as s:
            summary = s.run("PROFILE " + read_query("q3_candidates.cypher"), params).consume()
        lines = profile_text(summary.profile)
        with open(os.path.join(a.output_dir, "q3_profile_plan.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print("Q3 PROFILE:\n" + "\n".join(lines))

        # B4: path growth, 1 warm-up + `runs` measured executions, median client time
        growth = []
        pp = {"target_user": a.target_user, "like_threshold": a.like_threshold}
        for L in range(1, a.max_path_length + 1):
            q = PATH_QUERY.format(L=L)
            driver.execute_query(q, pp, database_="neo4j")            # warm-up
            times, rec = [], None
            for _ in range(a.runs):
                t0 = time.perf_counter_ns()
                recs, _, _ = driver.execute_query(q, pp, database_="neo4j")
                times.append((time.perf_counter_ns() - t0) / 1e6)
                rec = recs[0]
            row = [L, rec["matched_paths"], rec["distinct_end_vertices"],
                   round(statistics.median(times), 3)]
            growth.append(row)
            print("path_growth", row, "all runs ms:", [round(t, 1) for t in times])
        write_csv(os.path.join(a.output_dir, "path_growth.csv"),
                  ["path_length", "matched_paths", "distinct_end_vertices", "median_ms"], growth)


if __name__ == "__main__":
    main()
