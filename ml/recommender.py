import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def get_content_based_recommendations(
    all_books,
    favorite_books,
    highly_rated_books=None,
    top_n=8
):
    if highly_rated_books is None:
        highly_rated_books = []

    if not favorite_books and not highly_rated_books:
        return []

    books_data = []

    for book in all_books:
        category_name = book.category.name if book.category else ""

        content = f"""
        {book.title}
        {book.author}
        {book.description}
        {category_name}
        """

        books_data.append({
            "id": book.id,
            "title": book.title,
            "content": content
        })

    df = pd.DataFrame(books_data)

    if df.empty:
        return []

    tfidf = TfidfVectorizer(stop_words="english")
    tfidf_matrix = tfidf.fit_transform(df["content"])

    similarity_matrix = cosine_similarity(tfidf_matrix, tfidf_matrix)

    favorite_ids = [book.id for book in favorite_books]
    highly_rated_ids = [book.id for book in highly_rated_books]

    source_books = []

    for book in favorite_books:
        source_books.append({
            "book": book,
            "weight": 1.0,
            "type": "favorite"
        })

    for book in highly_rated_books:
        source_books.append({
            "book": book,
            "weight": 1.3,
            "type": "high_rating"
        })

    excluded_ids = list(set(favorite_ids + highly_rated_ids))

    recommendation_scores = {}
    recommendation_reasons = {}

    for source in source_books:
        source_book = source["book"]
        source_weight = source["weight"]
        source_type = source["type"]

        source_indexes = df[df["id"] == source_book.id].index.tolist()

        if not source_indexes:
            continue

        source_index = source_indexes[0]
        similarity_scores = list(enumerate(similarity_matrix[source_index]))

        for index, score in similarity_scores:
            book_id = df.iloc[index]["id"]

            if book_id not in excluded_ids:
                weighted_score = score * source_weight

                recommendation_scores[book_id] = (
                    recommendation_scores.get(book_id, 0) + weighted_score
                )

                if book_id not in recommendation_reasons:
                    recommendation_reasons[book_id] = []

                reason_text = source_book.title

                if source_type == "high_rating":
                    reason_text = f"{source_book.title} (high rating)"

                if reason_text not in recommendation_reasons[book_id]:
                    recommendation_reasons[book_id].append(reason_text)

    sorted_recommendations = sorted(
        recommendation_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    recommended_items = []

    for book_id, score in sorted_recommendations[:top_n]:
        book = next((book for book in all_books if book.id == book_id), None)

        if book:
            match_score = round(min(score * 100, 100), 1)

            recommended_items.append({
                "book": book,
                "score": match_score,
                "reason": recommendation_reasons.get(book_id, [])[:3]
            })

    return recommended_items