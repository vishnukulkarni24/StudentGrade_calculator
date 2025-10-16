from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Change in production

# -------------------------------
# Database connection
# -------------------------------
def connect_db():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="root",
            database="studentdb"
        )
        return conn
    except mysql.connector.Error as err:
        print("DB connection error:", err)
        exit()

# -------------------------------
# Student operations
# -------------------------------
def calculate_grade(percentage):
    if percentage >= 90:
        return "A, First Class Distinction"
    elif percentage >= 75:
        return "B, Distinction"
    elif percentage >= 50:
        return "C, Pass"
    else:
        return "F, Failed"

def fetch_data():
    conn = connect_db()
    df = pd.read_sql("SELECT * FROM students", conn)
    conn.close()
    return df

def insert_student(name, math, science, english):
    total = math + science + english
    percentage = total / 300 * 100
    grade = calculate_grade(percentage)

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO students (name, math, science, english, total_marks, percentage, grade)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (name, math, science, english, total, percentage, grade))
    conn.commit()
    conn.close()

def update_student(student_id, math, science, english):
    total = math + science + english
    percentage = total / 300 * 100
    grade = calculate_grade(percentage)

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE students
        SET math=%s, science=%s, english=%s, total_marks=%s, percentage=%s, grade=%s
        WHERE id=%s
    """, (math, science, english, total, percentage, grade, student_id))
    conn.commit()
    conn.close()

# -------------------------------
# Charts for stats
# -------------------------------
def get_charts():
    df = fetch_data()
    if df.empty:
        return "", ""

    plt.figure(figsize=(5,3))
    plt.bar(df["name"], df["percentage"], color='lightblue', edgecolor='black')
    plt.title("Score of Students")
    plt.xlabel("Student Name")
    plt.ylabel("Percentage")
    plt.ylim(0,100)
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    bar_chart = base64.b64encode(buf.getvalue()).decode()
    plt.close()

    plt.figure(figsize=(5,3))
    grade_counts = df["grade"].value_counts()
    plt.pie(grade_counts, labels=grade_counts.index, autopct='%1.1f%%', startangle=140)
    plt.title("Grade Distribution")
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    pie_chart = base64.b64encode(buf.getvalue()).decode()
    plt.close()

    return bar_chart, pie_chart

# -------------------------------
# Routes
# -------------------------------

# Home page
# Home page for everyone
@app.route('/home')
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("home.html")

# Student list page
@app.route('/student_list')
def student_list():
    if "user" not in session:
        return redirect(url_for("login"))

    df = fetch_data()
    return render_template(
        "index.html", 
        students=df.to_dict(orient='records'),
        role=session.get('role')  # pass role to template
    )

# Student list
@app.route('/')
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    df = fetch_data()
    return render_template("index.html", students=df.to_dict(orient='records'))

# Stats page
@app.route('/stats')
def stats():
    if "user_id" not in session:
        return redirect(url_for("login"))
    df = fetch_data()
    grade_counts = df['grade'].value_counts().to_dict() if not df.empty else {}
    avg_percentage = df['percentage'].mean() if not df.empty else 0
    bar_chart, pie_chart = get_charts()
    return render_template("stats.html",
                           grade_counts=grade_counts,
                           avg_percentage=round(avg_percentage, 2),
                           bar_chart=bar_chart,
                           pie_chart=pie_chart)

# Add student (admin only)
@app.route('/add_student', methods=['GET', 'POST'])
def add_student_route():
    if "user_id" not in session or session['role'] != 'admin':
        flash("Only admin can add students!", "error")
        return redirect(url_for("home"))
    if request.method == 'POST':
        name = request.form['name']
        math = float(request.form['math'])
        science = float(request.form['science'])
        english = float(request.form['english'])
        insert_student(name, math, science, english)
        flash(f"Student {name} added successfully!", "success")
        return redirect(url_for("index"))
    return render_template("add_student.html")

# Update student (admin only)
@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update_route(id):
    if "user_id" not in session or session['role'] != 'admin':
        flash("Only admin can update students!", "error")
        return redirect(url_for("home"))
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM students WHERE id=%s", (id,))
    student = cursor.fetchone()
    conn.close()
    if request.method == 'POST':
        math = float(request.form['math'])
        science = float(request.form['science'])
        english = float(request.form['english'])
        update_student(id, math, science, english)
        flash(f"Student {student['name']} updated successfully!", "success")
        return redirect(url_for("index"))
    return render_template("update_student.html", student=student)

@app.route('/student_list')
def home_student_list():
    if "user" not in session:
        return redirect(url_for("login"))

    # Fetch all students
    df = fetch_data()
    
    # Pass data to index.html
    return render_template("index.html", students=df.to_dict(orient='records'))

# Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        hashed_password = generate_password_hash(password)
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                           (username, hashed_password, role))
            conn.commit()
            flash("Registration successful! Please login.", "success")
        except mysql.connector.IntegrityError:
            flash("Username already exists!", "error")
        finally:
            conn.close()
        return redirect(url_for("login"))
    return render_template("register.html")

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash("Please enter both username and password!", "error")
            return redirect(url_for('login'))
        conn = connect_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f"Welcome {user['username']}!", "success")
            return redirect(url_for('home'))
        else:
            flash("Invalid username or password!", "error")
            return redirect(url_for('login'))
    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for("login"))

if __name__ == '__main__':
    app.run(debug=True)
