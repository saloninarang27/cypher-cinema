// Q3: three-hop candidates  target -> liked A <- supporter X -> liked B
// B must not be rated (any rating) by the target; support = DISTINCT supporters X
MATCH (u:User {id: $target_user})-[r1:RATED]->(a:Movie)<-[r2:RATED]-(x:User)
WHERE r1.rating >= $like_threshold
  AND r2.rating >= $like_threshold
  AND x <> u
WITH DISTINCT u, x
MATCH (x)-[r3:RATED]->(b:Movie)
WHERE r3.rating >= $like_threshold
  AND NOT EXISTS { (u)-[:RATED]->(b) }
RETURN b.id AS movie_id, b.title AS title, count(DISTINCT x) AS support
ORDER BY support DESC, movie_id ASC
LIMIT $topk
