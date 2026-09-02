import os
import uuid
import re
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, jsonify
from pymongo import MongoClient
import tls_client
import hashlib
import hmac

app = Flask(__name__)
app.secret_key = 'karan_bhaiya_super_secret'

# MongoDB
import urllib.parse
# ----------------------------------------------------
client = MongoClient('mongodb+srv://karanbhaiyagithub_db_user:6XlEePVBUcU7KH1q@webdatabasae.jgeewtr.mongodb.net/?appName=webdatabasae', tlsAllowInvalidCertificates=True)
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
    settings = db.settings.find_one({"id": "global"}) or {}
    if order_id.startswith("ADD2_"): return settings.get("karanpay_key_2", KARANPAY_KEY_2)
    return settings.get("karanpay_key_1", KARANPAY_KEY_1)

# ================= MIDDLEWARE =================
@app.context_processor
def inject_global_settings():
    settings = db.settings.find_one({"id": "global"}) or {}
    if not settings.get("app_name"): settings["app_name"] = "Karan Store"
    if not settings.get("telegram"): settings["telegram"] = "Karan_store"
    return dict(global_settings=settings)

@app.before_request
def check_maintenance():
    if request.path.startswith("/admin") or request.path.startswith("/static"):
        return None
    settings = db.settings.find_one({"id": "global"})
    if settings and settings.get("maintenance_mode", False) and request.path != "/":
        return render_template("login.html", error="Store is currently under Maintenance. Please try again later.")
    return None

# ================= USER ROUTES =================


@app.context_processor
def inject_global_data():
    data = {
        "unread_count": 0,
        "balance": 0.0,
        "global_settings": db.settings.find_one({"id": "global"}) or {}
    }
    if "user_id" in session:
        user = db.users.find_one({"user_id": session["user_id"]})
        if user:
            last_seen = user.get("last_seen_notification", "")
            data["unread_count"] = db.notifications.count_documents({"date": {"": last_seen}})
            data["balance"] = user.get("balance", 0.0)
    return data

@app.route("/", methods=["GET", "POST"])
def login():
    settings = db.settings.find_one({"id": "global"})
    maintenance = settings.get("maintenance_mode", False) if settings else False

    if request.method == "POST":
        if maintenance:
            return render_template("login.html", error="Store is currently under Maintenance. Please try again later.")
            
        
        email = request.form.get("email")
        password = request.form.get("password")
        
        # Hidden Admin Login
        if email == "admin@karan.com" and password == "karan123":
            session["admin"] = True
            return redirect("/admin/panel")

        
        user = db.users.find_one({"email": email, "password": password})
        if user:
            session["user_id"] = user["user_id"]
            session["username"] = user.get("username", "User")
            return redirect("/dashboard")
        else:
            return render_template("login.html", error="Invalid Email or Password.")
            
    # Get error from query param if any
    error = request.args.get('error')
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    settings = db.settings.find_one({"id": "global"})
    maintenance = settings.get("maintenance_mode", False) if settings else False

    if request.method == "POST":
        if maintenance:
            return render_template("register.html", error="Store is currently under Maintenance.")
            
        username = request.form.get("username")
        
        email = request.form.get("email")
        password = request.form.get("password")
        
        # Hidden Admin Login
        if email == "admin@karan.com" and password == "karan123":
            session["admin"] = True
            return redirect("/admin/panel")

        
        if db.users.find_one({"email": email}):
            return render_template("register.html", error="Email is already registered. Please Login.")
        
        if db.users.find_one({"username": username}):
            return render_template("register.html", error="Username is taken. Choose another.")
            
        default_avatar = settings.get("default_avatar", "") if settings else ""
        default_banner = settings.get("default_banner", "") if settings else ""

        # Create user
        user_id = str(uuid.uuid4().hex[:10]) # Generate a 10 char ID
        db.users.insert_one({
            "user_id": user_id,
            "username": username,
            "email": email,
            "password": password,
            "balance": 0.0,
            "avatar": default_avatar,
            "banner": default_banner,
            "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Auto login
        session["user_id"] = user_id
        session["username"] = username
        return redirect("/dashboard")
        
    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session: return redirect("/")
    user = db.users.find_one({"user_id": session["user_id"]})
    
    # Calculate stats
    orders = list(db.history.find({"user_id": session["user_id"]}).sort("date", -1))
    total_orders = len(orders)
    total_spent = sum(float(o.get("price", 0)) for o in orders)
    active_keys_count = len(orders) # In a real app we'd check validity
    
    # Fake recent transactions for UI
    transactions = []
    
    # Add real deposits
    deposits = list(db.deposit_history.find({"user_id": session["user_id"]}).sort("timestamp", -1).limit(3))
    for d in deposits:
        is_owner = "OWNER" in d.get("order_id", "")
        transactions.append({
            "type": "deposit",
            "id": d.get("order_id"),
            "desc": "Added by Owner" if is_owner else "UPI Deposit",
            "amount": d.get("amount", 0),
            "date": d.get("timestamp", "").split(" ")[0]
        })
        
    return render_template("dashboard.html", user=user, balance=user.get("balance", 0.0), total_orders=total_orders, total_spent=total_spent, active_keys_count=active_keys_count, transactions=transactions)


@app.route("/download")
def download_app():
    if "user_id" not in session: return redirect("/")
    user = db.users.find_one({"user_id": session["user_id"]})
    settings = db.settings.find_one({"id": "global"}) or {}
    return render_template("download.html", user=user, global_settings=settings)

@app.route("/store")
def store():
    try:
        if "user_id" not in session: return redirect("/")
        user = db.users.find_one({"user_id": session["user_id"]})
        raw_products = list(db.products.find({}).sort("order", 1))
        
        settings = db.settings.find_one({"id": "global"}) or {}
        hidden_cats = [c.strip().upper() for c in settings.get("hidden_categories", "").split(",")]
        
        grouped_products = {}
        for p in raw_products:
            cat = p.get("category", "Uncategorized").upper()
            if cat in hidden_cats: continue
            if cat not in grouped_products:
                grouped_products[cat] = {}
            
            name = p.get("name", "Unknown")
            if name not in grouped_products[cat]:
                grouped_products[cat][name] = []
            
            grouped_products[cat][name].append(p)
            
        final_products = {}
        for cat, names in grouped_products.items():
            final_products[cat] = []
            for name, plans in names.items():
                if not plans: continue
                final_products[cat].append({
                    "name": name,
                    "plans": sorted(plans, key=lambda x: x.get("order", 0)),
                    "media_url": plans[0].get("media_url", "")
                })
                
        categories = list(final_products.keys())
        categories.sort()
        
        return render_template("store.html", user=user, balance=user.get("balance", 0.0) if user else 0.0, products=final_products, categories=categories, global_settings=settings)
    except Exception as e:
        import traceback
        return "<pre>" + traceback.format_exc() + "</pre>"

@app.route('/settings')
def user_settings():
    if 'user_id' not in session: return redirect('/')
    return render_template('user_settings.html', balance=db.users.find_one({'user_id': session['user_id']}).get('balance', 0.0))

@app.route('/settings/appearance')
def appearance():
    if 'user_id' not in session: return redirect('/')
    return render_template('appearance.html', balance=db.users.find_one({'user_id': session['user_id']}).get('balance', 0.0))

@app.route('/settings/about')
def about():
    if 'user_id' not in session: return redirect('/')
    return render_template('about.html', settings=db.settings.find_one({'id': 'global'}) or {}, balance=db.users.find_one({'user_id': session['user_id']}).get('balance', 0.0))

@app.route('/profile')
def profile():
    if "user_id" not in session: return redirect("/")
    user = db.users.find_one({"user_id": session["user_id"]})
    return render_template("profile.html", user=user, balance=user.get("balance", 0.0))

@app.route("/history")
def history():
    if "user_id" not in session: return redirect("/")
    user_id = session["user_id"]
    orders = list(db.history.find({"user_id": user_id}).sort("date", -1))
    
    # Inject media_url from products
    for order in orders:
        prod = db.products.find_one({"name": order.get("product"), "plan_name": order.get("plan")})
        if prod:
            order["media_url"] = prod.get("media_url", "")
        else:
            # Try to match just by name
            prod_any = db.products.find_one({"name": order.get("product")})
            if prod_any:
                order["media_url"] = prod_any.get("media_url", "")
            else:
                order["media_url"] = ""
                
    return render_template("history.html", history=orders)

@app.route("/deposit_history")
def deposit_history():
    if "user_id" not in session: return redirect("/")
    user_id = session["user_id"]
    deposits = list(db.deposit_history.find({"user_id": user_id}).sort("timestamp", -1))
    return render_template("deposit_history.html", history=deposits)

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
    error = ""
    if request.method == "POST":
        target = request.form.get("target_id")
        amount = float(request.form.get("amount", 0))
        if amount >= 1 and user.get("balance", 0) >= amount:
            target_user = db.users.find_one({"user_id": target})
            if target_user and target != session["user_id"]:
                db.users.update_one({"user_id": session["user_id"]}, {"$inc": {"balance": -amount}})
                db.users.update_one({"user_id": target}, {"$inc": {"balance": amount}})
                msg = f"Success! Transferred ?{amount} to {target}"
            else:
                error = "Invalid User ID or cannot transfer to yourself."
        else:
            error = "Invalid amount or insufficient balance."
            
    # Refresh user to get new balance
    user = db.users.find_one({"user_id": session["user_id"]})
    return render_template("transfer.html", user=user, balance=user.get("balance", 0.0), msg=msg, error=error)

@app.route("/buy", methods=["POST"])
def buy():
    try:
        if "user_id" not in session:
            return jsonify({"success": False, "msg": "Not logged in"})
            
        user_id = session["user_id"]
        product_db_id = request.form.get("product_id")
        android_id = request.form.get("android_id", "0b9b969bc2e7997b")
        
        if not product_db_id:
            return jsonify({"success": False, "msg": "Invalid product ID!"})
            
        plan = db.products.find_one({"id": int(product_db_id)})
        if not plan:
            return jsonify({"success": False, "msg": "Product not found!"})
            
        if plan.get("status") in ["PATCHED", "UPDATING"]:
            msg = plan.get("status_msg") or "Product is currently unavailable (Patched/Updating)."
            return jsonify({"success": False, "msg": msg})
            
        price = float(plan.get("price", 0))
        user = db.users.find_one({"user_id": user_id})
        
        if float(user.get("balance", 0)) < price:
            return jsonify({"success": False, "msg": f"Insufficient Balance! You need ₹{price}"})
            
        # Deduct balance temporarily
        res = db.users.update_one({"user_id": user_id, "balance": {"$gte": price}}, {"$inc": {"balance": -price}})
        if res.modified_count == 0:
            return jsonify({"success": False, "msg": "Balance deduction failed!"})
        
        # Check Product Type
        if plan.get("type") == "manual":
            # Handle Manual Product Key System
            key_doc = db.keys.find_one_and_update(
                {"product_db_id": plan["id"], "used": False},
                {"$set": {"used": True, "used_by": user_id, "used_date": datetime.now()}}
            )
            if not key_doc:
                # Refund user
                db.users.update_one({"user_id": user_id}, {"$inc": {"balance": price}})
                return jsonify({"success": False, "msg": "Out of Stock! No keys available for this plan."})
                
            key_data = key_doc["key"]
            
            # Save to history
            db.history.insert_one({
                "user_id": user_id,
                "product": plan.get("name", "N/A"),
                "plan": plan.get("plan_name", "N/A"),
                "price": price,
                "license_key": key_data,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            return jsonify({"success": True, "key": key_data})
        else:
            # Handle API Product
            settings = db.settings.find_one({"id": "global"}) or {}
            current_api_key = settings.get("api_key", API_KEY)
            current_master_key = settings.get("master_key", MASTER_KEY)
            current_api_endpoint = settings.get("api_endpoint", API_ENDPOINT)
            
            payload = {'api_key': current_api_key, 'action': 'buy', 'product_id': str(plan.get("product_id", "")), 'duration': str(plan.get("plan_name", "")), 'android_id': android_id}
            headers = {'Content-Type': 'application/x-www-form-urlencoded', 'x-master-key': current_master_key}
            
            import requests
            api_res = requests.post(current_api_endpoint, data=payload, headers=headers, timeout=15)
            data = api_res.json()
            
            if data.get("status") == "success" or data.get("success") == True:
                key_data = data.get("key") or data.get("license") or "N/A"
                db.history.insert_one({
                    "user_id": user_id,
                    "product": plan.get("name", "N/A"),
                    "plan": plan.get("plan_name", "N/A"),
                    "price": price,
                    "license_key": key_data,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                return jsonify({"success": True, "key": key_data})
            else:
                db.users.update_one({"user_id": user_id}, {"$inc": {"balance": price}})
                error_msg = data.get("msg") or data.get("message") or "API Error: Unknown Error"
                return jsonify({"success": False, "msg": error_msg})
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Refund in case of critical failure
        if 'price' in locals():
            db.users.update_one({"user_id": user_id}, {"$inc": {"balance": price}})
        return jsonify({"success": False, "msg": f"Server Error: {str(e)}"})

# ================= ADMIN ROUTES =================

@app.route("/support", methods=["GET", "POST"])
def support():
    if "user_id" not in session: return redirect("/")
    user_id = session["user_id"]
    
    if request.method == "POST":
        message = request.form.get("message")
        if message:
            ticket = db.tickets.find_one({"user_id": user_id})
            new_msg = {"sender": "user", "text": message, "time": datetime.now().strftime("%I:%M %p")}
            if ticket:
                db.tickets.update_one({"user_id": user_id}, {"$push": {"messages": new_msg}, "$set": {"status": "open", "last_updated": datetime.now()}})
            else:
                db.tickets.insert_one({
                    "user_id": user_id,
                    "username": session.get("username", "User"),
                    "status": "open",
                    "messages": [new_msg],
                    "last_updated": datetime.now()
                })
        return redirect("/support")
        
    user = db.users.find_one({"user_id": user_id})
    ticket = db.tickets.find_one({"user_id": user_id})
    messages = ticket.get("messages", []) if ticket else []
    return render_template("support.html", user=user, balance=user.get("balance", 0.0), messages=messages)

@app.route("/admin/support")
def admin_support_list():
    if not session.get("admin"): return redirect("/admin")
    tickets = list(db.tickets.find().sort("last_updated", -1))
    return render_template("admin/support_list.html", tickets=tickets)

@app.route("/admin/support/<user_id>", methods=["GET", "POST"])
def admin_support_chat(user_id):
    if not session.get("admin"): return redirect("/admin")
    
    if request.method == "POST":
        message = request.form.get("message")
        if message:
            new_msg = {"sender": "admin", "text": message, "time": datetime.now().strftime("%I:%M %p")}
            db.tickets.update_one({"user_id": user_id}, {"$push": {"messages": new_msg}, "$set": {"status": "replied", "last_updated": datetime.now()}})
        return redirect(f"/admin/support/{user_id}")
        
    ticket = db.tickets.find_one({"user_id": user_id})
    if not ticket: return redirect("/admin/support")
    return render_template("admin/support_chat.html", ticket=ticket)


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if session.get("admin"):
        return redirect("/admin/panel")
    return redirect("/")


@app.route("/admin/panel")
def admin_panel():
    if not session.get("admin"): return redirect("/admin")
    total_users = db.users.count_documents({})
    users = list(db.users.find({}))
    total_balance = sum(u.get("balance", 0) for u in users)
    orders = db.history.count_documents({})
    
    # 7 Days Sales Graph Data
    from datetime import datetime, timedelta
    sales_labels = []
    sales_data = []
    for i in range(6, -1, -1):
        dt = datetime.now() - timedelta(days=i)
        date_str = dt.strftime('%Y-%m-%d')
        daily_sales = list(db.history.find({"date": {"$regex": f"^{date_str}"}}))
        daily_total = sum(float(s.get("price", 0)) for s in daily_sales)
        sales_labels.append(dt.strftime('%a'))
        sales_data.append(daily_total)
        
    return render_template("admin/panel.html", total_users=total_users, total_balance=total_balance, orders=orders, sales_labels=sales_labels, sales_data=sales_data)


@app.route("/admin/add_balance", methods=["POST"])
def admin_add_balance():
    if not session.get("admin"): return redirect("/")
    uid = request.form.get("user_id")
    amt = float(request.form.get("amount", 0))
    db.users.update_one({"user_id": uid}, {"$inc": {"balance": amt}})
    from datetime import datetime
    db.deposit_history.insert_one({
        "user_id": uid,
        "amount": amt,
        "utr": "ADMIN_ADD",
        "sender": "Admin",
        "status": "completed",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    return redirect("/admin/users")


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
        feedback_link = request.form.get("feedback_link", "")
        updates_link = request.form.get("updates_link", "")
        features = request.form.get("features", "")
        status = request.form.get("status", "SAFE")
        status_msg = request.form.get("status_msg", "")
        
        name = request.form.get("name", product.get("name"))
        category = request.form.get("category", product.get("category"))
        plan_name = request.form.get("plan_name", product.get("plan_name"))
        try:
            price = float(request.form.get("price", product.get("price")))
        except (TypeError, ValueError):
            price = 0.0
        try:
            api_id = int(request.form.get("product_id", product.get("product_id")))
        except (TypeError, ValueError):
            api_id = 0
        
        db.products.update_one({"id": pid}, {"$set": {
            "media_url": media_url,
            "feedback_link": feedback_link,
            "updates_link": updates_link, 
            "features": features, 
            "status": status, 
            "status_msg": status_msg,
            "name": name,
            "category": category,
            "plan_name": plan_name,
            "price": price,
            "product_id": api_id
        }})
        return redirect("/admin/products")
        
    return render_template("admin/edit_product.html", product=product)

@app.route("/admin/product/delete/<pid>")
def admin_delete_product(pid):
    if not session.get("admin"): return redirect("/admin")
    from bson.objectid import ObjectId
    # Try deleting by _id first, if it's a valid ObjectId
    try:
        res = db.products.delete_one({"_id": ObjectId(pid)})
        if res.deleted_count > 0: return redirect("/admin/products")
    except:
        pass
        
    # Fallback to custom 'id' field (both int and string)
    try:
        res = db.products.delete_one({"id": int(pid)})
        if res.deleted_count > 0: return redirect("/admin/products")
    except:
        pass
        
    db.products.delete_one({"id": str(pid)})
    return redirect("/admin/products")

@app.route("/admin/product/add", methods=["GET", "POST"])
def admin_add_product():
    if not session.get("admin"): return redirect("/admin")
    if request.method == "POST":
        p_type = request.form.get("type", "api")
        name = request.form.get("name")
        category = request.form.get("category")
        plan_name = request.form.get("plan_name")
        try:
            price = float(request.form.get("price"))
        except (TypeError, ValueError):
            price = 0.0
        try:
            product_id = int(request.form.get("product_id", 0))
        except (TypeError, ValueError):
            product_id = 0
        media_url = request.form.get("media_url", "")
        feedback_link = request.form.get("feedback_link", "")
        updates_link = request.form.get("updates_link", "")
        features = request.form.get("features", "")
        status = request.form.get("status", "SAFE")
        status_msg = request.form.get("status_msg", "")
        add_another = request.form.get("add_another") == "on"
        
        new_id = 1
        last_product = db.products.find_one({}, sort=[("id", -1)])
        if last_product: new_id = last_product["id"] + 1
        
        db.products.insert_one({
            "id": new_id,
            "type": p_type,
            "name": name,
            "category": category,
            "plan_name": plan_name,
            "price": price,
            "product_id": product_id,
            "media_url": media_url,
            "feedback_link": feedback_link,
            "updates_link": updates_link,
            "features": features,
            "status": status,
            "status_msg": status_msg,
            "order": new_id
        })
        
        if add_another:
            import urllib.parse
            query = urllib.parse.urlencode({
                "type": p_type,
                "name": name,
                "category": category,
                "media_url": media_url,
            "feedback_link": feedback_link,
            "updates_link": updates_link,
            "features": features,
            "status": status,
                "status_msg": status_msg,
                "product_id": product_id
            })
            return redirect(f"/admin/product/add?{query}")
            
        return redirect("/admin/products")
        
    return render_template("admin/add_product.html")



@app.route("/admin/user_profile", methods=["GET", "POST"])
def admin_user_profile():
    if not session.get("admin"): return redirect("/admin")
    settings = db.settings.find_one({"id": "global"}) or {}
    
    if request.method == "POST":
        data = request.json
        if data:
            if "default_avatar" in data:
                db.settings.update_one({"id": "global"}, {"$set": {"default_avatar": data["default_avatar"]}}, upsert=True)
            if "default_banner" in data:
                db.settings.update_one({"id": "global"}, {"$set": {"default_banner": data["default_banner"]}}, upsert=True)
            if "app_logo" in data:
                db.settings.update_one({"id": "global"}, {"$set": {"app_logo": data["app_logo"]}}, upsert=True)
            return jsonify({"success": True})
        return jsonify({"success": False})
        
    return render_template("admin/user_profile.html", settings=settings)

@app.route("/admin/settings", methods=["GET", "POST"])
def admin_settings():
    if not session.get("admin"): return redirect("/admin")
    settings = db.settings.find_one({"id": "global"}) or {"maintenance_mode": False, "hidden_categories": ""}
    
    if request.method == "POST":
        db.settings.update_one({"id": "global"}, {"$set": {
            "maintenance_mode": request.form.get("maintenance_mode") == "on", 
            "hidden_categories": request.form.get("hidden_categories", ""),
            "popup_message": request.form.get("popup_message", ""),
            "app_name": request.form.get("app_name", "Karan Store"),
                        "app_logo": request.form.get("app_logo", ""),
            "default_avatar": request.form.get("default_avatar", ""),
            "default_banner": request.form.get("default_banner", ""),
            "telegram": request.form.get("telegram", "Karan_store"),
            "instagram": request.form.get("instagram", "Karan_store"),
            "video_deposit": request.form.get("video_deposit", ""),
            "video_use": request.form.get("video_use", ""),
            "feedback_link": request.form.get("feedback_link", ""),
            "updates_link": request.form.get("updates_link", ""),
            "whatsapp_support": request.form.get("whatsapp_support", ""),
            "telegram_support": request.form.get("telegram_support", "")
        }}, upsert=True)
        return redirect("/admin/settings")
        
    return render_template("admin/settings.html", settings=settings)

@app.route("/admin/api_settings", methods=["GET", "POST"])

@app.route("/admin/api_analytics")
def admin_api_analytics():
    if not session.get("admin"): return redirect("/admin")
    
    # Get all API orders (they have ' (API)' in the product name)
    api_orders = list(db.history.find({"product": {"$regex": " \(API\)$"}}))
    
    total_api_revenue = sum(float(o.get("price", 0)) for o in api_orders)
    total_api_keys = len(api_orders)
    
    # Group by reseller
    reseller_stats = {}
    for o in api_orders:
        uid = o.get("user_id")
        if uid not in reseller_stats:
            user_doc = db.users.find_one({"user_id": uid})
            username = user_doc.get("username", "Unknown") if user_doc else "Unknown"
            reseller_stats[uid] = {"username": username, "spent": 0, "keys": 0}
            
        reseller_stats[uid]["spent"] += float(o.get("price", 0))
        reseller_stats[uid]["keys"] += 1
        
    sorted_resellers = sorted(reseller_stats.items(), key=lambda x: x[1]["spent"], reverse=True)
    
    # Get today's API revenue
    from datetime import datetime
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_orders = [o for o in api_orders if str(o.get("date", "")).startswith(today_str)]
    today_api_revenue = sum(float(o.get("price", 0)) for o in today_orders)
    
    return render_template("admin/api_analytics.html", 
        total_api_revenue=total_api_revenue,
        total_api_keys=total_api_keys,
        today_api_revenue=today_api_revenue,
        resellers=sorted_resellers,
        recent_orders=sorted(api_orders, key=lambda x: x.get("date", ""), reverse=True)[:50]
    )


def admin_api_settings():
    if not session.get("admin"): return redirect("/admin")
    settings = db.settings.find_one({"id": "global"}) or {}
    
    if request.method == "POST":
        db.settings.update_one({"id": "global"}, {"$set": {
            "api_endpoint": request.form.get("api_endpoint", "https://adminpanels.shop/api/reseller_v1.php"),
            "api_key": request.form.get("api_key", "4936a17fb44211207c7ca20bdc6a4a57"),
            "master_key": request.form.get("master_key", "a7f3e8b2c9d1f4a6b8c2d5e9f1a3b6c8"),
            "karanpay_key_1": request.form.get("karanpay_key_1", "guru131e012b5141689b9135317fb6fa7f"),
            "karanpay_key_2": request.form.get("karanpay_key_2", "guru1eff587f747b3df8c7a355570f90ce")
        }}, upsert=True)
        return redirect("/admin/api_settings")
        
    return render_template("admin/api_settings.html", settings=settings)

@app.route("/admin/keys", methods=["GET", "POST"])
def admin_keys():
    if not session.get("admin"): return redirect("/admin")
    
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            product_id = request.form.get("product_id")
            keys_text = request.form.get("keys", "")
            keys_list = [k.strip() for k in keys_text.split('\n') if k.strip()]
            for k in keys_list:
                db.keys.insert_one({
                    "product_db_id": int(product_id),
                    "key": k,
                    "used": False,
                    "used_by": None,
                    "used_date": None,
                    "added_date": datetime.now()
                })
        elif action == "delete":
            key_id = request.form.get("key_id")
            from bson.objectid import ObjectId
            db.keys.delete_one({"_id": ObjectId(key_id)})
            
        return redirect("/admin/keys")
        
    manual_products = list(db.products.find({"type": "manual"}))
    keys = list(db.keys.find().sort("added_date", -1))
    
    # Enrich keys with product info
    for k in keys:
        p = db.products.find_one({"id": k["product_db_id"]})
        k["product_name"] = p["name"] + " - " + p["plan_name"] if p else "Unknown Product"
        
    return render_template("admin/keys.html", products=manual_products, keys=keys)

@app.route("/admin/reorder", methods=["GET", "POST"])
def admin_reorder():
    if not session.get("admin"): return redirect("/admin")
    if request.method == "POST":
        order_data = request.json.get("order", [])
        for item in order_data:
            db.products.update_one({"id": item["id"]}, {"$set": {"order": item["order"]}})
        return jsonify({"success": True})
        
    raw_products = list(db.products.find({}).sort("order", 1))
    
    # Group them by name for the UI
    groups = {}
    for p in raw_products:
        key = p["name"]
        if key not in groups:
            groups[key] = {
                "name": p["name"],
                "category": p["category"],
                "count": 0,
                "ids": []
            }
        groups[key]["count"] += 1
        groups[key]["ids"].append(str(p["id"]))
        
    for k in groups:
        groups[k]["ids"] = ",".join(groups[k]["ids"])
        
    grouped_products = list(groups.values())
    
    return render_template("admin/reorder.html", grouped_products=grouped_products)

@app.route("/admin/product/delete_all")
def admin_delete_all_products():
    if not session.get("admin"): return redirect("/admin")
    db.products.delete_many({})
    return redirect("/admin/products")

@app.route("/admin/users")
def admin_users():
    if not session.get("admin"): return redirect("/admin")
    sort_by = request.args.get("sort", "_id")
    if sort_by == "balance":
        users = list(db.users.find({}).sort("balance", -1))
    else:
        users = list(db.users.find({}).sort("_id", -1))
    return render_template("admin/users.html", users=users)

@app.route("/admin/orders")
def admin_orders_list():
    if not session.get("admin"): return redirect("/admin")
    orders = list(db.history.find({}).sort("date", -1))
    return render_template("admin/orders.html", orders=orders)

@app.route("/admin/sales")
def admin_sales():
    if not session.get("admin"): return redirect("/admin")
    
    # Fetch all sales
    all_sales = list(db.history.find().sort("date", -1))
    
    # Calculate stats
    total_revenue = sum(float(s.get("price", 0)) for s in all_sales)
    total_sales = len(all_sales)
    
    # Today's sales
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_sales = [s for s in all_sales if s.get("date", "").startswith(today_str)]
    today_revenue = sum(float(s.get("price", 0)) for s in today_sales)
    
    return render_template("admin/sales.html", sales=all_sales, total_revenue=total_revenue, total_sales=total_sales, today_revenue=today_revenue, today_sales=len(today_sales))

@app.route("/admin/transactions")
def admin_transactions():
    if not session.get("admin"): return redirect("/admin")
    deposits = list(db.orders.find({}).sort("timestamp", -1))
    return render_template("admin/transactions.html", deposits=deposits)

@app.route("/admin/transaction/<action>/<order_id>")
def admin_transaction_action(action, order_id):
    if not session.get("admin"): return redirect("/admin")
    order = db.orders.find_one({"order_id": order_id})
    if not order or order["status"] != "pending": return redirect("/admin/transactions")
    
    if action == "approve":
        db.orders.update_one({"order_id": order_id}, {"$set": {"status": "completed", "utr": "MANUAL", "sender": "Admin Approved"}})
        db.users.update_one({"user_id": order["user_id"]}, {"$inc": {"balance": order["amount"]}})
        from datetime import datetime
        db.deposit_history.insert_one({"user_id": order["user_id"], "order_id": order_id, "amount": order["amount"], "utr": "MANUAL", "sender": "Admin Approved", "status": "completed", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    elif action == "reject":
        db.orders.update_one({"order_id": order_id}, {"$set": {"status": "failed", "utr": "REJECTED", "sender": "Admin Rejected"}})
    return redirect("/admin/transactions")

@app.route("/admin/notifications", methods=["GET", "POST"])
def admin_notifications():
    if not session.get("admin"): return redirect("/admin")
    
    if request.method == "POST":
        title = request.form.get("title")
        message = request.form.get("message")
        import datetime
        db.notifications.insert_one({
            "title": title,
            "message": message,
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return redirect("/admin/notifications")
        
    notifications = list(db.notifications.find().sort("date", -1))
    return render_template("admin/notifications.html", notifications=notifications)

@app.route("/notifications")
def user_notifications():
    if "user_id" not in session: return redirect("/")
    user_id = session["user_id"]
    from datetime import datetime
    db.users.update_one({"user_id": user_id}, {"$set": {"last_seen_notification": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}})
    user = db.users.find_one({"user_id": user_id})
    notifications = list(db.notifications.find().sort("date", -1))
    return render_template("notifications.html", user=user, balance=user.get("balance", 0.0), notifications=notifications)


@app.route("/api/change_password", methods=["POST"])
def api_change_password():
    if "user_id" not in session: return jsonify({"success": False, "error": "Not logged in"})
    data = request.json
    new_pw = data.get("password")
    if not new_pw or len(new_pw) < 8:
        return jsonify({"success": False, "error": "Invalid password"})
    
    db.users.update_one({"user_id": session["user_id"]}, {"$set": {"password": new_pw}})
    return jsonify({"success": True})

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route('/telegram_login')
def telegram_login():
    data = request.args.to_dict()
    if 'hash' not in data:
        return redirect('/?error=Invalid+Login')

    received_hash = data.pop('hash')
    
    # We need the bot token to verify.
    bot_token = '8833898625:AAEW18HVT9CIzvTW0lP7U6nub8FuXjX2bUI' # Provided in the system context earlier, fallback
    settings = db.settings.find_one({"id": "global"}) or {}
    
    # Verifying Telegram Login
    data_check_string = '\n'.join([f"{k}={v}" for k, v in sorted(data.items())])
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    hash_code = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if hash_code != received_hash:
        return redirect('/?error=Authentication+Failed')

    user_id = data.get('id')
    first_name = data.get('first_name', '')
    
    # Check if user exists
    user = db.users.find_one({'user_id': str(user_id)})
    if not user:
        # Create new user via Web Login
        db.users.insert_one({
            'user_id': str(user_id),
            'first_name': first_name,
            'balance': 0.0,
            'registered_via': 'web'
        })
    
    session['user_id'] = str(user_id)
    session['first_name'] = first_name
    
    # Send success message to Telegram using Bot API
    msg = f"✅ *Login Successful!*\n\nWelcome back to Karan Store Website, {first_name}!\nYou have securely logged in via Telegram."
    try:
        requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", data={
            'chat_id': user_id,
            'text': msg,
            'parse_mode': 'Markdown'
        })
    except:
        pass

    return redirect('/dashboard')

@app.route("/tutorial")
def tutorial():
    if "user_id" not in session: return redirect("/")
    user = db.users.find_one({"user_id": session["user_id"]})
    return render_template("tutorial.html", user=user, balance=user.get("balance", 0.0))

@app.route("/upload_avatar", methods=["POST"])
def upload_avatar():
    if "user_id" not in session: return jsonify({"success": False, "error": "Not logged in"})
    data = request.json
    avatar_b64 = data.get("avatar")
    if not avatar_b64: return jsonify({"success": False})
    db.users.update_one({"user_id": session["user_id"]}, {"$set": {"avatar": avatar_b64}})
    return jsonify({"success": True})

@app.route("/upload_banner", methods=["POST"])
def upload_banner():
    if "user_id" not in session: return jsonify({"success": False})
    data = request.json
    banner_b64 = data.get("banner")
    if banner_b64:
        db.users.update_one({"user_id": session["user_id"]}, {"$set": {"banner": banner_b64}})
        return jsonify({"success": True})
    return jsonify({"success": False})
    
    db.users.update_one({"user_id": session["user_id"]}, {"$set": {"avatar": avatar_b64}})
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)










































import secrets

@app.route("/api/generate_key", methods=["POST"])
def generate_api_key():
    if "user_id" not in session: return jsonify({"success": False})
    new_key = secrets.token_hex(16)
    db.users.update_one({"user_id": session["user_id"]}, {"$set": {"api_key": new_key}})
    return jsonify({"success": True, "api_key": new_key})

@app.route("/developer_api")
def developer_api():
    if "user_id" not in session: return redirect("/")
    user = db.users.find_one({"user_id": session["user_id"]})
    settings = db.settings.find_one({"id": "global"}) or {}
    
    # Ensure user has api_key
    if "api_key" not in user:
        new_key = secrets.token_hex(16)
        db.users.update_one({"user_id": session["user_id"]}, {"$set": {"api_key": new_key}})
        user["api_key"] = new_key
        
    master_key = settings.get("reseller_master_key", "c054bf5dc7a486e4c05147a11e4c7039")
    raw_products = list(db.products.find({}).sort("order", 1))
    
    # Group products by name and category for the API documentation table
    grouped = {}
    for p in raw_products:
        name = p.get("name", "Unknown")
        cat = p.get("category", "Uncategorized")
        key = f"{cat}___{name}"
        if key not in grouped: grouped[key] = {"name": name, "category": cat, "plans": [], "pid": p.get("id")}
        grouped[key]["plans"].append(p)
    
    return render_template("api.html", user=user, master_key=master_key, grouped_products=grouped, url_root=request.url_root)

@app.route("/api/reseller_v1.php", methods=["POST", "GET"])
@app.route("/api/reseller_v1", methods=["POST", "GET"])
def reseller_api():
    if request.method == "GET":
        return jsonify({"status": "error", "message": "Method Not Allowed. Use POST."})
        
    settings = db.settings.find_one({"id": "global"}) or {}
    expected_master_key = settings.get("reseller_master_key", "c054bf5dc7a486e4c05147a11e4c7039")
    provided_master_key = request.headers.get("x-master-key") or request.headers.get("X-Master-Key")
    
    if provided_master_key != expected_master_key:
        return jsonify({"status": "error", "message": "Invalid Master Key!"})
        
    api_key = request.form.get("api_key")
    if not api_key:
        return jsonify({"status": "error", "message": "Missing api_key parameter!"})
        
    user = db.users.find_one({"api_key": api_key})
    if not user:
        return jsonify({"status": "error", "message": "Invalid API Key!"})
        
    action = request.form.get("action")
    if action == "services":
        # Return list of services
        raw_products = list(db.products.find({}).sort("order", 1))
        services = []
        for p in raw_products:
            services.append({
                "service_id": p.get("id"),
                "name": p.get("name"),
                "category": p.get("category"),
                "plan_name": p.get("plan_name"),
                "price": p.get("price"),
                "status": p.get("status")
            })
        return jsonify({"status": "success", "services": services})
        
    elif action == "buy":
        product_pid = request.form.get("product_id")
        duration = request.form.get("duration")
        android_id = request.form.get("android_id", "")
        
        if not product_pid or not duration:
            return jsonify({"status": "error", "message": "Missing product_id or duration!"})
            
        # Find exact product in DB
        base_plan = db.products.find_one({"id": int(product_pid) if str(product_pid).isdigit() else product_pid})
        if not base_plan:
            base_plan = db.products.find_one({"id": str(product_pid)})
            
        if not base_plan:
            return jsonify({"status": "error", "message": "Service not found. Check PID."})
            
        target_name = base_plan.get("name")
        plan = db.products.find_one({"name": target_name, "plan_name": duration})
        
        if not plan:
            return jsonify({"status": "error", "message": "Service not found for this Duration."})
          
        if plan.get("status") in ["PATCHED", "UPDATING"]:
            return jsonify({"status": "error", "message": "Product is currently unavailable."})
            
        price = float(plan.get("price", 0))
        if float(user.get("balance", 0)) < price:
            return jsonify({"status": "error", "message": "Insufficient Balance!"})
            
        # Deduct Balance
        res = db.users.update_one({"_id": user["_id"], "balance": {"$gte": price}}, {"$inc": {"balance": -price}})
        if res.modified_count == 0:
            return jsonify({"status": "error", "message": "Balance deduction failed!"})
            
        # Fetch Key
        key_data = ""
        if plan.get("type") == "manual":
            key_doc = db.keys.find_one_and_update(
                {"product_db_id": plan["id"], "used": False},
                {"$set": {"used": True, "used_by": user["user_id"], "used_date": datetime.now()}}
            )
            if not key_doc:
                db.users.update_one({"_id": user["_id"]}, {"$inc": {"balance": price}}) # refund
                return jsonify({"status": "error", "message": "Out of Stock!"})
            key_data = key_doc["key"]
        else:
            # External API purchase
            current_api_key = settings.get("api_key", API_KEY)
            current_master_key = settings.get("master_key", MASTER_KEY)
            current_api_endpoint = settings.get("api_endpoint", API_ENDPOINT)
            
            payload = {'api_key': current_api_key, 'action': 'buy', 'product_id': str(plan.get("product_id", "")), 'duration': str(plan.get("plan_name", "")), 'android_id': android_id}
            headers = {'Content-Type': 'application/x-www-form-urlencoded', 'x-master-key': current_master_key}
            
            try:
                import requests
                api_res = requests.post(current_api_endpoint, data=payload, headers=headers, timeout=15)
                data = api_res.json()
                if data.get("status") == "success" or data.get("success") == True:
                    key_data = data.get("key") or data.get("license") or "N/A"
                else:
                    db.users.update_one({"_id": user["_id"]}, {"$inc": {"balance": price}}) # refund
                    error_msg = data.get("msg") or data.get("message") or "Provider API Error"
                    return jsonify({"status": "error", "message": error_msg})
            except Exception as e:
                db.users.update_one({"_id": user["_id"]}, {"$inc": {"balance": price}}) # refund
                return jsonify({"status": "error", "message": "Provider API connection failed!"})
                
        # Insert History
        db.history.insert_one({
            "user_id": user["user_id"],
            "product": plan.get("name", "N/A") + " (API)",
            "plan": plan.get("plan_name", "N/A"),
            "price": price,
            "license_key": key_data,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return jsonify({
            "status": "success",
            "key": key_data,
            "balance": float(user.get("balance", 0)) - price,
            "message": "Purchased successfully via API"
        })
    else:
        return jsonify({"status": "error", "message": "Invalid action!"})
