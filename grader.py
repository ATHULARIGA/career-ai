from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def get_model():
    return TfidfVectorizer(stop_words="english", max_features=1000)

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
        vectorizer = get_model()
        tfidf_matrix = vectorizer.fit_transform([ideal_answer, user_answer])
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    except Exception as e:
        print("EMBEDDING MODEL ERROR:", e)
        similarity = token_overlap_score(user_answer, ideal_answer)

    print("SIMILARITY:", similarity)

    scaled = (float(similarity) - 0.3) / (0.9 - 0.3)
    score = max(0, min(10, scaled * 10))

    return {"correctness": round(score, 1)}
