"""
Tindahan Store POS  — Flask Backend
Multi-user · Full analytics · Render-ready
"""
import sqlite3, os, hashlib, secrets, functools
from datetime import datetime, timezone
from flask import (Flask, request, jsonify, render_template,
                   g, session, redirect, url_for)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DATABASE = os.path.join(os.path.dirname(__file__), "tindahan.db")

# ─────────────────────────── DB HELPERS ────────────────────────────

def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        db = g._db = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
    return db

@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, "_db", None)
    if db:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            password    TEXT    NOT NULL,
            store_name  TEXT    NOT NULL DEFAULT 'My Store',
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name        TEXT    NOT NULL,
            price       REAL    NOT NULL CHECK(price > 0),
            quantity    INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
            category    TEXT    DEFAULT 'General',
            image_data  TEXT,
            created_at  TEXT    DEFAULT (datetime('now')),
            UNIQUE(user_id, name)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            transaction_ref TEXT    NOT NULL,
            total           REAL    NOT NULL,
            amount_paid     REAL    NOT NULL,
            change_due      REAL    NOT NULL,
            total_items     INTEGER NOT NULL,
            discount        REAL    DEFAULT 0,
            note            TEXT    DEFAULT '',
            created_at      TEXT    DEFAULT (datetime('now')),
            UNIQUE(user_id, transaction_ref)
        );

        CREATE TABLE IF NOT EXISTS transaction_items (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
            product_id     INTEGER REFERENCES products(id) ON DELETE SET NULL,
            product_name   TEXT    NOT NULL,
            unit_price     REAL    NOT NULL,
            quantity       INTEGER NOT NULL,
            subtotal       REAL    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_products_user ON products(user_id);
        CREATE INDEX IF NOT EXISTS idx_txn_user      ON transactions(user_id);
        CREATE INDEX IF NOT EXISTS idx_txn_date      ON transactions(created_at);
        CREATE INDEX IF NOT EXISTS idx_txni_txn      ON transaction_items(transaction_id);
        """)
        db.commit()

# ─────────────────────────── AUTH ──────────────────────────────────

def hash_pw(pw):
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + pw).encode()).hexdigest()
    return f"{salt}:{h}"

def verify_pw(pw, stored):
    try:
        salt, h = stored.split(":")
        return hashlib.sha256((salt + pw).encode()).hexdigest() == h
    except Exception:
        return False

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json:
                return jsonify({"error": "Not authenticated"}), 401
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────── PAGES ─────────────────────────────────

@app.route("/")
def index():
    if "user_id" in session:
        return render_template("app.html")
    return render_template("auth.html")

@app.route("/app")
@login_required
def app_page():
    return render_template("app.html")

# ─────────────────────────── AUTH API ──────────────────────────────

@app.route("/api/auth/register", methods=["POST"])
def register():
    d          = request.get_json() or {}
    username   = (d.get("username") or "").strip()
    password   = d.get("password", "")
    store_name = (d.get("store_name") or "My Store").strip()

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    db = get_db()
    if db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
        return jsonify({"error": "Username already taken"}), 409

    cur = db.execute(
        "INSERT INTO users (username,password,store_name) VALUES (?,?,?)",
        (username, hash_pw(password), store_name)
    )
    db.commit()
    uid  = cur.lastrowid
    user = dict(db.execute("SELECT id,username,store_name FROM users WHERE id=?", (uid,)).fetchone())
    session.update(user_id=uid, username=user["username"], store_name=user["store_name"])
    return jsonify({"user": user}), 201

@app.route("/api/auth/login", methods=["POST"])
def login():
    d        = request.get_json() or {}
    username = (d.get("username") or "").strip()
    password = d.get("password", "")
    db  = get_db()
    row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row or not verify_pw(password, row["password"]):
        return jsonify({"error": "Invalid username or password"}), 401
    session.update(user_id=row["id"], username=row["username"], store_name=row["store_name"])
    return jsonify({"user": {"id": row["id"], "username": row["username"], "store_name": row["store_name"]}})

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/auth/me")
@login_required
def me():
    db  = get_db()
    row = db.execute("SELECT id,username,store_name FROM users WHERE id=?", (session["user_id"],)).fetchone()
    return jsonify(dict(row))

@app.route("/api/auth/update", methods=["PUT"])
@login_required
def update_profile():
    d          = request.get_json() or {}
    uid        = session["user_id"]
    db         = get_db()
    store_name = (d.get("store_name") or "").strip()
    new_pw     = d.get("new_password", "")
    if store_name:
        db.execute("UPDATE users SET store_name=? WHERE id=?", (store_name, uid))
        session["store_name"] = store_name
    if new_pw:
        if len(new_pw) < 6:
            return jsonify({"error": "Password must be ≥ 6 characters"}), 400
        db.execute("UPDATE users SET password=? WHERE id=?", (hash_pw(new_pw), uid))
    db.commit()
    return jsonify({"ok": True, "store_name": session["store_name"]})

# ─────────────────────────── PRODUCTS ──────────────────────────────

@app.route("/api/products")
@login_required
def get_products():
    uid = session["user_id"]
    rows = get_db().execute(
        "SELECT * FROM products WHERE user_id=? ORDER BY name", (uid,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/products", methods=["POST"])
@login_required
def add_product():
    d   = request.get_json() or {}
    uid = session["user_id"]
    name = (d.get("name") or "").strip()
    try:
        price = float(d["price"]); qty = int(d["quantity"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "price and quantity are required numbers"}), 400
    if not name:
        return jsonify({"error": "Name required"}), 400
    if price <= 0 or qty < 0:
        return jsonify({"error": "price>0, quantity>=0"}), 400
    category   = (d.get("category") or "General").strip()
    image_data = d.get("image_data")
    db = get_db()
    if db.execute("SELECT id FROM products WHERE user_id=? AND LOWER(name)=LOWER(?)", (uid, name)).fetchone():
        return jsonify({"error": f'"{name}" already exists'}), 409
    cur = db.execute(
        "INSERT INTO products (user_id,name,price,quantity,category,image_data) VALUES (?,?,?,?,?,?)",
        (uid, name, price, qty, category, image_data)
    )
    db.commit()
    return jsonify(dict(db.execute("SELECT * FROM products WHERE id=?", (cur.lastrowid,)).fetchone())), 201

@app.route("/api/products/<int:pid>", methods=["PUT"])
@login_required
def update_product(pid):
    uid = session["user_id"]
    db  = get_db()
    row = db.execute("SELECT * FROM products WHERE id=? AND user_id=?", (pid, uid)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    d  = request.get_json() or {}
    name       = (d.get("name") or row["name"]).strip()
    price      = float(d.get("price",    row["price"]))
    qty        = int(  d.get("quantity", row["quantity"]))
    category   = (d.get("category") or row["category"] or "General").strip()
    image_data = d.get("image_data", row["image_data"])
    if price <= 0 or qty < 0:
        return jsonify({"error": "price>0, quantity>=0"}), 400
    if db.execute("SELECT id FROM products WHERE user_id=? AND LOWER(name)=LOWER(?) AND id!=?", (uid,name,pid)).fetchone():
        return jsonify({"error": f'Another product named "{name}" already exists'}), 409
    db.execute("UPDATE products SET name=?,price=?,quantity=?,category=?,image_data=? WHERE id=?",
               (name, price, qty, category, image_data, pid))
    db.commit()
    return jsonify(dict(db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()))

@app.route("/api/products/<int:pid>/restock", methods=["POST"])
@login_required
def restock(pid):
    uid = session["user_id"]
    db  = get_db()
    row = db.execute("SELECT * FROM products WHERE id=? AND user_id=?", (pid, uid)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    add = int((request.get_json() or {}).get("quantity", 0))
    if add <= 0:
        return jsonify({"error": "quantity must be > 0"}), 400
    db.execute("UPDATE products SET quantity=quantity+? WHERE id=?", (add, pid))
    db.commit()
    return jsonify(dict(db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()))

@app.route("/api/products/<int:pid>", methods=["DELETE"])
@login_required
def delete_product(pid):
    uid = session["user_id"]
    db  = get_db()
    if not db.execute("SELECT id FROM products WHERE id=? AND user_id=?", (pid, uid)).fetchone():
        return jsonify({"error": "Not found"}), 404
    db.execute("DELETE FROM products WHERE id=?", (pid,))
    db.commit()
    return jsonify({"ok": True})

# ─────────────────────────── CHECKOUT ──────────────────────────────

@app.route("/api/checkout", methods=["POST"])
@login_required
def checkout():
    uid  = session["user_id"]
    d    = request.get_json() or {}
    cart = d.get("cart", [])
    paid = float(d.get("amount_paid", 0))
    disc = float(d.get("discount", 0))
    note = (d.get("note") or "").strip()
    if not cart:
        return jsonify({"error": "Cart is empty"}), 400

    db = get_db()
    total, resolved = 0.0, []
    for item in cart:
        row = db.execute("SELECT * FROM products WHERE id=? AND user_id=?",
                         (item["id"], uid)).fetchone()
        if not row:
            return jsonify({"error": f'Product not found'}), 404
        qty = int(item.get("cartQuantity", 0))
        if row["quantity"] < qty:
            return jsonify({"error": f'Not enough stock for "{row["name"]}"'}), 400
        sub = row["price"] * qty
        total += sub
        resolved.append({"row": row, "qty": qty, "sub": sub})

    disc  = min(disc, total)
    after = total - disc
    if paid < after:
        return jsonify({"error": f"Insufficient payment (need ₱{after:.2f})"}), 400

    change  = paid - after
    n_items = sum(r["qty"] for r in resolved)
    count   = db.execute("SELECT COUNT(*) as c FROM transactions WHERE user_id=?", (uid,)).fetchone()["c"]
    ref     = f"TXN{uid:03d}-{(count+1):05d}"

    cur = db.execute(
        "INSERT INTO transactions (user_id,transaction_ref,total,amount_paid,change_due,total_items,discount,note) VALUES (?,?,?,?,?,?,?,?)",
        (uid, ref, after, paid, change, n_items, disc, note)
    )
    txn_id = cur.lastrowid
    for r in resolved:
        db.execute(
            "INSERT INTO transaction_items (transaction_id,product_id,product_name,unit_price,quantity,subtotal) VALUES (?,?,?,?,?,?)",
            (txn_id, r["row"]["id"], r["row"]["name"], r["row"]["price"], r["qty"], r["sub"])
        )
        db.execute("UPDATE products SET quantity=quantity-? WHERE id=?", (r["qty"], r["row"]["id"]))
    db.commit()

    txn = dict(db.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone())
    txn["items"] = [dict(i) for i in db.execute(
        "SELECT * FROM transaction_items WHERE transaction_id=?", (txn_id,)
    ).fetchall()]
    return jsonify(txn), 201

# ─────────────────────────── SALES & ANALYTICS ─────────────────────

@app.route("/api/sales/summary")
@login_required
def sales_summary():
    uid = session["user_id"]
    row = get_db().execute("""
        SELECT COUNT(*) AS total_transactions,
               COALESCE(SUM(total),0)       AS total_sales,
               COALESCE(SUM(total_items),0) AS total_items_sold
        FROM transactions WHERE user_id=?
    """, (uid,)).fetchone()
    return jsonify(dict(row))

@app.route("/api/sales/monthly")
@login_required
def sales_monthly():
    uid  = session["user_id"]
    year = request.args.get("year", str(datetime.now().year))
    rows = get_db().execute("""
        SELECT strftime('%m', created_at)    AS month,
               COUNT(*)                      AS orders,
               COALESCE(SUM(total),0)        AS revenue,
               COALESCE(SUM(total_items),0)  AS items
        FROM transactions
        WHERE user_id=? AND strftime('%Y', created_at)=?
        GROUP BY month ORDER BY month
    """, (uid, year)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/sales/yearly")
@login_required
def sales_yearly():
    uid  = session["user_id"]
    rows = get_db().execute("""
        SELECT strftime('%Y', created_at)    AS year,
               COUNT(*)                      AS orders,
               COALESCE(SUM(total),0)        AS revenue,
               COALESCE(SUM(total_items),0)  AS items
        FROM transactions WHERE user_id=?
        GROUP BY year ORDER BY year DESC
    """, (uid,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/sales/top-products")
@login_required
def top_products():
    uid   = session["user_id"]
    limit = int(request.args.get("limit", 8))
    rows  = get_db().execute("""
        SELECT ti.product_name,
               SUM(ti.quantity) AS total_qty,
               SUM(ti.subtotal) AS total_revenue
        FROM transaction_items ti
        JOIN transactions t ON t.id=ti.transaction_id
        WHERE t.user_id=?
        GROUP BY ti.product_name
        ORDER BY total_revenue DESC LIMIT ?
    """, (uid, limit)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/sales/daily")
@login_required
def sales_daily():
    uid  = session["user_id"]
    days = int(request.args.get("days", 30))
    rows = get_db().execute("""
        SELECT strftime('%Y-%m-%d', created_at) AS day,
               COUNT(*)               AS orders,
               COALESCE(SUM(total),0) AS revenue
        FROM transactions
        WHERE user_id=? AND created_at >= datetime('now', ? || ' days')
        GROUP BY day ORDER BY day
    """, (uid, f"-{days}")).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/sales/transactions")
@login_required
def get_transactions():
    uid    = session["user_id"]
    limit  = int(request.args.get("limit", 20))
    page   = int(request.args.get("page", 1))
    month  = request.args.get("month")
    year   = request.args.get("year")
    offset = (page - 1) * limit

    q, params = "WHERE user_id=?", [uid]
    if month:
        q += " AND strftime('%Y-%m',created_at)=?"; params.append(month)
    elif year:
        q += " AND strftime('%Y',created_at)=?";    params.append(year)

    db    = get_db()
    total = db.execute(f"SELECT COUNT(*) as c FROM transactions {q}", params).fetchone()["c"]
    rows  = db.execute(
        f"SELECT * FROM transactions {q} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()
    txns = []
    for r in rows:
        t = dict(r)
        t["items"] = [dict(i) for i in db.execute(
            "SELECT * FROM transaction_items WHERE transaction_id=?", (r["id"],)
        ).fetchall()]
        txns.append(t)
    return jsonify({"transactions": txns, "total": total, "page": page, "limit": limit})

@app.route("/api/sales/transactions/<int:tid>", methods=["DELETE"])
@login_required
def delete_transaction(tid):
    uid = session["user_id"]
    db  = get_db()
    row = db.execute("SELECT * FROM transactions WHERE id=? AND user_id=?", (tid, uid)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    items = db.execute("SELECT * FROM transaction_items WHERE transaction_id=?", (tid,)).fetchall()
    for item in items:
        if item["product_id"]:
            db.execute("UPDATE products SET quantity=quantity+? WHERE id=? AND user_id=?",
                       (item["quantity"], item["product_id"], uid))
    db.execute("DELETE FROM transactions WHERE id=?", (tid,))
    db.commit()
    return jsonify({"ok": True})

# ─────────────────────────── DASHBOARD ─────────────────────────────

@app.route("/api/dashboard")
@login_required
def dashboard():
    uid   = session["user_id"]
    db    = get_db()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month = datetime.now(timezone.utc).strftime("%Y-%m")

    t_row = db.execute("""
        SELECT COALESCE(SUM(total),0) AS revenue, COUNT(*) AS orders
        FROM transactions WHERE user_id=? AND DATE(created_at)=?
    """, (uid, today)).fetchone()

    m_row = db.execute("""
        SELECT COALESCE(SUM(total),0) AS revenue, COUNT(*) AS orders
        FROM transactions WHERE user_id=? AND strftime('%Y-%m',created_at)=?
    """, (uid, month)).fetchone()

    low = db.execute("""
        SELECT id,name,quantity,price FROM products
        WHERE user_id=? AND quantity<=5 AND quantity>0 ORDER BY quantity LIMIT 5
    """, (uid,)).fetchall()

    out   = db.execute("SELECT COUNT(*) as c FROM products WHERE user_id=? AND quantity=0", (uid,)).fetchone()
    total = db.execute("SELECT COUNT(*) as c FROM products WHERE user_id=?", (uid,)).fetchone()

    return jsonify({
        "today":          dict(t_row),
        "month":          dict(m_row),
        "low_stock":      [dict(r) for r in low],
        "out_of_stock":   out["c"],
        "total_products": total["c"],
        "store_name":     session.get("store_name", "My Store"),
        "username":       session.get("username", "")
    })


init_db()

if __name__ == "__main__":
    print("→ http://localhost:5000")
    app.run(debug=True, port=5000)
