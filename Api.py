from flask import Flask, request, jsonify, render_template_string

import sqlite3

import os



app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.path.join(BASE_DIR, "paytm.db")



if not os.path.exists(DB_FILE):

    print("❌ paytm.db not found! Run: py build_db.py")

    exit()





def query_db(sql, params=()):

    con = sqlite3.connect(DB_FILE)

    con.row_factory = sqlite3.Row

    cur = con.cursor()

    cur.execute(sql, params)

    rows = [dict(r) for r in cur.fetchall()]

    con.close()

    return rows





def clean_number(num):

    """+91, spaces, dashes, .0 sab hata do"""

    if not num:

        return ""

    return (str(num)

            .replace("+91", "")

            .replace(" ", "")

            .replace("-", "")

            .replace(".0", "")

            .strip())





# Get total count for homepage

con = sqlite3.connect(DB_FILE)

cur = con.cursor()

cur.execute("SELECT COUNT(*) FROM users")

TOTAL = cur.fetchone()[0]

con.close()

print(f"✅ DB loaded | Total records: {TOTAL:,}")





# ============================================================

# HOMEPAGE — simple UI

# ============================================================

@app.route("/")

def home():

    return render_template_string("""

    <!DOCTYPE html>

    <html>

    <head>

        <title>Paytm Users API</title>

        <style>

            body { font-family: Arial; max-width: 800px; margin: 40px auto; padding: 20px;

                   background: #f0f4f8; }

            h1 { color: #1e3a8a; }

            .card { background: white; padding: 20px; border-radius: 10px; 

                    box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin: 15px 0; }

            input { padding: 12px; font-size: 16px; width: 250px; 

                    border: 2px solid #3b82f6; border-radius: 6px; }

            button { padding: 12px 24px; font-size: 16px; background: #3b82f6; 

                     color: white; border: none; border-radius: 6px; cursor: pointer; }

            button:hover { background: #2563eb; }

            pre { background: #1e293b; color: #e2e8f0; padding: 15px; 

                  border-radius: 6px; overflow-x: auto; }

            a { color: #3b82f6; }

            .badge { background: #10b981; color: white; padding: 4px 10px; 

                     border-radius: 12px; font-size: 14px; }

        </style>

    </head>

    <body>

        <h1>📱 Paytm Users API</h1>

        <p><span class="badge">{{ total }} records loaded</span></p>

        

        <div class="card">

            <h3>🔍 Search by Mobile Number</h3>

            <input id="num" placeholder="e.g. 9730403194" value="">

            <button onclick="search()">Search</button>

            <pre id="result" style="display:none"></pre>

        </div>

        

        <div class="card">

            <h3>📚 API Endpoints</h3>

            <ul>

                <li><a href="/api/paytm?number=9730403194">/api/paytm?number=9730403194</a></li>

                <li><a href="/api/search?q=atul">/api/search?q=atul</a></li>

                <li><a href="/api/search?q=Aurangabad&field=city">/api/search?q=Aurangabad&field=city</a></li>

                <li><a href="/api/stats">/api/stats</a></li>

            </ul>

        </div>

        

        <script>

            async function search() {

                const n = document.getElementById('num').value.trim();

                const res = document.getElementById('result');

                if (!n) return alert('Enter number');

                res.style.display = 'block';

                res.textContent = '⏳ Searching...';

                try {

                    const r = await fetch('/api/paytm?number=' + encodeURIComponent(n));

                    const j = await r.json();

                    res.textContent = JSON.stringify(j, null, 2);

                } catch(e) {

                    res.textContent = 'Error: ' + e;

                }

            }

            document.getElementById('num').addEventListener('keypress', e => {

                if (e.key === 'Enter') search();

            });

        </script>

    </body>

    </html>

    """, total=TOTAL)





# ============================================================

# PRIMARY API — search by mobile number

# ============================================================

@app.route("/api/paytm")

def get_paytm_user():

    raw = request.args.get("number", "")

    number = clean_number(raw)



    if not number:

        return jsonify({

            "status": False,

            "message": "Provide ?number=9730403194"

        }), 400



    rows = query_db(

        "SELECT * FROM users WHERE mobile = ? LIMIT 20",

        (number,)

    )



    if not rows:

        return jsonify({

            "status": False,

            "message": "No record found",

            "number": number

        }), 404



    # Clean None values

    cleaned = []

    for r in rows:

        cleaned.append({k: v for k, v in r.items() if v not in (None, "", "nan")})



    return jsonify({

        "status": True,

        "number": number,

        "total_matches": len(cleaned),

        "data": cleaned if len(cleaned) > 1 else cleaned[0]

    })





# ============================================================

# SEARCH — by name, email, city, pan, etc.

# ============================================================

@app.route("/api/search")

def search():

    q = request.args.get("q", "").strip()

    field = request.args.get("field", "").strip().lower()

    limit = min(int(request.args.get("limit", 50)), 500)



    if not q:

        return jsonify({"status": False, "message": "Provide ?q=value"}), 400



    valid_fields = ["name", "email", "mobile", "city", "gender",

                    "address", "pan", "state", "bank", "income"]



    if field and field in valid_fields:

        rows = query_db(

            f'SELECT * FROM users WHERE "{field}" LIKE ? LIMIT ?',

            (f"%{q}%", limit)

        )

    else:

        # search across all main fields

        cond = " OR ".join([f'"{c}" LIKE ?' for c in valid_fields])

        params = tuple([f"%{q}%"] * len(valid_fields)) + (limit,)

        rows = query_db(f"SELECT * FROM users WHERE {cond} LIMIT ?", params)



    if not rows:

        return jsonify({"status": False, "message": "No results", "query": q}), 404



    cleaned = []

    for r in rows:

        cleaned.append({k: v for k, v in r.items() if v not in (None, "", "nan")})



    return jsonify({

        "status": True,

        "query": q,

        "field": field or "all",

        "count": len(cleaned),

        "data": cleaned

    })





# ============================================================

# STATS

# ============================================================

@app.route("/api/stats")

def stats():

    con = sqlite3.connect(DB_FILE)

    cur = con.cursor()

    cur.execute("SELECT COUNT(*) FROM users")

    total = cur.fetchone()[0]

    cur.execute("""SELECT __source_file__, COUNT(*) FROM users 

                   GROUP BY __source_file__ ORDER BY COUNT(*) DESC""")

    per_file = dict(cur.fetchall())

    con.close()

    return jsonify({

        "status": True,

        "total_records": total,

        "total_files": len(per_file),

        "per_file": per_file

    })





# ============================================================

# BULK LOOKUP — multiple numbers in one call

# ============================================================

@app.route("/api/bulk")

def bulk():

    nums = request.args.get("numbers", "")

    if not nums:

        return jsonify({"status": False, "message": "Provide ?numbers=num1,num2,num3"}), 400



    numbers = [clean_number(n) for n in nums.split(",") if n.strip()]

    if not numbers:

        return jsonify({"status": False, "message": "No valid numbers"}), 400



    placeholders = ",".join(["?"] * len(numbers))

    rows = query_db(

        f"SELECT * FROM users WHERE mobile IN ({placeholders})",

        tuple(numbers)

    )



    grouped = {}

    for r in rows:

        cleaned = {k: v for k, v in r.items() if v not in (None, "", "nan")}

        grouped.setdefault(r["mobile"], []).append(cleaned)



    return jsonify({

        "status": True,

        "requested": len(numbers),

        "found": len(grouped),

        "data": grouped

    })





if __name__ == "__main__":

    print("\n🚀 API running at: http://127.0.0.1:5000")

    print("📱 Test: http://127.0.0.1:5000/api/paytm?number=9730403194\n")

    app.run(host="0.0.0.0", port=5000, debug=False)
