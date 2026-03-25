from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

vectorizer = TfidfVectorizer(stop_words="english", max_features=1000)

def token_overlap_score(a: str, b: str) -> float:
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)

def grade_answer(user_answer, ideal_answer):
    if not user_answer or not user_answer.strip():
        return {"correctness": 0.0, "error": "empty_answer"}

    try:
        tfidf_matrix = vectorizer.fit_transform([ideal_answer, user_answer])
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    except Exception as e:
        print("EMBEDDING MODEL ERROR:", e)
        similarity = token_overlap_score(user_answer, ideal_answer)

    tfidf_scaled = max(0, min(10, ((float(similarity) - 0.2) / (0.85 - 0.2)) * 10))
    overlap = token_overlap_score(user_answer, ideal_answer)
    overlap_scaled = min(10, overlap * 14)
    score = round((tfidf_scaled * 0.7) + (overlap_scaled * 0.3), 1)

    return {"correctness": score}
