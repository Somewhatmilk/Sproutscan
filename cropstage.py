from flask import Flask, request, jsonify, render_template
import sqlite3

app = Flask(__name__)
DB_NAME = "sproutscan.db"


def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crop_name TEXT NOT NULL,
                category TEXT NOT NULL,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cropstage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crop_id INTEGER NOT NULL,
                stage_name TEXT NOT NULL,
                expected_days INTEGER,
                ai_confidence INTEGER,
                status TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (crop_id) REFERENCES crops(id)
            )
        """)

        conn.commit()



@app.get("/cropstage")
def cropstage():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT
                c.id,
                c.crop_name,
                COALESCE(cs.stage_name, '') AS stage_name,
                COALESCE(cs.expected_days, '') AS expected_days,
                COALESCE(cs.ai_confidence, '') AS ai_confidence,
                COALESCE(cs.status, '') AS status
            FROM crops c
            LEFT JOIN cropstage cs
              ON cs.id = (
                SELECT id
                FROM cropstage
                WHERE crop_id = c.id
                ORDER BY created_at DESC, id DESC
                LIMIT 1
              )
            ORDER BY c.id DESC
        """).fetchall()

    return render_template("cropstage.html", crops=rows)



@app.get("/add-crop")
def add_crop_page():
    return render_template("cropstage_add.html")

@app.post("/api/crops")
def create_crop():
    data = request.get_json(silent=True) or {}
    crop_name = (data.get("crop_name") or "").strip()
    category = (data.get("category") or "").strip()
    notes = (data.get("notes") or "").strip()

    if not crop_name or not category:
        return jsonify({"error": "Crop name and category are required"}), 400

    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT INTO crops (crop_name, category, notes) VALUES (?, ?, ?)",
            (crop_name, category, notes)
        )
        conn.commit()

    return jsonify({"message": "Crop created"}), 201

@app.get("/api/crops")
def list_crops():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM crops ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])


#add the ai confidence thingy here, also if possible have it so confidence >= 90% growth status = normal, confidence<90% = needs to be checked 
@app.get("/crop_view")
def view_list():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT
                c.id AS crop_id,
                c.crop_name,
                c.category,
                c.notes,
                COALESCE(cs.stage_name, '') AS stage_name,
                COALESCE(cs.expected_days, '') AS expected_days,
                COALESCE(cs.ai_confidence, '') AS ai_confidence,
                COALESCE(cs.status, '') AS status
            FROM crops c
            LEFT JOIN cropstage cs
              ON cs.id = (
                SELECT id
                FROM cropstage
                WHERE crop_id = c.id
                ORDER BY created_at DESC, id DESC
                LIMIT 1
              )
            ORDER BY c.crop_name ASC""").fetchall()
    return render_template("viewcrops.html", crops=rows)

@app.route("/api/crops/<int:crop_id>", methods=["DELETE"])
def delete_crop(crop_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM cropstage WHERE crop_id = ?", (crop_id,))
        conn.execute("DELETE FROM crops WHERE id = ?", (crop_id,))
        conn.commit()
    return jsonify({"message": "Crop deleted"}), 200


@app.route("/", methods=["GET"])
def login_page():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        # Fetch users to populate the profile selection cards
        try:
            users = conn.execute("SELECT * FROM users").fetchall()
        except sqlite3.OperationalError:
            users = []  
            
    return render_template("login.html", users=users)

if __name__ == "__main__":
    init_db()
    print(app.url_map)
    app.run(debug=True)
