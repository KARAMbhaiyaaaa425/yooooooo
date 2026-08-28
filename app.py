import os
from flask import Flask, render_template, request, redirect, session, jsonify
from pymongo import MongoClient
import tls_client

app = Flask(__name__)
app.secret_key = "karan_bhaiya_super_secret"

# MongoDB
client = MongoClient("mongodb+srv://notchff644_db_user:n6ghmq4Cuz3ViMcf@cluster0.pqt6pea.mongodb.net/?appName=Cluster0", tlsAllowInvalidCertificates=True)
db = client["karanpay_bot"]

# API Config
API_ENDPOINT = "https://adminpanels.shop/api/reseller_v1.php"
API_KEY = "4936a17fb44211207c7ca20bdc6a4a57"
MASTER_KEY = "a7f3e8b2c9d1f4a6b8c2d5e9f1a3b6c8"

# ================= USER ROUTES =================

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form.get("user_id")
        user = db.users.find_one({"user_id": user_id})
        if user:
            session["user_id"] = user_id
            session["username"] = user.get("username", "User")
            return redirect("/store")
        else:
            return render_template("login.html", error="User ID not found! Pehle Telegram bot par /start karein.")
    return render_template("login.html")

@app.route("/store")
def store():
    if "user_id" not in session: return redirect("/")
    user = db.users.find_one({"user_id": session["user_id"]})
    products = list(db.products.find({}).sort("order", 1))
    return render_template("store.html", user=user, balance=user.get("balance", 0.0), products=products)

@app.route("/profile")
def profile():
    if "user_id" not in session: return redirect("/")
    user = db.users.find_one({"user_id": session["user_id"]})
    return render_template("profile.html", user=user, balance=user.get("balance", 0.0))

@app.route("/history")
def history():
    if "user_id" not in session: return redirect("/")
    user_id = session["user_id"]
    orders = list(db.history.find({"user_id": user_id}).sort("date", -1))
    return render_template("history.html", orders=orders)

@app.route("/deposit_history")
def deposit_history():
    if "user_id" not in session: return redirect("/")
    user_id = session["user_id"]
    deposits = list(db.deposit_history.find({"user_id": user_id}).sort("timestamp", -1))
    return render_template("deposit_history.html", deposits=deposits)

@app.route("/transfer", methods=["GET", "POST"])
def transfer():
    if "user_id" not in session: return redirect("/")
    user = db.users.find_one({"user_id": session["user_id"]})
    msg = ""
    if request.method == "POST":
        target = request.form.get("target_id")
        amount = float(request.form.get("amount", 0))
        if amount >= 1 and user["balance"] >= amount:
            target_user = db.users.find_one({"user_id": target})
            if target_user and target != session["user_id"]:
                db.users.update_one({"user_id": session["user_id"]}, {"$inc": {"balance": -amount}})
                db.users.update_one({"user_id": target}, {"$inc": {"balance": amount}})
                msg = f"Success! Transferred ₹{amount} to {target}"
                user["balance"] -= amount
            else:
                msg = "Invalid Target User ID"
        else:
            msg = "Invalid amount or insufficient balance"
    return render_template("transfer.html", user=user, balance=user.get("balance", 0.0), msg=msg)

@app.route("/buy", methods=["POST"])
def buy():
    if "user_id" not in session:
        return jsonify({"success": False, "msg": "Not logged in"})
        
    user_id = session["user_id"]
    product_db_id = request.form.get("product_id")
    android_id = request.form.get("android_id", "0b9b969bc2e7997b")
    
    plan = db.products.find_one({"id": int(product_db_id)})
    if not plan:
        return jsonify({"success": False, "msg": "Product not found!"})
        
    price = plan["price"]
    user = db.users.find_one({"user_id": user_id})
    
    if user["balance"] < price:
        return jsonify({"success": False, "msg": f"Insufficient Balance! You need ₹{price}"})
        
    # Deduct balance
    db.users.update_one({"user_id": user_id, "balance": {"$gte": price}}, {"$inc": {"balance": -price}})
    
    # Fetch key from API
    payload = {
        'api_key': API_KEY,
        'action': 'buy',
        'product_id': str(plan["product_id"]),
        'duration': str(plan["plan_name"]),
        'android_id': android_id
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'x-master-key': MASTER_KEY}
    
    try:
        tls_session = tls_client.Session(client_identifier="chrome_112")
        res = tls_session.post(API_ENDPOINT, data=payload, headers=headers, timeout_seconds=15)
        data = res.json()
        key = data.get("key") or data.get("license") or "Error fetching key"
        
        if "Error" not in key:
            db.history.insert_one({"user_id": user_id, "product": plan["name"], "plan": plan["plan_name"], "price": price, "license_key": key})
            return jsonify({"success": True, "key": key})
        else:
            db.users.update_one({"user_id": user_id}, {"$inc": {"balance": price}}) # Refund
            return jsonify({"success": False, "msg": "API Error: " + key})
    except Exception as e:
        db.users.update_one({"user_id": user_id}, {"$inc": {"balance": price}}) # Refund
        return jsonify({"success": False, "msg": "Failed to connect to API"})

# ================= ADMIN ROUTES =================

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "karan123":
            session["admin"] = True
            return redirect("/admin/panel")
        else:
            return render_template("login.html", error="Invalid Admin Credentials", is_admin=True)
    return render_template("login.html", is_admin=True)

@app.route("/admin/panel")
def admin_panel():
    if not session.get("admin"): return redirect("/admin")
    
    total_users = db.users.count_documents({})
    users = list(db.users.find({}))
    total_balance = sum(u.get("balance", 0) for u in users)
    
    orders = db.orders.count_documents({"status": "completed"})
    
    return render_template("admin/panel.html", total_users=total_users, total_balance=total_balance, orders=orders)

@app.route("/admin/add_balance", methods=["GET", "POST"])
def admin_add_balance():
    if not session.get("admin"): return redirect("/admin")
    msg = ""
    if request.method == "POST":
        uid = request.form.get("user_id")
        amt = float(request.form.get("amount", 0))
        db.users.update_one({"user_id": uid}, {"$inc": {"balance": amt}})
        msg = f"Added ₹{amt} to {uid}"
    return render_template("admin/add_balance.html", msg=msg)

@app.route("/admin/products", methods=["GET"])
def admin_products():
    if not session.get("admin"): return redirect("/admin")
    products = list(db.products.find({}).sort("order", 1))
    return render_template("admin/products.html", products=products)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
