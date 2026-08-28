import re

with open('app.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix admin_add_product price casting
text = re.sub(
    r'price = float\((request\.form\.get\("price"\))\)',
    r'try:\n            price = float(\1)\n        except (TypeError, ValueError):\n            price = 0.0',
    text
)

# Fix admin_edit_product price casting
text = re.sub(
    r'price = float\((request\.form\.get\("price", product\.get\("price"\))\)\)',
    r'try:\n            price = float(\1)\n        except (TypeError, ValueError):\n            price = 0.0',
    text
)

# Fix product_id casting in add
text = re.sub(
    r'product_id = request\.form\.get\("product_id", "0"\)\n\s*if not product_id: product_id = "0"',
    r'try:\n            product_id = int(request.form.get("product_id", 0))\n        except (TypeError, ValueError):\n            product_id = 0',
    text
)
# And its usage in insert_one
text = re.sub(
    r'"product_id": int\(product_id\),',
    r'"product_id": product_id,',
    text
)

# Fix product_id casting in edit
text = re.sub(
    r'api_id = request\.form\.get\("product_id", product\.get\("product_id"\)\)',
    r'try:\n            api_id = int(request.form.get("product_id", product.get("product_id")))\n        except (TypeError, ValueError):\n            api_id = 0',
    text
)

# Fix the broken indentation in add_another
text = text.replace('            "media_url": media_url,\n            "feedback_link": feedback_link,\n            "updates_link": updates_link,\n            "features": features,\n                "status": status,', '            "media_url": media_url,\n            "feedback_link": feedback_link,\n            "updates_link": updates_link,\n            "features": features,\n            "status": status,')


with open('app.py', 'w', encoding='utf-8') as f:
    f.write(text)
