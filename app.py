import pandas as pd

from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from models import db, User, Category, Book, Favorite, Rating
from ml.recommender import get_content_based_recommendations

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)


def admin_required():
    if not session.get("user_id"):
        flash("Please login to access this page.", "warning")
        return False

    if session.get("role") != "admin":
        flash("Access denied. Admin privileges are required.", "danger")
        return False

    return True


@app.route("/")
def home():
    featured_books = Book.query.limit(8).all()
    total_books = Book.query.count()
    total_categories = Category.query.count()

    return render_template(
        "index.html",
        featured_books=featured_books,
        total_books=total_books,
        total_categories=total_categories
    )
@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/dashboard")
def dashboard():
    if not admin_required():
        return redirect(url_for("login"))

    total_books = Book.query.count()
    total_categories = Category.query.count()
    total_users = User.query.count()
    total_favorites = Favorite.query.count()
    total_ratings = Rating.query.count()

    categories = Category.query.all()
    books = Book.query.all()
    users = User.query.all()

    category_stats = []
    for category in categories:
        count = Book.query.filter_by(category_id=category.id).count()
        category_stats.append({"name": category.name, "count": count})

    top_rated_books = []
    for book in books:
        ratings = Rating.query.filter_by(book_id=book.id).all()
        if ratings:
            avg = round(sum(r.rating for r in ratings) / len(ratings), 1)
            top_rated_books.append({
                "book": book,
                "average_rating": avg,
                "rating_count": len(ratings)
            })

    top_rated_books = sorted(top_rated_books, key=lambda x: x["average_rating"], reverse=True)[:5]

    most_favorited_books = []
    for book in books:
        count = Favorite.query.filter_by(book_id=book.id).count()
        if count > 0:
            most_favorited_books.append({"book": book, "favorite_count": count})

    most_favorited_books = sorted(most_favorited_books, key=lambda x: x["favorite_count"], reverse=True)[:5]

    active_users = []
    for user in users:
        favorites_count = Favorite.query.filter_by(user_id=user.id).count()
        ratings_count = Rating.query.filter_by(user_id=user.id).count()
        total_activity = favorites_count + ratings_count

        if total_activity > 0:
            active_users.append({
                "user": user,
                "favorites": favorites_count,
                "ratings": ratings_count,
                "activity_score": total_activity
            })

    active_users = sorted(active_users, key=lambda x: x["activity_score"], reverse=True)[:5]

    rating_distribution = []
    for value in range(1, 6):
        rating_distribution.append({
            "rating": value,
            "count": Rating.query.filter_by(rating=value).count()
        })

    precision_demo = 84
    recall_demo = 78
    f1_demo = 81

    return render_template(
        "dashboard.html",
        total_books=total_books,
        total_categories=total_categories,
        total_users=total_users,
        total_favorites=total_favorites,
        total_ratings=total_ratings,
        category_stats=category_stats,
        top_rated_books=top_rated_books,
        most_favorited_books=most_favorited_books,
        active_users=active_users,
        rating_distribution=rating_distribution,
        precision_demo=precision_demo,
        recall_demo=recall_demo,
        f1_demo=f1_demo
    )


@app.route("/admin/books")
def admin_books():
    if not admin_required():
        return redirect(url_for("login"))

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

    books = query.all()
    categories = Category.query.all()
    total_categories = Category.query.count()
    total_books = Book.query.count()

    return render_template(
        "admin_books.html",
        books=books,
        categories=categories,
        total_categories=total_categories,
        total_books=total_books,
        search=search,
        selected_category=category_id
    )


@app.route("/admin/books/add", methods=["GET", "POST"])
def add_book():
    if not admin_required():
        return redirect(url_for("login"))

    categories = Category.query.all()

    if request.method == "POST":
        new_book = Book(
            title=request.form["title"],
            author=request.form["author"],
            category_id=request.form["category_id"],
            published_year=request.form["published_year"],
            image=request.form["image"],
            description=request.form["description"]
        )

        db.session.add(new_book)
        db.session.commit()

        flash("Book added successfully.", "success")
        return redirect(url_for("admin_books"))

    return render_template("add_book.html", categories=categories)


@app.route("/admin/books/edit/<int:book_id>", methods=["GET", "POST"])
def edit_book(book_id):
    if not admin_required():
        return redirect(url_for("login"))

    book = Book.query.get_or_404(book_id)
    categories = Category.query.all()

    if request.method == "POST":
        book.title = request.form["title"]
        book.author = request.form["author"]
        book.category_id = request.form["category_id"]
        book.published_year = request.form["published_year"]
        book.image = request.form["image"]
        book.description = request.form["description"]

        db.session.commit()

        flash("Book updated successfully.", "success")
        return redirect(url_for("admin_books"))

    return render_template(
        "edit_book.html",
        book=book,
        categories=categories
    )


@app.route("/admin/books/delete/<int:book_id>", methods=["POST"])
def delete_book(book_id):
    if not admin_required():
        return redirect(url_for("login"))

    book = Book.query.get_or_404(book_id)

    Favorite.query.filter_by(book_id=book.id).delete()
    Rating.query.filter_by(book_id=book.id).delete()

    db.session.delete(book)
    db.session.commit()

    flash("Book deleted successfully.", "success")
    return redirect(url_for("admin_books"))


@app.route("/admin/categories")
def admin_categories():
    if not admin_required():
        return redirect(url_for("login"))

    search = request.args.get("search", "")

    query = Category.query

    if search:
        query = query.filter(
            Category.name.like(f"%{search}%")
        )

    categories = query.all()

    total_categories = Category.query.count()
    total_books = Book.query.count()

    return render_template(
        "admin_categories.html",
        categories=categories,
        total_categories=total_categories,
        total_books=total_books,
        search=search
    )


@app.route("/admin/categories/add", methods=["GET", "POST"])
def add_category():
    if not admin_required():
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]

        existing_category = Category.query.filter_by(name=name).first()

        if existing_category:
            flash("Category already exists.", "warning")
            return redirect(url_for("add_category"))

        new_category = Category(name=name)

        db.session.add(new_category)
        db.session.commit()

        flash("Category added successfully.", "success")
        return redirect(url_for("admin_categories"))

    return render_template("add_category.html")


@app.route("/admin/categories/edit/<int:category_id>", methods=["GET", "POST"])
def edit_category(category_id):
    if not admin_required():
        return redirect(url_for("login"))

    category = Category.query.get_or_404(category_id)

    if request.method == "POST":
        category.name = request.form["name"]

        db.session.commit()

        flash("Category updated successfully.", "success")
        return redirect(url_for("admin_categories"))

    return render_template(
        "edit_category.html",
        category=category
    )


@app.route("/admin/categories/delete/<int:category_id>", methods=["POST"])
def delete_category(category_id):
    if not admin_required():
        return redirect(url_for("login"))

    category = Category.query.get_or_404(category_id)

    books_in_category = Book.query.filter_by(category_id=category.id).count()

    if books_in_category > 0:
        flash("This category cannot be deleted because it contains books.", "danger")
        return redirect(url_for("admin_categories"))

    db.session.delete(category)
    db.session.commit()

    flash("Category deleted successfully.", "success")
    return redirect(url_for("admin_categories"))


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

    similar_books = Book.query.filter(
        Book.category_id == book.category_id,
        Book.id != book.id
    ).limit(4).all()

    return render_template(
        "book_details.html",
        book=book,
        is_favorite=is_favorite,
        user_rating=user_rating,
        average_rating=average_rating,
        rating_count=len(ratings),
        similar_books=similar_books
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
    if not admin_required():
        return redirect(url_for("login"))

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

@app.route("/remove-favorite/<int:book_id>")
def remove_favorite(book_id):
    if not session.get("user_id"):
        flash("Please login to manage favorites.", "warning")
        return redirect(url_for("login"))

    favorite = Favorite.query.filter_by(
        user_id=session["user_id"],
        book_id=book_id
    ).first()

    if favorite:
        db.session.delete(favorite)
        db.session.commit()
        flash("Book removed from favorites.", "success")
    else:
        flash("This book is not in your favorites.", "info")

    return redirect(request.referrer or url_for("books"))


@app.route("/remove-rating/<int:book_id>", methods=["POST"])
def remove_rating(book_id):
    if not session.get("user_id"):
        flash("Please login to manage ratings.", "warning")
        return redirect(url_for("login"))

    rating = Rating.query.filter_by(
        user_id=session["user_id"],
        book_id=book_id
    ).first()

    if rating:
        db.session.delete(rating)
        db.session.commit()
        flash("Your rating has been removed.", "success")
    else:
        flash("No rating found for this book.", "info")

    return redirect(url_for("book_details", book_id=book_id))

@app.route("/recommendations")
def recommendations():
    if not session.get("user_id"):
        flash("Please login to view your recommendations.", "warning")
        return redirect(url_for("login"))

    favorites = Favorite.query.filter_by(user_id=session["user_id"]).all()
    favorite_book_ids = [favorite.book_id for favorite in favorites]

    favorite_books = Book.query.filter(Book.id.in_(favorite_book_ids)).all()

    highly_rated_records = Rating.query.filter(
        Rating.user_id == session["user_id"],
        Rating.rating >= 4
    ).all()

    highly_rated_book_ids = [
        rating.book_id for rating in highly_rated_records
    ]

    highly_rated_books = Book.query.filter(
        Book.id.in_(highly_rated_book_ids)
    ).all()

    all_books = Book.query.all()

    recommended_items = get_content_based_recommendations(
        all_books=all_books,
        favorite_books=favorite_books,
        highly_rated_books=highly_rated_books,
        top_n=8
    )

    for item in recommended_items:
        if item["score"] >= 75:
            item["confidence"] = "High Match"
            item["badge_class"] = "bg-success"
        elif item["score"] >= 50:
            item["confidence"] = "Medium Match"
            item["badge_class"] = "bg-warning text-dark"
        else:
            item["confidence"] = "Low Match"
            item["badge_class"] = "bg-secondary"

    return render_template(
        "recommendations.html",
        favorite_books=favorite_books,
        recommended_items=recommended_items
    )

    for item in recommended_items:
        if item["score"] >= 75:
            item["confidence"] = "High Match"
            item["badge_class"] = "bg-success"
        elif item["score"] >= 50:
            item["confidence"] = "Medium Match"
            item["badge_class"] = "bg-warning text-dark"
        else:
            item["confidence"] = "Low Match"
            item["badge_class"] = "bg-secondary"

    return render_template(
        "recommendations.html",
        favorite_books=favorite_books,
        recommended_items=recommended_items
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