from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

model = SentenceTransformer('all-MiniLM-L6-v2')
def grade_answer(user_answer, ideal_answer):

    print("IDEAL IN GRADER:", ideal_answer)
    print("USER IN GRADER:", user_answer)

    emb1 = model.encode([ideal_answer], normalize_embeddings=True)
    emb2 = model.encode([user_answer], normalize_embeddings=True)

    similarity = cosine_similarity(emb1, emb2)[0][0]

    print("SIMILARITY:", similarity)

    scaled = (float(similarity) - 0.3) / (0.9 - 0.3)
    score = max(0, min(10, scaled * 10))

    return {"correctness": round(score, 1)}