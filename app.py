from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import json, os, re
from typing import List, Optional

app = Flask(__name__)
app.secret_key = "super-secret-change-this"
DATA_FILE = "mahasiswa.json"
USERS_FILE = "users.json"

# ---------- Data model ----------
JURUSAN_LIST = [
    "Teknik Informatika",
    "Manajemen",
    "Hukum",
    "Sastra Inggris",
    "PJOK",
    "PGSD",
    "Ilmu Komunikasi"
]

class ValidationError(Exception):
    pass

class Mahasiswa:
    def __init__(self, nim: str, nama: str, kelas: str, ipk: float, jurusan: str):
        self.nim = str(nim)
        self.nama = nama
        self.kelas = kelas
        self.ipk = float(ipk)
        self.jurusan = jurusan

    def to_dict(self):
        return {
            "nim": self.nim,
            "nama": self.nama,
            "kelas": self.kelas,
            "ipk": self.ipk,
            "jurusan": self.jurusan
        }

# ---------- Validation ----------
def validate_input(nim, nama, kelas, ipk, jurusan):
    if not re.match(r'^\d{12}$', str(nim)):
        raise ValidationError("NIM harus 12 digit angka.")
    if not re.match(r'^[A-Za-z ]+$', nama):
        raise ValidationError("Nama hanya boleh huruf dan spasi.")
    if not re.match(r'^[A-Za-z0-9]+$', kelas):
        raise ValidationError("Kelas hanya boleh huruf dan angka tanpa spasi.")
    try:
        ipk_f = float(ipk)
    except:
        raise ValidationError("IPK harus angka desimal.")
    if not (0.0 <= ipk_f <= 4.0):
        raise ValidationError("IPK harus antara 0.0 – 4.0.")
    if jurusan not in JURUSAN_LIST:
        raise ValidationError("Jurusan tidak valid.")
    return True

# ---------- Load & Save ----------
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

def load_data() -> List[Mahasiswa]:
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            raw = json.load(f)
            return [Mahasiswa(m["nim"], m["nama"], m["kelas"], m["ipk"], m.get("jurusan","")) for m in raw]
        except:
            return []

def save_data(mahasiswa: List[Mahasiswa]):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([m.to_dict() for m in mahasiswa], f, indent=4, ensure_ascii=False)

# Ensure default admin exists
users = load_users()
if "admin" not in users:
    users["admin"] = generate_password_hash("12345")
    save_users(users)

# ---------- Simple user system ----------
def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            flash("Silakan login terlebih dahulu.", "error")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

# ---------- Search ---------- (operate on list[Mahasiswa])
def search_students(arr: List[Mahasiswa], keyword: str):
    k = keyword.lower()
    return [m for m in arr if k in m.nim.lower() or k in m.nama.lower() or k in m.jurusan.lower()]

# Binary search (returns list) - we search by nama/nim/jurusan substring after sorting by nama
def binary_search(arr: List[Mahasiswa], keyword: str):
    keyword = keyword.lower()
    arr_sorted = sorted(arr, key=lambda x: x.nama.lower())
    left, right = 0, len(arr_sorted) - 1
    result = []
    while left <= right:
        mid = (left + right) // 2
        midval = arr_sorted[mid].nama.lower()
        if keyword in midval or keyword in arr_sorted[mid].nim.lower() or keyword in arr_sorted[mid].jurusan.lower():
            # collect neighbors that match too
            i = mid
            while i >= 0 and (keyword in arr_sorted[i].nama.lower() or keyword in arr_sorted[i].nim.lower() or keyword in arr_sorted[i].jurusan.lower()):
                result.append(arr_sorted[i]); i -= 1
            i = mid+1
            while i < len(arr_sorted) and (keyword in arr_sorted[i].nama.lower() or keyword in arr_sorted[i].nim.lower() or keyword in arr_sorted[i].jurusan.lower()):
                result.append(arr_sorted[i]); i += 1
            break
        elif keyword < midval:
            right = mid - 1
        else:
            left = mid + 1
    return result

# ---------- Sorting algorithms (operate on Python list of Mahasiswa) ----------
def bubble_sort(arr: List[Mahasiswa], key: str, reverse: bool=False):
    a = arr[:]  # copy
    n = len(a)
    for i in range(n):
        for j in range(0, n-i-1):
            v1 = getattr(a[j], key)
            v2 = getattr(a[j+1], key)
            if (v1 > v2 and not reverse) or (v1 < v2 and reverse):
                a[j], a[j+1] = a[j+1], a[j]
    return a

def insertion_sort(arr: List[Mahasiswa], key: str, reverse: bool=False):
    a = arr[:]
    for i in range(1, len(a)):
        current = a[i]
        j = i-1
        while j >= 0:
            vj = getattr(a[j], key)
            vc = getattr(current, key)
            if (vj > vc and not reverse) or (vj < vc and reverse):
                a[j+1] = a[j]
                j -= 1
            else:
                break
        a[j+1] = current
    return a

def selection_sort(arr: List[Mahasiswa], key: str, reverse: bool=False):
    a = arr[:]
    n = len(a)
    for i in range(n):
        sel = i
        for j in range(i+1, n):
            vj = getattr(a[j], key)
            vs = getattr(a[sel], key)
            if (vj < vs and not reverse) or (vj > vs and reverse):
                sel = j
        a[i], a[sel] = a[sel], a[i]
    return a

# helper to pick sorting algorithm
SORT_ALGS = {
    "bubble": bubble_sort,
    "insertion": insertion_sort,
    "selection": selection_sort
}

# ---------- ROUTES ----------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","").strip()
        users = load_users()
        if u in users and check_password_hash(users[u], p):
            session["user"] = u
            return redirect(url_for("index"))
        else:
            flash("Username atau password salah.", "error")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        users = load_users()
        if username in users:
            flash("Username sudah digunakan!", "error")
            return redirect(url_for("register"))
        users[username] = generate_password_hash(password)
        save_users(users)
        flash("Akun berhasil dibuat! Silakan login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# INDEX: search + filter + sort
@app.route("/")
@login_required
def index():
    data = load_data()
    q = request.args.get("q","").strip()
    jurusan_filter = request.args.get("jurusan","")
    method = request.args.get("method","linear")  # search method
    sort_alg = request.args.get("sort_alg", "")    # bubble/insertion/selection or empty
    sort_field = request.args.get("sort_field", "nama")  # nim/nama/ipk
    order = request.args.get("order", "asc")  # asc / desc

    # filter jurusan first
    if jurusan_filter:
        data = [m for m in data if m.jurusan == jurusan_filter]

    # search
    if q:
        if method == "linear":
            data = search_students(data, q)
        elif method == "sequential":
            # sequential same as linear but kept for UI parity
            data = [m for m in data if q.lower() in m.nim.lower() or q.lower() in m.nama.lower() or q.lower() in m.jurusan.lower()]
        elif method == "binary":
            data = binary_search(data, q)

    # sort
    reverse = (order == "desc")
    if sort_alg and sort_field:
        # use selected algorithm
        alg = SORT_ALGS.get(sort_alg, None)
        if alg:
            # need to ensure key exists; if ipk, key must be numeric; getattr works
            data = alg(data, sort_field, reverse=reverse)
    else:
        # default python sort (stable & fast)
        data = sorted(data, key=lambda x: getattr(x, sort_field), reverse=reverse)

    return render_template("index.html",
                           data=data,
                           jurusan_list=JURUSAN_LIST,
                           q=q,
                           jurusan_filter=jurusan_filter,
                           method=method,
                           sort_alg=sort_alg,
                           sort_field=sort_field,
                           order=order)

@app.route("/mahasiswa")
@login_required
def mahasiswa_page():
    data = load_data()
    return render_template("mahasiswa.html", data=data)

@app.route("/tambah", methods=["GET", "POST"])
@login_required
def tambah():
    if request.method == "POST":
        nim = request.form["nim"].strip()
        nama = request.form["nama"].strip()
        kelas = request.form["kelas"].strip().upper()
        ipk = request.form["ipk"].strip()
        jurusan = request.form["jurusan"].strip()
        validate_input(nim, nama, kelas, ipk, jurusan)
        data = load_data()
        # check duplicate nim
        if any(m.nim == nim for m in data):
            flash("NIM sudah terdaftar!", "error")
            return redirect(url_for("tambah"))
        m = Mahasiswa(nim, nama, kelas, float(ipk), jurusan)
        data.append(m)
        save_data(data)
        flash("Mahasiswa berhasil ditambahkan!", "success")
        return redirect(url_for('index'))
    return render_template("tambah.html", jurusan_list=JURUSAN_LIST)

@app.route("/delete/<nim>")
@login_required
def delete(nim):
    data = load_data()
    new_data = [m for m in data if m.nim != nim]
    if len(new_data) == len(data):
        flash("Data tidak ditemukan.", "error")
    else:
        save_data(new_data)
        flash("Data berhasil dihapus.", "info")
    return redirect(url_for("index"))

@app.route("/edit/<nim>", methods=["GET","POST"])
@login_required
def edit(nim):
    data = load_data()
    mhs = next((m for m in data if m.nim == nim), None)
    if not mhs:
        flash("Data tidak ditemukan.", "error")
        return redirect(url_for("index"))
    if request.method == "POST":
        try:
            nama = request.form["nama"].strip()
            kelas = request.form["kelas"].strip().upper()
            ipk = request.form["ipk"].strip()
            jurusan = request.form["jurusan"].strip()
            validate_input(nim, nama, kelas, ipk, jurusan)
            mhs.nama = nama
            mhs.kelas = kelas
            mhs.ipk = float(ipk)
            mhs.jurusan = jurusan
            save_data(data)
            flash("Data berhasil diperbarui.", "info")
            return redirect(url_for("index"))
        except Exception as e:
            flash(str(e), "error")
            return redirect(url_for("edit", nim=nim))
    return render_template("edit.html", mhs=mhs, jurusan_list=JURUSAN_LIST)

@app.route("/dashboard")
@login_required
def dashboard():
    data = load_data()
    total = len(data)
    avg_ipk = round(sum([m.ipk for m in data]) / total, 2) if total > 0 else 0
    per_jurusan = {j: len([m for m in data if m.jurusan == j]) for j in JURUSAN_LIST}

    return render_template(
        "dashboard.html",
        title="Dashboard",
        total=total,
        avg_ipk=avg_ipk,
        per_jurusan=per_jurusan
    )

@app.route("/api/search")
@login_required
def api_search():
    q = request.args.get("q","").strip()
    data = load_data()
    found = search_students(data, q) if q else data
    return jsonify([m.to_dict() for m in found])



# ---------- RUN ----------
if __name__ == "__main__":
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    if not os.path.exists(USERS_FILE):
        save_users({"admin": generate_password_hash("12345")})
    app.run(debug=True)