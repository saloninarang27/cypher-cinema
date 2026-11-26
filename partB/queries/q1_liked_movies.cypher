// Q1: movies liked by the target user (direct neighborhood)
MATCH (u:User {id: $target_user})-[r:RATED]->(m:Movie)
WHERE r.rating >= $like_threshold
RETURN m.id AS movie_id, m.title AS title, r.rating AS rating
ORDER BY rating DESC, movie_id ASC
LIMIT $topk
