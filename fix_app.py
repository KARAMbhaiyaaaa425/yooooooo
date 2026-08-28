import re

with open('app.py', 'r', encoding='utf-8') as f:
    text = f.read()

correct_block = '''@app.route("/transfer", methods=["GET", "POST"])
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
            return jsonify({"success": False, "msg": "Not logged in"})'''

text = re.sub(r'@app\.route\("/transfer", methods=\["GET", "POST"\]\)\s*def transfer\(\):\s*return jsonify\({"success": False, "msg": "Not logged in"}\)', correct_block, text)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(text)
