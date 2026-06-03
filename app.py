import pandas as pd

from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from models import db, User, Category, Book, Favorite, Rating
from ml.recommender import get_content_based_recommendations

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/books")
def books():
    search = request.args.get("search", "")
    category_id = request.args.get("category", "")

    query = Book.query

    if search:
        query = query.filter(
            (Book.title.like(f"%{search}%")) |
            (Book.author.like(f"%{search}%"))
        )

    if category_id:
        query = query.filter(Book.category_id == int(category_id))

    all_books = query.all()
    categories = Category.query.all()
    total_books = Book.query.count()

    favorite_book_ids = []

    if session.get("user_id"):
        favorites = Favorite.query.filter_by(user_id=session["user_id"]).all()
        favorite_book_ids = [favorite.book_id for favorite in favorites]

    return render_template(
        "books.html",
        books=all_books,
        categories=categories,
        total_books=total_books,
        search=search,
        selected_category=category_id,
        favorite_book_ids=favorite_book_ids
    )


@app.route("/book/<int:book_id>")
def book_details(book_id):
    book = Book.query.get_or_404(book_id)

    is_favorite = False
    user_rating = None

    ratings = Rating.query.filter_by(book_id=book.id).all()

    if ratings:
        average_rating = round(
            sum(rating.rating for rating in ratings) / len(ratings),
            1
        )
    else:
        average_rating = None

    if session.get("user_id"):
        favorite = Favorite.query.filter_by(
            user_id=session["user_id"],
            book_id=book.id
        ).first()

        if favorite:
            is_favorite = True

        rating = Rating.query.filter_by(
            user_id=session["user_id"],
            book_id=book.id
        ).first()

        if rating:
            user_rating = rating.rating

    return render_template(
        "book_details.html",
        book=book,
        is_favorite=is_favorite,
        user_rating=user_rating,
        average_rating=average_rating,
        rating_count=len(ratings)
    )


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        flash("Please login to access your profile.", "warning")
        return redirect(url_for("login"))

    user = User.query.get_or_404(session["user_id"])

    favorites = Favorite.query.filter_by(user_id=user.id).all()
    favorite_book_ids = [favorite.book_id for favorite in favorites]
    favorite_books = Book.query.filter(Book.id.in_(favorite_book_ids)).all()

    ratings = Rating.query.filter_by(user_id=user.id).all()

    rated_books = []

    for rating in ratings:
        book = Book.query.get(rating.book_id)

        if book:
            rated_books.append({
                "book": book,
                "rating": rating.rating
            })

    return render_template(
        "profile.html",
        user=user,
        favorite_books=favorite_books,
        rated_books=rated_books
    )


@app.route("/rate-book/<int:book_id>", methods=["POST"])
def rate_book(book_id):
    if not session.get("user_id"):
        flash("Please login to rate books.", "warning")
        return redirect(url_for("login"))

    rating_value = int(request.form["rating"])

    existing_rating = Rating.query.filter_by(
        user_id=session["user_id"],
        book_id=book_id
    ).first()

    if existing_rating:
        existing_rating.rating = rating_value
        flash("Your rating has been updated.", "success")
    else:
        new_rating = Rating(
            user_id=session["user_id"],
            book_id=book_id,
            rating=rating_value
        )

        db.session.add(new_rating)
        flash("Your rating has been submitted.", "success")

    db.session.commit()

    return redirect(url_for("book_details", book_id=book_id))


@app.route("/import-books-csv")
def import_books_csv():
    Favorite.query.delete()
    Rating.query.delete()
    Book.query.delete()
    Category.query.delete()
    db.session.commit()

    df = pd.read_csv("data/books.csv")

    for category_name in df["category"].unique():
        category = Category(name=category_name)
        db.session.add(category)

    db.session.commit()

    for _, row in df.iterrows():
        category = Category.query.filter_by(name=row["category"]).first()

        book = Book(
            title=row["title"],
            author=row["author"],
            category_id=category.id,
            published_year=int(row["published_year"]),
            image=row["image"],
            description=row["description"]
        )

        db.session.add(book)

    db.session.commit()

    flash("Books imported successfully from CSV dataset.", "success")
    return redirect(url_for("books"))


@app.route("/add-favorite/<int:book_id>")
def add_favorite(book_id):
    if not session.get("user_id"):
        flash("Please login to add books to favorites.", "warning")
        return redirect(url_for("login"))

    existing_favorite = Favorite.query.filter_by(
        user_id=session["user_id"],
        book_id=book_id
    ).first()

    if existing_favorite:
        flash("This book is already in your favorites.", "info")
    else:
        favorite = Favorite(
            user_id=session["user_id"],
            book_id=book_id
        )

        db.session.add(favorite)
        db.session.commit()

        flash("Book added to favorites.", "success")

    return redirect(request.referrer or url_for("books"))


@app.route("/recommendations")
def recommendations():
    if not session.get("user_id"):
        flash("Please login to view your recommendations.", "warning")
        return redirect(url_for("login"))

    favorites = Favorite.query.filter_by(user_id=session["user_id"]).all()
    favorite_book_ids = [favorite.book_id for favorite in favorites]

    favorite_books = Book.query.filter(Book.id.in_(favorite_book_ids)).all()
    all_books = Book.query.all()

    recommended_books = get_content_based_recommendations(
        all_books=all_books,
        favorite_books=favorite_books,
        top_n=8
    )

    return render_template(
        "recommendations.html",
        favorite_books=favorite_books,
        recommended_books=recommended_books
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            flash("Username or email already exists.", "danger")
            return redirect(url_for("register"))

        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role="user"
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role

            flash("Logged in successfully.", "success")
            return redirect(url_for("home"))

        flash("Invalid email or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)