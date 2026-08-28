import os
import uuid
import re
import requests
from datetime import datetime, timedelta
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

# KaranPay Config
KARANPAY_KEY_1 = "guru131e012b5141689b9135317fb6fa7f"
KARANPAY_KEY_2 = "guru1eff587f747b3df8c7a355570f90ce"
KARANPAY_CREATE_URL = "https://gurupaygateway.com/api/create-order"
KARANPAY_STATUS_URL = "https://gurupaygateway.com/api/check-status"

def get_karanpay_key(order_id):
    if order_id.startswith("ADD2_"): return KARANPAY_KEY_2
    return KARANPAY_KEY_1

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

@app.route("/deposit", methods=["GET", "POST"])
def deposit():
    if "user_id" not in session: return redirect("/")
    user_id = session["user_id"]
    user = db.users.find_one({"user_id": user_id})
    
    if request.method == "POST":
        amount = float(request.form.get("amount", 0))
        gateway = request.form.get("gateway", "1")
        if amount < 1:
            return render_template("deposit.html", user=user, balance=user.get("balance", 0.0), error="Minimum amount is ₹1")
            
        order_prefix = "ADD1_" if gateway == "1" else "ADD2_"
        order_id = f"{order_prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"
        customer_name = session.get("username", "WebUser")
        
        payload = {"amount": f"{amount:.2f}", "order_id": order_id, "customer_name": customer_name}
        headers = {"X-Guru-Key": get_karanpay_key(order_id), "Content-Type": "application/json"}
        
        try:
            resp = requests.post(KARANPAY_CREATE_URL, json=payload, headers=headers, timeout=20).json()
            if resp.get("status") == "success":
                payment_url = resp.get("data", {}).get("payment_url") or resp.get("payment_url")
                upi_url = payment_url
                try:
                    html_resp = requests.get(payment_url, timeout=10).text
                    matches = re.findall(r'upi://pay\?[^\"\'<>]+', html_resp)
                    if matches: upi_url = matches[0].replace("&amp;", "&")
                except: pass
                
                db.orders.insert_one({"order_id": order_id, "user_id": user_id, "amount": amount, "status": "pending", "utr": "", "sender": "", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
                
                return render_template("deposit_pay.html", order_id=order_id, amount=amount, upi_url=upi_url, payment_url=payment_url)
        except Exception as e:
            return render_template("deposit.html", user=user, balance=user.get("balance", 0.0), error="Gateway Error: " + str(e))
            
    return render_template("deposit.html", user=user, balance=user.get("balance", 0.0))

@app.route("/check_payment/<order_id>")
def check_payment(order_id):
    if "user_id" not in session: return jsonify({"success": False})
    order = db.orders.find_one({"order_id": order_id})
    if not order: return jsonify({"success": False})
    if order["status"] == "completed": return jsonify({"success": True})
    
    headers = {"X-Guru-Key": get_karanpay_key(order_id), "Content-Type": "application/json"}
    try:
        resp = requests.post(KARANPAY_STATUS_URL, json={"order_id": order_id}, headers=headers, timeout=10).json()
        if resp.get("status") == "success" and resp.get("data", {}).get("payment_status") == "success":
            d = resp["data"]
            user_id = order["user_id"]
            amount = d.get("amount", order["amount"])
            utr = d.get("utr", "N/A")
            sender = d.get("customer_name", "Unknown")
            
            res = db.orders.update_one({"order_id": order_id, "status": "pending"}, {"$set": {"status": "completed", "utr": utr, "sender": sender}})
            if res.modified_count > 0:
                db.users.update_one({"user_id": user_id}, {"$inc": {"balance": amount}})
                db.deposit_history.insert_one({"user_id": user_id, "order_id": order_id, "amount": amount, "utr": utr, "sender": sender, "status": "completed", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
                return jsonify({"success": True})
    except:
        pass
    return jsonify({"success": False})


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
        
    db.users.update_one({"user_id": user_id, "balance": {"$gte": price}}, {"$inc": {"balance": -price}})
    
    payload = {'api_key': API_KEY, 'action': 'buy', 'product_id': str(plan["product_id"]), 'duration': str(plan["plan_name"]), 'android_id': android_id}
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'x-master-key': MASTER_KEY}
    
    try:
        tls_session = tls_client.Session(client_identifier="chrome_112")
        res = tls_session.post(API_ENDPOINT, data=payload, headers=headers, timeout_seconds=15)
        data = res.json()
        key = data.get("key") or data.get("license") or "Error fetching key"
        
        if "Error" not in key:
            db.history.insert_one({"user_id": user_id, "product": plan["name"], "plan": plan["plan_name"], "price": price, "license_key": key, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            return jsonify({"success": True, "key": key})
        else:
            db.users.update_one({"user_id": user_id}, {"$inc": {"balance": price}})
            return jsonify({"success": False, "msg": "API Error: " + key})
    except Exception as e:
        db.users.update_one({"user_id": user_id}, {"$inc": {"balance": price}})
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

@app.route("/admin/product/edit/<int:pid>", methods=["GET", "POST"])
def admin_edit_product(pid):
    if not session.get("admin"): return redirect("/admin")
    product = db.products.find_one({"id": pid})
    if not product: return redirect("/admin/products")
    
    if request.method == "POST":
        media_url = request.form.get("media_url", "")
        features = request.form.get("features", "")
        db.products.update_one({"id": pid}, {"$set": {"media_url": media_url, "features": features}})
        return redirect("/admin/products")
        
    return render_template("admin/edit_product.html", product=product)

@app.route("/admin/product/delete/<int:pid>")
def admin_delete_product(pid):
    if not session.get("admin"): return redirect("/admin")
    db.products.delete_one({"id": pid})
    return redirect("/admin/products")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
