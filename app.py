import csv
from datetime import datetime
import html
import json
import os
from pathlib import Path
import sqlite3
from zipfile import ZIP_DEFLATED, ZipFile

from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for


BASE_DIR = Path(__file__).resolve().parent
QUESTION_FILE = BASE_DIR / "questions.json"
DB_FILE = BASE_DIR / "submissions.db"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123456")
NORMAL_POINT = 0.25
TF_SCORE = {4: 1.0, 3: 0.5, 2: 0.25, 1: 0.1, 0: 0.0}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "doi-secret-key-khi-dua-len-hosting")


def load_questions():
    with QUESTION_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def public_questions():
    items = []
    for question in load_questions():
        item = {
            "label": question.get("label", ""),
            "type": question["type"],
            "question": question["question"],
        }
        if question["type"] == "multiple_choice":
            item["choices"] = question["choices"]
        if question["type"] == "true_false_group":
            item["statements"] = question["statements"]
        if question.get("images"):
            item["images"] = ["/static/" + image.replace("assets/", "assets/") for image in question["images"]]
        items.append(item)
    return items


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submitted_at TEXT NOT NULL,
                student_name TEXT NOT NULL,
                score REAL NOT NULL,
                max_score REAL NOT NULL,
                answered INTEGER NOT NULL,
                normal_correct INTEGER NOT NULL,
                true_false_points REAL NOT NULL,
                answers_json TEXT NOT NULL,
                review_json TEXT NOT NULL,
                ip_address TEXT
            )
            """
        )


def normalize_true_false(value):
    text = str(value or "").strip().upper()
    if text in {"Đ", "D", "TRUE", "T", "DUNG", "ĐÚNG"}:
        return "Đ"
    if text in {"S", "FALSE", "F", "SAI"}:
        return "S"
    return text


def normalize_answer(value, question_type):
    if question_type == "true_false_group":
        return normalize_true_false(value)
    if question_type == "multiple_choice":
        return str(value or "").strip().upper()
    return " ".join(str(value or "").strip().lower().split())


def format_answer(answer):
    if isinstance(answer, list):
        return ", ".join(f"{chr(ord('a') + index)}:{item or '-'}" for index, item in enumerate(answer))
    return answer or "-"


def count_true_false_group_correct(selected, correct):
    selected = selected or [None, None, None, None]
    count = 0
    for selected_item, correct_item in zip(selected, correct):
        if selected_item and normalize_true_false(selected_item) == normalize_true_false(correct_item):
            count += 1
    return count


def grade(answers):
    questions = load_questions()
    normal_correct = 0
    true_false_points = 0.0
    review = []

    for index, question in enumerate(questions):
        selected = answers[index] if index < len(answers) else None
        label = question.get("label", f"Cau {index + 1}")
        if question["type"] == "true_false_group":
            correct_count = count_true_false_group_correct(selected, question["answer"])
            item_score = TF_SCORE.get(correct_count, 0.0)
            true_false_points += item_score
            review.append({
                "label": label,
                "type": question["type"],
                "selected": format_answer(selected),
                "correct": format_answer(question["answer"]),
                "result": f"{correct_count}/4",
                "score": item_score,
            })
        else:
            is_correct = normalize_answer(selected, question["type"]) == normalize_answer(question["answer"], question["type"])
            if is_correct:
                normal_correct += 1
            review.append({
                "label": label,
                "type": question["type"],
                "selected": selected or "-",
                "correct": question["answer"],
                "result": "Dung" if is_correct else "Sai",
                "score": NORMAL_POINT if is_correct else 0.0,
            })

    answered = sum(1 for answer in answers if answer and (not isinstance(answer, list) or any(answer)))
    normal_total = sum(1 for question in questions if question["type"] != "true_false_group")
    true_false_total = sum(1 for question in questions if question["type"] == "true_false_group")
    max_score = normal_total * NORMAL_POINT + true_false_total
    score = normal_correct * NORMAL_POINT + true_false_points
    return {
        "score": round(score, 2),
        "max_score": round(max_score, 2),
        "answered": answered,
        "normal_correct": normal_correct,
        "true_false_points": round(true_false_points, 2),
        "review": review,
    }


def fetch_submissions():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM submissions ORDER BY id DESC").fetchall()


def fetch_submission(submission_id):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()


def require_admin():
    return session.get("admin_ok") is True


@app.route("/")
def student_page():
    return render_template("student.html", questions=public_questions())


@app.post("/submit")
def submit():
    data = request.get_json(force=True)
    student_name = str(data.get("student_name", "")).strip()
    answers = data.get("answers", [])
    if not student_name:
        return jsonify({"error": "Vui long nhap ho ten."}), 400

    result = grade(answers)
    submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            """
            INSERT INTO submissions (
                submitted_at, student_name, score, max_score, answered,
                normal_correct, true_false_points, answers_json, review_json, ip_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                submitted_at,
                student_name,
                result["score"],
                result["max_score"],
                result["answered"],
                result["normal_correct"],
                result["true_false_points"],
                json.dumps(answers, ensure_ascii=False),
                json.dumps(result["review"], ensure_ascii=False),
                request.headers.get("X-Forwarded-For", request.remote_addr),
            ),
        )
        submission_id = cursor.lastrowid

    return jsonify({
        "submission_id": submission_id,
        "score": result["score"],
        "max_score": result["max_score"],
        "message": "Da nop bai thanh cong.",
    })


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = ""
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin_ok"] = True
            return redirect(url_for("admin"))
        error = "Sai mat khau."
    return render_template("login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
def admin():
    if not require_admin():
        return redirect(url_for("admin_login"))
    return render_template("admin.html", submissions=fetch_submissions())


@app.route("/admin/submission/<int:submission_id>")
def admin_submission(submission_id):
    if not require_admin():
        return redirect(url_for("admin_login"))
    submission = fetch_submission(submission_id)
    if submission is None:
        return "Khong tim thay bai nop.", 404
    review = json.loads(submission["review_json"])
    return render_template("submission_detail.html", submission=submission, review=review)


def cell_ref(row_index, col_index):
    letters = ""
    col = col_index
    while col:
        col, remainder = divmod(col - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"{letters}{row_index}"


def sheet_xml(rows):
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            ref = cell_ref(row_index, col_index)
            text = html.escape("" if value is None else str(value))
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>')
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>' + "".join(xml_rows) + '</sheetData></worksheet>'
    )


def make_xlsx(summary_rows, detail_rows):
    import io
    output = io.BytesIO()
    sheets = [("Tong hop", summary_rows), ("Chi tiet", detail_rows)]
    with ZipFile(output, "w", ZIP_DEFLATED) as xlsx:
        xlsx.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        content_types = ['<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>']
        workbook_sheets = []
        workbook_rels = []
        for index, (name, rows) in enumerate(sheets, start=1):
            workbook_sheets.append(f'<sheet name="{html.escape(name)}" sheetId="{index}" r:id="rId{index}"/>')
            workbook_rels.append(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>')
            content_types.append(f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
            xlsx.writestr(f"xl/worksheets/sheet{index}.xml", sheet_xml(rows))
        xlsx.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + "".join(workbook_sheets) + "</sheets></workbook>")
        xlsx.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(workbook_rels) + "</Relationships>")
        xlsx.writestr("[Content_Types].xml", "".join(content_types) + "</Types>")
    output.seek(0)
    return output.read()


@app.route("/admin/export.xlsx")
def export_xlsx():
    if not require_admin():
        return redirect(url_for("admin_login"))
    summary = [["Thoi gian", "Ho ten", "Diem", "Diem toi da", "So cau da tra loi"]]
    detail = [["Thoi gian", "Ho ten", "Cau", "Loai", "Tra loi", "Dap an", "Ket qua", "Diem cau"]]
    for row in reversed(fetch_submissions()):
        summary.append([row["submitted_at"], row["student_name"], row["score"], row["max_score"], row["answered"]])
        for item in json.loads(row["review_json"]):
            detail.append([row["submitted_at"], row["student_name"], item["label"], item["type"], item["selected"], item["correct"], item["result"], item["score"]])
    data = make_xlsx(summary, detail)
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=teacher_results.xlsx"},
    )


init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
