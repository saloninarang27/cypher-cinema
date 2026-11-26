"""B6/B7: graph-neighborhood recommenders built from u1.base only, evaluated on u1.test.

Method A: common-neighbor support.   Method B: Jaccard-weighted top-`neighbors` users.
u1.test is read ONLY inside evaluate() (after both recommenders are fully defined).
"""
import argparse
import os
from collections import defaultdict

from data import load_movies, load_ratings, write_csv

METHOD_A = "A_common_neighbor"
METHOD_B = "B_jaccard_weighted"


class TrainGraph:
    """User-movie graph from training ratings only."""

    def __init__(self, train, like_threshold):
        self.rated = defaultdict(set)     # every training rating, any value
        self.liked = defaultdict(set)     # rating >= like_threshold
        self.likers = defaultdict(set)    # movie -> users who like it
        for u, m, r, _ in train:
            self.rated[u].add(m)
            if r >= like_threshold:
                self.liked[u].add(m)
                self.likers[m].add(u)

    def supporters(self, u):
        """Users v != u sharing at least one liked movie with u."""
        out = set()
        for m in self.liked[u]:
            out |= self.likers[m]
        out.discard(u)
        return out

    def method_a(self, u, topk):
        score = defaultdict(int)
        for v in self.supporters(u):
            for m in self.liked[v]:
                score[m] += 1                # each distinct v counted once per m
        return self._rank(u, score, topk)

    def jaccard_neighbors(self, u, neighbors):
        lu = self.liked[u]
        sims = []
        for v in self.supporters(u):         # non-supporters have Jaccard 0 -> discarded
            inter = len(lu & self.liked[v])
            sims.append((inter / len(lu | self.liked[v]), v))
        sims.sort(key=lambda t: (-t[0], t[1]))
        return [(v, j) for j, v in sims[:neighbors]]

    def method_b(self, u, neighbors, topk):
        score = defaultdict(float)
        for v, j in self.jaccard_neighbors(u, neighbors):
            for m in self.liked[v]:
                score[m] += j
        return self._rank(u, score, topk)

    def _rank(self, u, score, topk):
        rated = self.rated[u]                # exclude EVERY training-rated movie
        cands = [(m, s) for m, s in score.items() if m not in rated]
        cands.sort(key=lambda t: (-t[1], t[0]))
        return cands[:topk]


def evaluate(graph, data_dir, like_threshold, neighbors, topk):
    """B7: only place u1.test is read."""
    relevant = defaultdict(set)
    for u, m, r, _ in load_ratings(data_dir, "u1.test"):
        if r >= like_threshold:
            relevant[u].add(m)
    rows = []
    for method, rec in [(METHOD_A, lambda u: graph.method_a(u, topk)),
                        (METHOD_B, lambda u: graph.method_b(u, neighbors, topk))]:
        p_sum = r_sum = hit_users = 0
        eligible = sorted(u for u in relevant if relevant[u])
        for u in eligible:
            hits = len({m for m, _ in rec(u)} & relevant[u])
            p_sum += hits / topk
            r_sum += hits / len(relevant[u])
            hit_users += hits > 0
        rows.append([method, len(eligible), p_sum / len(eligible), r_sum / len(eligible), hit_users])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--users", type=int, nargs="+", default=[1, 50, 100])
    ap.add_argument("--like-threshold", type=int, default=4)
    ap.add_argument("--neighbors", type=int, default=20)
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--output-dir", default="partB/output")
    ap.add_argument("--skip-eval", action="store_true", help="only write recommendations.csv")
    a = ap.parse_args()
    if a.topk < 1 or a.neighbors < 1:
        raise SystemExit("--topk and --neighbors must be >= 1")

    graph = TrainGraph(load_ratings(a.data_dir, "u1.base"), a.like_threshold)
    titles = {m: t for m, t, _ in load_movies(a.data_dir)}

    rows = []
    for method in (METHOD_A, METHOD_B):
        for u in a.users:
            recs = graph.method_a(u, a.topk) if method == METHOD_A else \
                graph.method_b(u, a.neighbors, a.topk)
            rows += [[method, u, i, m, titles[m], s] for i, (m, s) in enumerate(recs, 1)]
    write_csv(os.path.join(a.output_dir, "recommendations.csv"),
              ["method", "user_id", "rank", "movie_id", "title", "score"], rows)
    for r in rows:
        print(r)

    if not a.skip_eval:
        ev = evaluate(graph, a.data_dir, a.like_threshold, a.neighbors, a.topk)
        write_csv(os.path.join(a.output_dir, "evaluation.csv"),
                  ["method", "eligible_users", "mean_precision_at_10", "mean_recall_at_10",
                   "users_with_at_least_one_hit"], ev)
        for r in ev:
            print(r)


if __name__ == "__main__":
    main()
