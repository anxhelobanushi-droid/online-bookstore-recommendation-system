from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from models import db, User, Category, Book, Favorite

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/books")
def books():
    search = request.args.get("search", "")

    if search:
        all_books = Book.query.filter(
            (Book.title.like(f"%{search}%")) |
            (Book.author.like(f"%{search}%"))
        ).all()
    else:
        all_books = Book.query.all()

    favorite_book_ids = []

    if session.get("user_id"):
        favorites = Favorite.query.filter_by(user_id=session["user_id"]).all()
        favorite_book_ids = [favorite.book_id for favorite in favorites]

    return render_template(
        "books.html",
        books=all_books,
        search=search,
        favorite_book_ids=favorite_book_ids
    )


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

    return redirect(url_for("books"))


@app.route("/recommendations")
def recommendations():
    if not session.get("user_id"):
        flash("Please login to view your recommendations.", "warning")
        return redirect(url_for("login"))

    favorites = Favorite.query.filter_by(user_id=session["user_id"]).all()
    favorite_book_ids = [favorite.book_id for favorite in favorites]

    favorite_books = Book.query.filter(Book.id.in_(favorite_book_ids)).all()

    favorite_category_ids = list(
        set(book.category_id for book in favorite_books)
    )

    recommended_books = []

    if favorite_category_ids:
        recommended_books = Book.query.filter(
            Book.category_id.in_(favorite_category_ids),
            ~Book.id.in_(favorite_book_ids)
        ).all()

    return render_template(
        "recommendations.html",
        favorite_books=favorite_books,
        recommended_books=recommended_books
    )


@app.route("/seed-data")
def seed_data():
    if Category.query.first():
        flash("Data already exists.", "info")
        return redirect(url_for("books"))

    categories = [
        "Technology", "Science", "Business", "Psychology", "Education",
        "History", "Biography", "Fiction", "Fantasy", "Romance"
    ]

    for category_name in categories:
        db.session.add(Category(name=category_name))

    db.session.commit()

    sample_books = [
        ("Clean Code", "Robert C. Martin", "Technology", 2008, "clean_code.jpg"),
        ("Python Crash Course", "Eric Matthes", "Technology", 2019, "python_crash_course.jpg"),
        ("Artificial Intelligence", "Stuart Russell", "Technology", 2020, "artificial_intelligence.jpg"),
        ("Atomic Habits", "James Clear", "Psychology", 2018, "atomic_habits.jpg"),
        ("The Psychology of Money", "Morgan Housel", "Business", 2020, "psychology_of_money.jpg"),
        ("Sapiens", "Yuval Noah Harari", "History", 2011, "sapiens.jpg"),
        ("Educated", "Tara Westover", "Biography", 2018, "educated.jpg"),
        ("The Hobbit", "J.R.R. Tolkien", "Fantasy", 1937, "the_hobbit.jpg"),
        ("Pride and Prejudice", "Jane Austen", "Romance", 1813, "pride_and_prejudice.jpg"),
        ("A Brief History of Time", "Stephen Hawking", "Science", 1988, "brief_history_of_time.jpg")
    ]

    for title, author, category_name, year, image in sample_books:
        category = Category.query.filter_by(name=category_name).first()

        book = Book(
            title=title,
            author=author,
            description="A selected book from the SmartBooks online library.",
            published_year=year,
            image=image,
            category_id=category.id
        )

        db.session.add(book)

    db.session.commit()

    flash("Initial books and categories added successfully.", "success")
    return redirect(url_for("books"))


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