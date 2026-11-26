"""Shared MovieLens 100K readers for Assignment 3B."""
import csv
import os


def _path(data_dir, name):
    p = os.path.join(data_dir, name)
    if not os.path.isfile(p):
        raise SystemExit(f"{name} not found in --data-dir {data_dir!r}")
    return p


def load_ratings(data_dir, name):
    """u1.base / u1.test -> list of (user_id, movie_id, rating, timestamp)."""
    with open(_path(data_dir, name), encoding="ascii") as f:
        return [tuple(map(int, line.split("\t"))) for line in f if line.strip()]


def load_genres(data_dir):
    """u.genre -> list of (genre_id, name)."""
    out = []
    with open(_path(data_dir, "u.genre"), encoding="ISO-8859-1") as f:
        for line in f:
            if line.strip():
                name, gid = line.strip().split("|")
                out.append((int(gid), name))
    return out


def load_movies(data_dir):
    """u.item -> list of (movie_id, title, [genre_ids with flag 1])."""
    out = []
    with open(_path(data_dir, "u.item"), encoding="ISO-8859-1") as f:
        for line in f:
            if line.strip():
                cols = line.rstrip("\n").split("|")
                flags = cols[-19:]
                out.append((int(cols[0]), cols[1], [g for g, v in enumerate(flags) if v == "1"]))
    return out


def load_users(data_dir):
    """u.user -> list of user_ids."""
    with open(_path(data_dir, "u.user"), encoding="ISO-8859-1") as f:
        return [int(line.split("|")[0]) for line in f if line.strip()]


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
