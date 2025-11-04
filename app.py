import os
from datetime import date
from flask import Flask, render_template_string, request, redirect, url_for, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


db = SQLAlchemy()
login_manager = LoginManager()


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

    database_url = os.environ.get(
        "DATABASE_URL",
        # Default to local SQLite for development/testing
        "sqlite:///ewaste.db",
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"

    class User(UserMixin, db.Model):
        __tablename__ = "users"
        id = db.Column(db.Integer, primary_key=True)
        email = db.Column(db.String(255), unique=True, nullable=False)
        password_hash = db.Column(db.String(255), nullable=False)
        is_admin = db.Column(db.Boolean, default=False, nullable=False)

        def set_password(self, password: str) -> None:
            self.password_hash = generate_password_hash(password)

        def check_password(self, password: str) -> bool:
            return check_password_hash(self.password_hash, password)

    class Pickup(db.Model):
        __tablename__ = "pickups"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
        name = db.Column(db.String(255), nullable=False)
        email = db.Column(db.String(255), nullable=False)
        address = db.Column(db.String(500), nullable=False)
        item = db.Column(db.String(255), nullable=False)
        date = db.Column(db.String(20), nullable=False)  # ISO date string
        status = db.Column(db.String(32), nullable=False, default="Scheduled")

        user = db.relationship("User")

    with app.app_context():
        db.create_all()

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    # In-memory storage (for demo purposes)
    pickup_requests = []  # each: {id, name, email, address, item, date}
    next_id = {"value": 1}

    layout_css = """/* Tailwind handles most styling; keep minimal overrides if needed */"""

    home_html = """
    <!doctype html>
    <html lang=\"en\">
    <head>
        <meta charset=\"utf-8\">
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
        <title>E-Waste Management</title>
        <script src=\"https://cdn.tailwindcss.com\"></script>
        <style>{{ layout_css }}</style>
    </head>
    <body class=\"bg-gray-50 text-gray-800\">
        <nav class=\"bg-white border-b border-gray-200\">
            <div class=\"max-w-6xl mx-auto px-4 py-3 flex items-center justify-between\">
                <div class=\"text-xl font-bold\">E-Waste</div>
                <div class=\"space-x-6\">
                    <a id=\"navHome\" href=\"{{ url_for('index') }}\" class=\"text-gray-700 hover:text-black font-medium\">Home</a>
                    <a id=\"navCenters\" href=\"{{ url_for('centers') }}\" class=\"text-gray-700 hover:text-black font-medium\">Centers</a>
                    <a id=\"navSchedule\" href=\"{{ url_for('schedule') }}\" class=\"text-gray-700 hover:text-black font-medium\">Schedule Pickup</a>
                    <a id=\"navAdmin\" href=\"{{ url_for('admin_requests') }}\" class=\"text-gray-700 hover:text-black font-medium\">Admin</a>
                    {% if current_user.is_authenticated %}
                    <a id=\"navMyPickups\" href=\"{{ url_for('my_pickups') }}\" class=\"text-gray-700 hover:text-black font-medium\">My Pickups</a>
                    <span class=\"text-gray-500\">{{ current_user.email }}</span>
                    <a id=\"navLogout\" href=\"{{ url_for('logout') }}\" class=\"text-gray-700 hover:text-black font-medium\">Logout</a>
                    {% else %}
                    <a id=\"navLogin\" href=\"{{ url_for('login') }}\" class=\"text-gray-700 hover:text-black font-medium\">Login</a>
                    <a id=\"navRegister\" href=\"{{ url_for('register') }}\" class=\"text-gray-700 hover:text-black font-medium\">Register</a>
                    {% endif %}
                </div>
            </div>
        </nav>
        <header class=\"bg-gradient-to-r from-emerald-500 to-teal-600 text-white\">
            <div class=\"max-w-6xl mx-auto px-4 py-16\">
                <h1 class=\"text-3xl md:text-4xl font-bold\">Responsible E‑Waste Management</h1>
                <p class=\"mt-3 text-emerald-50 max-w-2xl\">Schedule safe pickup of electronic waste and find nearby authorized centers.</p>
                <a href=\"{{ url_for('schedule') }}\" class=\"inline-block mt-6 bg-white text-emerald-700 font-semibold px-5 py-3 rounded-lg shadow hover:shadow-md\">Schedule a Pickup</a>
            </div>
        </header>
        <main class=\"max-w-6xl mx-auto px-4 py-10\">
            <div class=\"grid gap-6 md:grid-cols-3\">
                <div class=\"bg-white rounded-xl border border-gray-200 p-6 shadow-sm\">
                    <h2 class=\"text-lg font-semibold\">Certified Centers</h2>
                    <p class=\"mt-2 text-sm text-gray-600\">Find vetted e‑waste collection partners near you.</p>
                </div>
                <div class=\"bg-white rounded-xl border border-gray-200 p-6 shadow-sm\">
                    <h2 class=\"text-lg font-semibold\">Convenient Pickup</h2>
                    <p class=\"mt-2 text-sm text-gray-600\">Choose a date and we’ll handle the rest.</p>
                </div>
                <div class=\"bg-white rounded-xl border border-gray-200 p-6 shadow-sm\">
                    <h2 class=\"text-lg font-semibold\">Safe Disposal</h2>
                    <p class=\"mt-2 text-sm text-gray-600\">Your devices are recycled following best practices.</p>
                </div>
            </div>
        </main>
    </body>
    </html>
    """

    centers_html = """
    <!doctype html>
    <html lang=\"en\">
    <head>
        <meta charset=\"utf-8\">
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
        <title>Centers</title>
        <script src=\"https://cdn.tailwindcss.com\"></script>
        <style>{{ layout_css }}</style>
    </head>
    <body class=\"bg-gray-50 text-gray-800\">
        <div class=\"max-w-6xl mx-auto px-4 py-10\">
            <h1 class=\"text-2xl font-bold mb-6\">Authorized Centers</h1>
            <div class=\"bg-white rounded-xl border border-gray-200 p-6 shadow-sm\">
                <div class=\"overflow-x-auto\">
                    <table id=\"centersTable\" class=\"min-w-full text-left text-sm\">
                        <thead class=\"text-gray-700\">
                            <tr>
                                <th class=\"py-2 pr-6\">Name</th>
                                <th class=\"py-2 pr-6\">City</th>
                                <th class=\"py-2 pr-6\">Contact</th>
                            </tr>
                        </thead>
                        <tbody class=\"divide-y divide-gray-100\">
                            <tr><td class=\"py-2 pr-6\">GreenTech Recycling</td><td class=\"py-2 pr-6\">Pune</td><td class=\"py-2 pr-6\">+91-9876543210</td></tr>
                            <tr><td class=\"py-2 pr-6\">EcoCycle Hub</td><td class=\"py-2 pr-6\">Mumbai</td><td class=\"py-2 pr-6\">+91-9000012345</td></tr>
                            <tr><td class=\"py-2 pr-6\">RenewIT</td><td class=\"py-2 pr-6\">Bengaluru</td><td class=\"py-2 pr-6\">+91-9123456780</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    schedule_html = """
    <!doctype html>
    <html lang=\"en\">
    <head>
        <meta charset=\"utf-8\">
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
        <title>Schedule Pickup</title>
        <script src=\"https://cdn.tailwindcss.com\"></script>
        <style>{{ layout_css }}</style>
    </head>
    <body class=\"bg-gray-50 text-gray-800\">
        <div class=\"max-w-2xl mx-auto px-4 py-10\">
            <h1 class=\"text-2xl font-bold mb-6\">Schedule Pickup</h1>
            <form method=\"post\" action=\"{{ url_for('schedule') }}\" class=\"bg-white rounded-xl border border-gray-200 p-6 shadow-sm space-y-4\">
                <div>
                    <label for=\"name\" class=\"block text-sm font-medium text-gray-700\">Full Name</label>
                    <input id=\"name\" name=\"name\" type=\"text\" required class=\"mt-1 block w-full rounded-lg border-gray-300 focus:border-emerald-500 focus:ring-emerald-500\">
                </div>
                <div>
                    <label for=\"email\" class=\"block text-sm font-medium text-gray-700\">Email</label>
                    <input id=\"email\" name=\"email\" type=\"email\" required class=\"mt-1 block w-full rounded-lg border-gray-300 focus:border-emerald-500 focus:ring-emerald-500\">
                </div>
                <div>
                    <label for=\"address\" class=\"block text-sm font-medium text-gray-700\">Address</label>
                    <input id=\"address\" name=\"address\" type=\"text\" required class=\"mt-1 block w-full rounded-lg border-gray-300 focus:border-emerald-500 focus:ring-emerald-500\">
                </div>
                <div>
                    <label for=\"item\" class=\"block text-sm font-medium text-gray-700\">Item</label>
                    <input id=\"item\" name=\"item\" type=\"text\" placeholder=\"e.g., Laptop\" required class=\"mt-1 block w-full rounded-lg border-gray-300 focus:border-emerald-500 focus:ring-emerald-500\">
                </div>
                <div>
                    <label for=\"date\" class=\"block text-sm font-medium text-gray-700\">Preferred Date</label>
                    <input id=\"date\" name=\"date\" type=\"date\" required class=\"mt-1 block w-full rounded-lg border-gray-300 focus:border-emerald-500 focus:ring-emerald-500\">
                </div>
                <button id=\"scheduleSubmit\" type=\"submit\" class=\"inline-flex items-center justify-center bg-emerald-600 hover:bg-emerald-700 text-white font-semibold px-4 py-2 rounded-lg\">Submit Request</button>
            </form>
        </div>
    </body>
    </html>
    """

    auth_html = """
    <!doctype html>
    <html lang=\"en\">
    <head>
        <meta charset=\"utf-8\">
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
        <title>{{ title }}</title>
        <script src=\"https://cdn.tailwindcss.com\"></script>
        <style>{{ layout_css }}</style>
    </head>
    <body class=\"bg-gray-50 text-gray-800\">
        <div class=\"max-w-md mx-auto px-4 py-10\">
            <h1 class=\"text-2xl font-bold mb-6\">{{ title }}</h1>
            <form method=\"post\" class=\"bg-white rounded-xl border border-gray-200 p-6 shadow-sm space-y-4\">
                {% if form == 'register' %}
                <div>
                    <label for=\"email\" class=\"block text-sm font-medium text-gray-700\">Email</label>
                    <input id=\"email\" name=\"email\" type=\"email\" required class=\"mt-1 block w-full rounded-lg border-gray-300 focus:border-emerald-500 focus:ring-emerald-500\">
                </div>
                <div>
                    <label for=\"password\" class=\"block text-sm font-medium text-gray-700\">Password</label>
                    <input id=\"password\" name=\"password\" type=\"password\" required class=\"mt-1 block w-full rounded-lg border-gray-300 focus:border-emerald-500 focus:ring-emerald-500\">
                </div>
                <div class=\"flex items-center\">
                    <input id=\"is_admin\" name=\"is_admin\" type=\"checkbox\" class=\"mr-2\">
                    <label for=\"is_admin\" class=\"text-sm text-gray-700\">Register as admin</label>
                </div>
                <button type=\"submit\" class=\"inline-flex items-center justify-center bg-emerald-600 hover:bg-emerald-700 text-white font-semibold px-4 py-2 rounded-lg\">Create Account</button>
                {% elif form == 'login' %}
                <div>
                    <label for=\"email\" class=\"block text-sm font-medium text-gray-700\">Email</label>
                    <input id=\"email\" name=\"email\" type=\"email\" required class=\"mt-1 block w-full rounded-lg border-gray-300 focus:border-emerald-500 focus:ring-emerald-500\">
                </div>
                <div>
                    <label for=\"password\" class=\"block text-sm font-medium text-gray-700\">Password</label>
                    <input id=\"password\" name=\"password\" type=\"password\" required class=\"mt-1 block w-full rounded-lg border-gray-300 focus:border-emerald-500 focus:ring-emerald-500\">
                </div>
                <button id=\"loginSubmit\" type=\"submit\" class=\"inline-flex items-center justify-center bg-emerald-600 hover:bg-emerald-700 text-white font-semibold px-4 py-2 rounded-lg\">Login</button>
                {% endif %}
            </form>
        </div>
    </body>
    </html>
    """

    confirm_html = """
    <!doctype html>
    <html lang=\"en\">
    <head>
        <meta charset=\"utf-8\">
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
        <title>Request Submitted</title>
        <script src=\"https://cdn.tailwindcss.com\"></script>
        <style>{{ layout_css }}</style>
    </head>
    <body class=\"bg-gray-50 text-gray-800\">
        <div class=\"max-w-xl mx-auto px-4 py-10\">
            <div class=\"bg-white rounded-xl border border-gray-200 p-6 shadow-sm\">
                <h1 id=\"confirmMsg\" class=\"text-xl font-semibold\">Pickup request #{{ rid }} created for {{ name }}</h1>
                <a id=\"adminLink\" href=\"{{ url_for('admin_requests') }}\" class=\"inline-block mt-4 text-emerald-700 hover:text-emerald-800 font-medium\">View all requests</a>
            </div>
        </div>
    </body>
    </html>
    """

    admin_html = """
    <!doctype html>
    <html lang=\"en\">
    <head>
        <meta charset=\"utf-8\">
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
        <title>Admin - Requests</title>
        <script src=\"https://cdn.tailwindcss.com\"></script>
        <style>{{ layout_css }}</style>
    </head>
    <body class=\"bg-gray-50 text-gray-800\">
        <div class=\"max-w-6xl mx-auto px-4 py-10\">
            <h1 class=\"text-2xl font-bold mb-6\">Pickup Requests</h1>
            <div class=\"bg-white rounded-xl border border-gray-200 p-6 shadow-sm\">
                <div class=\"overflow-x-auto\">
                <table id=\"requestsTable\" class=\"min-w-full text-left text-sm\">
                        <thead class=\"text-gray-700\">
                            <tr>
                                <th class=\"py-2 pr-6\">ID</th>
                                <th class=\"py-2 pr-6\">Name</th>
                                <th class=\"py-2 pr-6\">Email</th>
                                <th class=\"py-2 pr-6\">Item</th>
                                <th class=\"py-2 pr-6\">Date</th>
                                <th class=\"py-2 pr-6\">Status</th>
                                <th class=\"py-2 pr-6\"></th>
                            </tr>
                        </thead>
                        <tbody class=\"divide-y divide-gray-100\">
                            {% for r in requests %}
                            <tr>
                                <td class=\"py-2 pr-6\">{{ r.id }}</td>
                                <td class=\"py-2 pr-6\">{{ r.name }}</td>
                                <td class=\"py-2 pr-6\">{{ r.email }}</td>
                                <td class=\"py-2 pr-6\">{{ r.item }}</td>
                                <td class=\"py-2 pr-6\">{{ r.date }}</td>
                                <td class=\"py-2 pr-6\">{{ r.status }}</td>
                                <td class=\"py-2 pr-6\">
                                    <form method=\"post\" action=\"{{ url_for('update_status', pickup_id=r.id) }}\" class=\"flex items-center space-x-2\">
                                        <select name=\"status\" class=\"border rounded px-2 py-1\">
                                            {% for s in ['Scheduled','Assigned','Picked','Processing','Recycled','Cancelled'] %}
                                            <option value=\"{{ s }}\" {% if r.status == s %}selected{% endif %}>{{ s }}</option>
                                            {% endfor %}
                                        </select>
                                        <button type=\"submit\" class=\"text-emerald-700 font-medium\">Update</button>
                                    </form>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    my_pickups_html = """
    <!doctype html>
    <html lang=\"en\">
    <head>
        <meta charset=\"utf-8\">
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
        <title>My Pickups</title>
        <script src=\"https://cdn.tailwindcss.com\"></script>
        <style>{{ layout_css }}</style>
    </head>
    <body class=\"bg-gray-50 text-gray-800\">
        <div class=\"max-w-6xl mx-auto px-4 py-10\">
            <h1 class=\"text-2xl font-bold mb-6\">My Pickups</h1>
            <div class=\"bg-white rounded-xl border border-gray-200 p-6 shadow-sm\">
                <div class=\"overflow-x-auto\">
                    <table class=\"min-w-full text-left text-sm\">
                        <thead class=\"text-gray-700\">
                            <tr>
                                <th class=\"py-2 pr-6\">ID</th>
                                <th class=\"py-2 pr-6\">Item</th>
                                <th class=\"py-2 pr-6\">Date</th>
                                <th class=\"py-2 pr-6\">Status</th>
                            </tr>
                        </thead>
                        <tbody class=\"divide-y divide-gray-100\">
                            {% for r in requests %}
                            <tr>
                                <td class=\"py-2 pr-6\">{{ r.id }}</td>
                                <td class=\"py-2 pr-6\">{{ r.item }}</td>
                                <td class=\"py-2 pr-6\">{{ r.date }}</td>
                                <td class=\"py-2 pr-6\">{{ r.status }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    @app.get("/")
    def index():
        return render_template_string(home_html, layout_css=layout_css)

    @app.get("/centers")
    def centers():
        return render_template_string(centers_html, layout_css=layout_css)

    @app.get("/schedule")
    def schedule():
        return render_template_string(schedule_html, layout_css=layout_css)

    @login_required
    @app.post("/schedule")
    def schedule_post():
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        address = (request.form.get("address") or "").strip()
        item = (request.form.get("item") or "").strip()
        date = (request.form.get("date") or "").strip()

        p = Pickup(
            user_id=current_user.id,
            name=name,
            email=email,
            address=address,
            item=item,
            date=date,
            status="Scheduled",
        )
        db.session.add(p)
        db.session.commit()

        return render_template_string(confirm_html, rid=p.id, name=name, layout_css=layout_css)

    @login_required
    @app.get("/requests")
    def admin_requests():
        if not current_user.is_admin:
            return redirect(url_for("index"))
        requests_list = Pickup.query.order_by(Pickup.id.desc()).all()
        return render_template_string(admin_html, requests=requests_list, layout_css=layout_css)

    @login_required
    @app.post("/requests/<int:pickup_id>/status")
    def update_status(pickup_id: int):
        if not current_user.is_admin:
            return redirect(url_for("index"))
        p = Pickup.query.get_or_404(pickup_id)
        new_status = (request.form.get("status") or "").strip()
        if new_status:
            p.status = new_status
            db.session.commit()
        return redirect(url_for("admin_requests"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            is_admin = bool(request.form.get("is_admin"))
            if not email or not password:
                return render_template_string(auth_html, title="Register", form="register", layout_css=layout_css)
            if User.query.filter_by(email=email).first():
                return render_template_string(auth_html, title="Register", form="register", layout_css=layout_css)
            u = User(email=email, is_admin=is_admin)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            login_user(u)
            return redirect(url_for("index"))
        return render_template_string(auth_html, title="Register", form="register", layout_css=layout_css)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            u = User.query.filter_by(email=email).first()
            if u and u.check_password(password):
                login_user(u)
                return redirect(url_for("index"))
        return render_template_string(auth_html, title="Login", form="login", layout_css=layout_css)

    @app.get("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))

    @app.get("/my-pickups")
    @login_required
    def my_pickups():
        mine = Pickup.query.filter_by(user_id=current_user.id).order_by(Pickup.id.desc()).all()
        return render_template_string(my_pickups_html, requests=mine, layout_css=layout_css)

    return app


if __name__ == "__main__":
    # Development run: python app.py
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)


