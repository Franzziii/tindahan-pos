# 🏪 Tindahan Store POS

Full-stack Point-of-Sale system — Flask + SQLite + Claymorphism UI  
Multi-user · Sales Analytics · Render.com ready

---

## ✨ Features

### 🔐 Auth
- Register with store name, username, password
- Login / Logout
- Each user has their own isolated data (products, sales, transactions)
- Update store name and password from Profile

### 🛍️ Products
- Add / Edit / Delete products
- Upload product photo (drag & drop or tap)
- Category tagging (Beverages, Snacks, Canned Goods, etc.)
- Low stock + out-of-stock alerts on dashboard
- Restock existing products

### 🛒 Cart & Payment
- Tap any product to add to cart
- Increase / decrease / inline-edit quantities
- **Discount field** — apply peso amount discount
- **Note field** — e.g. "Senior discount"
- Live change calculator
- Complete Sale button → receipt modal

### 📊 Sales Analytics
- **Transactions** — paginated list, filter by month, delete individual transactions (restores stock), print
- **Monthly** — all 12 months in a grid for any year, print report
- **Yearly** — year-over-year summary, print report
- **Top Items** — animated bar chart of best-selling products
- Dashboard KPIs: Today's revenue, This month's revenue, low stock list

### 🖨️ Print
- Print individual receipt (80mm thermal-ready)
- Print transaction list for any month
- Print monthly report
- Print yearly report

---

## 🚀 Local Setup

```bash
pip install flask gunicorn
python app.py
# Open http://localhost:5000
```

---

## ☁️ Deploy to Render.com

1. Push this folder to a GitHub repository

2. Go to https://render.com → **New → Web Service**

3. Connect your GitHub repo

4. Settings:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`

5. Add environment variable:
   - `SECRET_KEY` → click **Generate** (random value)

6. Click **Deploy** — done! 🎉

> **Note:** Render's free tier uses ephemeral storage. The SQLite database resets on redeploy. For persistent data, upgrade to a paid plan or migrate to PostgreSQL.

---

## 📁 File Structure

```
tindahan_pos/
├── app.py               ← Flask backend + REST API
├── requirements.txt     ← Flask + gunicorn
├── render.yaml          ← One-click Render config
├── templates/
│   ├── auth.html        ← Login / Register page
│   └── app.html         ← Main POS app (all pages)
└── README.md
```

---

## 🛠️ API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/auth/me` | Current user |
| PUT | `/api/auth/update` | Update store name / password |
| GET | `/api/products` | List products |
| POST | `/api/products` | Add product |
| PUT | `/api/products/:id` | Update product |
| DELETE | `/api/products/:id` | Delete product |
| POST | `/api/products/:id/restock` | Add stock |
| POST | `/api/checkout` | Process sale |
| GET | `/api/dashboard` | Dashboard data |
| GET | `/api/sales/summary` | All-time totals |
| GET | `/api/sales/monthly?year=2026` | Monthly breakdown |
| GET | `/api/sales/yearly` | Year-over-year |
| GET | `/api/sales/top-products` | Best sellers |
| GET | `/api/sales/transactions?page=1&month=2026-03` | Transaction list |
| DELETE | `/api/sales/transactions/:id` | Delete transaction (restores stock) |
