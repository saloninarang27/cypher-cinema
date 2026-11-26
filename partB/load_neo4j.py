"""B1: load u.user, u.item, u.genre and u1.base (training only) into Neo4j.

Idempotent: constraints + MERGE. --reset deletes the whole graph first.
"""
import argparse
import os

from neo4j import GraphDatabase

from data import load_genres, load_movies, load_ratings, load_users, write_csv

CONSTRAINTS = [
    "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
    "CREATE CONSTRAINT movie_id IF NOT EXISTS FOR (m:Movie) REQUIRE m.id IS UNIQUE",
    "CREATE CONSTRAINT genre_id IF NOT EXISTS FOR (g:Genre) REQUIRE g.id IS UNIQUE",
]

LOAD_USERS = "UNWIND $rows AS r MERGE (:User {id: r.id})"
LOAD_GENRES = "UNWIND $rows AS r MERGE (g:Genre {id: r.id}) SET g.name = r.name"
LOAD_MOVIES = "UNWIND $rows AS r MERGE (m:Movie {id: r.id}) SET m.title = r.title"
LOAD_IN_GENRE = """
UNWIND $rows AS r
MATCH (m:Movie {id: r.movie_id}), (g:Genre {id: r.genre_id})
MERGE (m)-[:IN_GENRE]->(g)
"""
LOAD_RATED = """
UNWIND $rows AS r
MATCH (u:User {id: r.user_id}), (m:Movie {id: r.movie_id})
MERGE (u)-[x:RATED]->(m)
SET x.rating = r.rating, x.timestamp = r.timestamp
"""
COUNTS = [
    ("users", "MATCH (n:User) RETURN count(n) AS c"),
    ("movies", "MATCH (n:Movie) RETURN count(n) AS c"),
    ("genres", "MATCH (n:Genre) RETURN count(n) AS c"),
    ("rated_relationships", "MATCH (:User)-[r:RATED]->(:Movie) RETURN count(r) AS c"),
    ("in_genre_relationships", "MATCH (:Movie)-[r:IN_GENRE]->(:Genre) RETURN count(r) AS c"),
]


def batched(driver, query, rows, size):
    for i in range(0, len(rows), size):
        driver.execute_query(query, rows=rows[i:i + size], database_="neo4j")


def reset(driver):
    # delete in chunks so a big graph never needs one huge transaction
    while True:
        recs, _, _ = driver.execute_query(
            "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n RETURN count(*) AS c", database_="neo4j")
        if recs[0]["c"] == 0:
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--uri", default="bolt://localhost:7687")
    ap.add_argument("--user", default="neo4j")
    ap.add_argument("--password", default="bdaGraph2026")
    ap.add_argument("--reset", action="store_true", help="delete the existing graph first")
    ap.add_argument("--batch-size", type=int, default=1000)
    ap.add_argument("--output-dir", default="partB/output")
    a = ap.parse_args()

    users = [{"id": u} for u in load_users(a.data_dir)]
    genres = [{"id": g, "name": n} for g, n in load_genres(a.data_dir)]
    movies_raw = load_movies(a.data_dir)
    movies = [{"id": m, "title": t} for m, t, _ in movies_raw]
    in_genre = [{"movie_id": m, "genre_id": g} for m, _, gs in movies_raw for g in gs]
    rated = [{"user_id": u, "movie_id": m, "rating": r, "timestamp": t}
             for u, m, r, t in load_ratings(a.data_dir, "u1.base")]   # training split only

    with GraphDatabase.driver(a.uri, auth=(a.user, a.password)) as driver:
        driver.verify_connectivity()
        if a.reset:
            reset(driver)
            print("graph reset")
        for c in CONSTRAINTS:                       # before any relationship is loaded
            driver.execute_query(c, database_="neo4j")
        for name, q, rows in [("users", LOAD_USERS, users), ("genres", LOAD_GENRES, genres),
                              ("movies", LOAD_MOVIES, movies),
                              ("in_genre", LOAD_IN_GENRE, in_genre), ("rated", LOAD_RATED, rated)]:
            batched(driver, q, rows, a.batch_size)
            print(f"loaded {name}: {len(rows)} rows")
        counts = []
        for metric, q in COUNTS:
            recs, _, _ = driver.execute_query(q, database_="neo4j")
            counts.append((metric, recs[0]["c"]))

    write_csv(os.path.join(a.output_dir, "db_counts.csv"), ["metric", "value"], counts)
    for k, v in counts:
        print(f"{k},{v}")
    expected = {"users": 943, "movies": 1682, "genres": 19, "rated_relationships": 80000}
    bad = {k: v for k, v in counts if k in expected and v != expected[k]}
    if bad:
        raise SystemExit(f"FAIL: unexpected counts {bad}")


if __name__ == "__main__":
    main()
