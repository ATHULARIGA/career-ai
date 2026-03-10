from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

model = None


def get_model():
    global model
    if model is None:
        model = SentenceTransformer("all-MiniLM-L6-v2")
    return model


def token_overlap_score(a: str, b: str) -> float:
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def grade_answer(user_answer, ideal_answer):

    print("IDEAL IN GRADER:", ideal_answer)
    print("USER IN GRADER:", user_answer)

    try:
        emb_model = get_model()
        emb1 = emb_model.encode([ideal_answer], normalize_embeddings=True)
        emb2 = emb_model.encode([user_answer], normalize_embeddings=True)
        similarity = cosine_similarity(emb1, emb2)[0][0]
    except Exception as e:
        print("EMBEDDING MODEL ERROR:", e)
        similarity = token_overlap_score(user_answer, ideal_answer)

    print("SIMILARITY:", similarity)

    scaled = (float(similarity) - 0.3) / (0.9 - 0.3)
    score = max(0, min(10, scaled * 10))

    return {"correctness": round(score, 1)}
