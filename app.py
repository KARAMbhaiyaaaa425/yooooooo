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

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form.get("user_id")
        user = db.users.find_one({"user_id": user_id})
        if user:
            session["user_id"] = user_id
            session["username"] = user.get("username", "User")
            return redirect("/dashboard")
        else:
            return render_template("login.html", error="User ID not found! Pehle Telegram bot par /start karein.")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")
    
    user = db.users.find_one({"user_id": session["user_id"]})
    balance = user.get("balance", 0.0)
    
    products = list(db.products.find({}).sort("order", 1))
    return render_template("dashboard.html", user=user, balance=balance, products=products)

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

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        # Hardcoded Admin Credentials
        if username == "admin" and password == "karan123":
            session["admin"] = True
            return redirect("/admin/panel")
        else:
            return render_template("login.html", error="Invalid Admin Credentials", is_admin=True)
    return render_template("login.html", is_admin=True)

@app.route("/admin/panel")
def admin_panel():
    if not session.get("admin"):
        return redirect("/admin")
        
    total_users = db.users.count_documents({})
    # Get total balance
    users = list(db.users.find({}))
    total_balance = sum(u.get("balance", 0) for u in users)
    
    return f"""
    <h1 style="color:red;">Owner Admin Panel</h1>
    <p>Total Users: {total_users}</p>
    <p>Total Users Balance: ₹{total_balance}</p>
    <a href="/logout">Logout</a>
    """

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
