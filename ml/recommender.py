import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def get_content_based_recommendations(all_books, favorite_books, top_n=8):
    if not favorite_books:
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
    favorite_titles = [book.title for book in favorite_books]

    favorite_indexes = df[df["id"].isin(favorite_ids)].index.tolist()

    recommendation_scores = {}

    for favorite_index in favorite_indexes:
        similarity_scores = list(enumerate(similarity_matrix[favorite_index]))

        for index, score in similarity_scores:
            book_id = df.iloc[index]["id"]

            if book_id not in favorite_ids:
                recommendation_scores[book_id] = recommendation_scores.get(book_id, 0) + score

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
                "reason": favorite_titles[:3]
            })

    return recommended_items