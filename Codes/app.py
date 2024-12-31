import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SECRET_KEY'] = 'Tanya_SuperStar'
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Название маршрута для входа

# Словарь пользователей для демонстрации
users = {
    "admin": {"password": "adminpassword", "role": "admin"},
    "user": {"password": "userpassword", "role": "user"}
}

# Модель пользователя
class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.role = users[username]["role"]

@login_manager.user_loader
def load_user(username):
    if username in users:
        return User(username)
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Проверка логина и пароля
        if username in users and users[username]['password'] == password:
            user = User(username)
            login_user(user)
            return redirect(url_for('dashboard'))

        flash('Неправильное имя пользователя или пароль', 'danger')

    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=current_user.id)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/statistics', methods=['GET'])
@login_required
def statistics():
    if current_user.role != 'admin':
        return '''
        <html>
            <body style="text-align: center; padding: 50px;">
                <h1 style="color: red; font-size: 36px;">Доступно только администратору!</h1>
                <p style="font-size: 20px;">У вас нет необходимых прав для доступа к этой странице.</p>
            </body>
        </html>
        ''', 403


    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM logs")
    data = cursor.fetchall()
    conn.close()
    return render_template('stat.html', data=data)

def init_db():
    with app.app_context():
        db.create_all()

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
