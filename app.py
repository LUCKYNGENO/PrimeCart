from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
from pymysql.cursors import DictCursor
import os
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
# Upload folder
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# MySQL Configuration
app.config["MYSQL_HOST"] = config.MYSQL_HOST
app.config["MYSQL_USER"] = config.MYSQL_USER
app.config["MYSQL_PASSWORD"] = config.MYSQL_PASSWORD
app.config["MYSQL_DB"] = config.MYSQL_DB
app.config["MYSQL_PORT"] = config.MYSQL_PORT

def get_db():
    return pymysql.connect(
        host=config.MYSQL_HOST,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DB,
        port=config.MYSQL_PORT,
        ssl={"ssl": {}},
        cursorclass=DictCursor,
        autocommit=True
    )


# ==========================
# HELPERS
# ==========================

def allowed_file(filename):
    """Check if uploaded file has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required():
    """Returns True if admin is logged in, False otherwise."""
    return "admin" in session


# ==========================
# HOME PAGE
# ==========================

# ==========================
# HOME PAGE
# ==========================

@app.route("/")
def home():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()

    conn = get_db()
    cur = conn.cursor()

    # Featured products
    cur.execute("SELECT * FROM products WHERE featured = TRUE")
    featured_products = cur.fetchall()

    # Trending products
    cur.execute("""
        SELECT * FROM products
        ORDER BY rating DESC
        LIMIT 4
    """)
    trending = cur.fetchall()

    # Products
    if search:
        cur.execute(
            "SELECT * FROM products WHERE name LIKE %s",
            ("%" + search + "%",)
        )
    elif category:
        cur.execute(
            "SELECT * FROM products WHERE category=%s",
            (category,)
        )
    else:
        cur.execute("SELECT * FROM products")

    products = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "index.html",
        products=products,
        featured_products=featured_products,
        trending=trending,
        search=search,
        category=category
    )


# ==========================
# AUTH — LOGIN / LOGOUT
# ==========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if admin_required():
        return redirect(url_for("admin"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template(
                "login.html",
                error="Please fill in all fields."
            )

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM admins WHERE username=%s",
            (username,)
        )

        admin = cur.fetchone()

        cur.close()
        conn.close()

        if admin and check_password_hash(admin["password"], password):
            session["admin"] = admin["id"]
            session["username"] = admin["username"]

            flash(
                "Welcome back, " + admin["username"] + "!",
                "success"
            )

            return redirect(url_for("admin"))

        return render_template(
            "login.html",
            error="Invalid username or password."
        )

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    session.pop("username", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ==========================
# PRODUCT — VIEW & REVIEWS
# ==========================

# ==========================
# PRODUCT — VIEW & REVIEWS
# ==========================

@app.route("/product/<int:id>")
def product(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM products WHERE id=%s",
        (id,)
    )

    product = cur.fetchone()

    if not product:
        cur.close()
        conn.close()
        flash("Product not found.", "error")
        return redirect(url_for("home"))

    cur.execute("""
        SELECT username, rating, comment, created_at
        FROM reviews
        WHERE product_id=%s
        ORDER BY created_at DESC
    """, (id,))

    reviews = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "product.html",
        product=product,
        reviews=reviews
    )


@app.route("/review/<int:id>", methods=["POST"])
def add_review(id):

    username = request.form.get("username", "").strip()
    rating = request.form.get("rating")
    comment = request.form.get("comment", "").strip()

    if not username or not rating or not comment:
        flash("Please fill in all review fields.", "error")
        return redirect(url_for("product", id=id))

    try:
        rating = int(rating)

        if rating < 1 or rating > 5:
            raise ValueError

    except ValueError:
        flash("Rating must be between 1 and 5.", "error")
        return redirect(url_for("product", id=id))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO reviews
        (product_id, username, rating, comment)
        VALUES
        (%s, %s, %s, %s)
    """, (id, username, rating, comment))

    conn.commit()

    cur.close()
    conn.close()

    flash("Review submitted successfully!", "success")

    return redirect(url_for("product", id=id))


# ==========================
# ADMIN DASHBOARD
# ==========================

@app.route("/admin")
def admin():

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM products")
    products = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM products")
    total_products = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM clicks")
    total_clicks = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM reviews")
    total_reviews = cur.fetchone()[0]

    cur.close()
    conn.close()

    return render_template(
        "admin.html",
        products=products,
        total_products=total_products,
        total_clicks=total_clicks,
        total_reviews=total_reviews
    )


# ==========================
# ADD PRODUCT
# ==========================

@app.route("/add_product", methods=["POST"])
def add_product():

    if not admin_required():
        return redirect(url_for("login"))

    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    price = request.form.get("price")
    affiliate_link = request.form.get("affiliate_link", "").strip()
    description = request.form.get("description", "").strip()
    discount = request.form.get("discount", 0)
    flash_sale = 1 if request.form.get("flash_sale") else 0

    if not name or not category or not price:
        flash("Name, category and price are required.", "error")
        return redirect(url_for("admin"))

    image = request.files.get("image")
    filename = ""

    if image and image.filename:

        if not allowed_file(image.filename):
            flash(
                "Invalid image format. Allowed: png, jpg, jpeg, gif, webp",
                "error"
            )
            return redirect(url_for("admin"))

        filename = secure_filename(image.filename)
        image.save(
            os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )
        )

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO products
        (
            name,
            category,
            price,
            image,
            affiliate_link,
            description,
            discount,
            flash_sale
        )
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        name,
        category,
        price,
        filename,
        affiliate_link,
        description,
        discount,
        flash_sale
    ))

    conn.commit()

    cur.close()
    conn.close()

    flash("Product added successfully!", "success")

    return redirect(url_for("admin"))


# ==========================
# EDIT PRODUCT
# ==========================

@app.route("/edit/<int:id>")
def edit_product():

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM products WHERE id=%s",
        (id,)
    )

    product = cur.fetchone()

    cur.close()
    conn.close()

    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("admin"))

    return render_template(
        "edit.html",
        product=product
    )


@app.route("/update/<int:id>", methods=["POST"])
def update_product(id):

    if not admin_required():
        return redirect(url_for("login"))

    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    price = request.form.get("price")
    affiliate_link = request.form.get("affiliate_link", "").strip()
    description = request.form.get("description", "").strip()

    if not name or not category or not price:
        flash("Name, category and price are required.", "error")
        return redirect(url_for("edit_product", id=id))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE products
        SET
            name=%s,
            category=%s,
            price=%s,
            affiliate_link=%s,
            description=%s
        WHERE id=%s
    """, (
        name,
        category,
        price,
        affiliate_link,
        description,
        id
    ))

    conn.commit()

    cur.close()
    conn.close()

    flash("Product updated successfully!", "success")

    return redirect(url_for("admin"))


# ==========================
# DELETE PRODUCT
# ==========================

@app.route("/delete/<int:id>")
def delete_product(id):

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM products WHERE id=%s",
        (id,)
    )

    conn.commit()

    cur.close()
    conn.close()

    flash("Product deleted.", "info")

    return redirect(url_for("admin"))


# ==========================
# BUY (Affiliate Click Tracking)
# ==========================

@app.route("/buy/<int:id>")
def buy_product(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT affiliate_link FROM products WHERE id=%s",
        (id,)
    )

    product = cur.fetchone()

    if not product:
        cur.close()
        conn.close()
        flash("Product not found.", "error")
        return redirect(url_for("home"))

    cur.execute(
        "INSERT INTO clicks (product_id) VALUES (%s)",
        (id,)
    )

    conn.commit()

    cur.close()
    conn.close()

    return redirect(product[0])


# ==========================
# WISHLIST
# ==========================

@app.route("/wishlist")
def wishlist():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT products.*
        FROM wishlist
        JOIN products
        ON wishlist.product_id = products.id
    """)

    products = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "wishlist.html",
        products=products
    )

@app.route("/wishlist/add/<int:id>")
def add_to_wishlist(id):
    cur = mysql.connection.cursor()

    # Prevent duplicate wishlist entries
    cur.execute(
        "SELECT id FROM wishlist WHERE product_id = %s",
        (id,)
    )
    existing = cur.fetchone()

    if not existing:
        cur.execute("INSERT INTO wishlist (product_id) VALUES (%s)", (id,))
        mysql.connection.commit()
        flash("Added to wishlist!", "success")
    else:
        flash("Already in your wishlist.", "info")

    cur.close()
    return redirect(url_for("wishlist"))


# ==========================
# REMOVE FROM WISHLIST
# ==========================

@app.route("/wishlist/remove/<int:id>")
def remove_from_wishlist(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM wishlist WHERE product_id=%s",
        (id,)
    )

    conn.commit()

    cur.close()
    conn.close()

    flash("Removed from wishlist.", "info")

    return redirect(url_for("wishlist"))


# ==========================
# CART (Session-based)
# ==========================

@app.route("/cart")
def cart():

    ids = session.get("cart", [])
    products = []

    if ids:

        conn = get_db()
        cur = conn.cursor()

        placeholders = ",".join(["%s"] * len(ids))

        cur.execute(
            f"SELECT * FROM products WHERE id IN ({placeholders})",
            tuple(ids)
        )

        products = cur.fetchall()

        cur.close()
        conn.close()

    return render_template(
        "cart.html",
        products=products
    )


@app.route("/cart/add/<int:id>")
def add_to_cart(id):

    if "cart" not in session:
        session["cart"] = []

    cart = session["cart"]

    if id not in cart:
        cart.append(id)
        flash("Added to cart!", "success")
    else:
        flash("Already in your cart.", "info")

    session["cart"] = cart

    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:id>")
def remove_from_cart(id):

    cart = session.get("cart", [])

    if id in cart:
        cart.remove(id)
        flash("Removed from cart.", "info")

    session["cart"] = cart

    return redirect(url_for("cart"))


@app.route("/cart/clear")
def clear_cart():

    session.pop("cart", None)

    flash("Cart cleared.", "info")

    return redirect(url_for("cart"))


# ==========================
# CONTACT
# ==========================

@app.route("/contact", methods=["GET", "POST"])
def contact():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()

        if not name or not email or not message:
            return render_template(
                "contact.html",
                error="Please fill in all fields."
            )

        print(f"[CONTACT] {name} <{email}>: {message}")

        return render_template(
            "contact.html",
            success="Thank you! Your message has been received."
        )

    return render_template("contact.html")


# ==========================
# ABOUT
# ==========================

@app.route("/about")
def about():
    return render_template("about.html")


# ==========================
# RUN APP
# ==========================

if __name__ == "__main__":
    app.run(debug=True)