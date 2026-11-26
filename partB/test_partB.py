"""Self-check for Assignment 3B.

python partB/test_partB.py --data-dir <ml-100k> [--output-dir partB/output] [--target-user 1 --like-threshold 4 --topk 10]

1. Recommender invariants (always): no training-rated movie recommended, ranks sorted,
   tie rules, Jaccard computed independently, different users/neighbors/threshold.
2. If q1..q4.csv exist: recompute Q1-Q4 in plain Python from u1.base and compare with
   the Neo4j output (run run_queries.py with the same parameters first).
"""
import argparse
import csv
import os
from collections import defaultdict

from data import load_movies, load_ratings
from recommend import TrainGraph


def check_recommenders(train):
    for lt in (4, 5):
        g = TrainGraph(train, lt)
        for u in (1, 7, 50, 100, 450):
            for recs in (g.method_a(u, 15), g.method_b(u, 5, 15), g.method_b(u, 30, 7)):
                assert all(m not in g.rated[u] for m, _ in recs), "rated movie recommended"
                keys = [(-s, m) for m, s in recs]
                assert keys == sorted(keys), "bad ordering"
            # Method A independently: brute force over all users
            score = defaultdict(int)
            for v in g.liked:
                if v != u and g.liked[u] & g.liked[v]:
                    for m in g.liked[v]:
                        score[m] += 1
            exp = sorted(((m, s) for m, s in score.items() if m not in g.rated[u]),
                         key=lambda t: (-t[1], t[0]))[:15]
            assert g.method_a(u, 15) == exp
            # Jaccard independently
            nb = g.jaccard_neighbors(u, 20)
            for v, j in nb:
                a, b = g.liked[u], g.liked[v]
                assert abs(j - len(a & b) / len(a | b)) < 1e-15 and j > 0
            assert [(-j, v) for v, j in nb] == sorted((-j, v) for v, j in nb)
    print("recommender checks passed")


def python_queries(train, titles, genres, u, lt, k):
    g = TrainGraph(train, lt)
    rating = {(a, m): r for a, m, r, _ in train}
    q1 = sorted(((m, titles[m], rating[(u, m)]) for m in g.liked[u]),
                key=lambda t: (-t[2], t[0]))[:k]
    common = {v: len(g.liked[u] & g.liked[v]) for v in g.supporters(u)}
    q2 = sorted(common.items(), key=lambda t: (-t[1], t[0]))[:k]
    q3 = [(m, titles[m], s) for m, s in g.method_a(u, k)]
    sup, gen = defaultdict(set), defaultdict(set)
    for a in g.liked[u]:
        for x in g.likers[a] - {u}:
            for b in g.liked[x] - g.rated[u]:
                shared = genres[a] & genres[b]
                if shared:
                    sup[b].add(x)
                    gen[b] |= shared
    q4 = sorted(((b, titles[b], len(sup[b]), len(gen[b])) for b in sup),
                key=lambda t: (-t[2], -t[3], t[0]))[:k]
    return {"q1": q1, "q2": q2, "q3": q3, "q4": q4}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--output-dir", default="partB/output")
    ap.add_argument("--target-user", type=int, default=1)
    ap.add_argument("--like-threshold", type=int, default=4)
    ap.add_argument("--topk", type=int, default=10)
    a = ap.parse_args()
    train = load_ratings(a.data_dir, "u1.base")
    assert len(train) == 80000
    check_recommenders(train)

    movies = load_movies(a.data_dir)
    titles = {m: t for m, t, _ in movies}
    genres = {m: set(gs) for m, _, gs in movies}
    exp = python_queries(train, titles, genres, a.target_user, a.like_threshold, a.topk)
    for q, rows in exp.items():
        path = os.path.join(a.output_dir, f"{q}.csv")
        if not os.path.isfile(path):
            print(f"{q}.csv not found - skipped (run run_queries.py first)")
            continue
        with open(path, encoding="utf-8") as f:
            got = [tuple(r) for r in list(csv.reader(f))[1:]]
        want = [tuple(map(str, r)) for r in rows]
        assert got == want, f"{q} mismatch:\n got  {got}\n want {want}"
        print(f"{q}.csv matches the independent Python computation")
    print("all 3B self-checks passed")


if __name__ == "__main__":
    main()
