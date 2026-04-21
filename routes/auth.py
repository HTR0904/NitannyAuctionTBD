from flask import Blueprint, render_template, session, redirect, url_for, request
from utils import *
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@auth_bp.route('/login_bidder', methods=['POST'])
def login_bidder():
    ensure_admin_schema()
    username = request.form.get('bidder_email')
    password = request.form.get('bidder_password')

    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM User_Login WHERE email = ?", (username,))
    user = cursor.fetchone()
    if user is None:
        if authenticate_app_user(username, password, 'bidder'):
            session['user_email'] = username
            session['account_type'] = '/bidder'
            return redirect('/bidder')
        conn.close()
        return render_template('login.html', error="Invalid username or password")

    if hash_password(password) != user[0]:
        conn.close()
        return render_template('login.html', error="Invalid username or password")

    cursor.execute("SELECT email FROM Bidders WHERE email = ?", (username,))
    if cursor.fetchone():
        conn.close()
        ensure_app_user(username, 'bidder')
        session['user_email'] = username
        session['account_type'] = '/bidder'
        return redirect('/bidder')

    conn.close()
    return render_template('login.html', error="Not a valid bidder account")


@auth_bp.route('/login_seller', methods=['POST'])
def login_seller():
    ensure_admin_schema()
    seller_username = request.form.get('seller_email')
    seller_password = request.form.get('seller_password')

    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM User_Login WHERE email = ?", (seller_username,))
    user = cursor.fetchone()

    if user is None:
        if authenticate_app_user(seller_username, seller_password, 'seller'):
            session['user_email'] = seller_username
            session['account_type'] = '/seller'
            return redirect('/seller')
        conn.close()
        return render_template('login.html', error="Invalid login")

    if hash_password(seller_password) != user[0]:
        conn.close()
        return render_template('login.html', error="Invalid login")

    cursor.execute("SELECT email FROM Sellers WHERE email = ?", (seller_username,))
    if cursor.fetchone():
        conn.close()
        ensure_app_user(seller_username, 'seller')
        session['user_email'] = seller_username
        session['account_type'] = '/seller'
        return redirect('/seller')

    conn.close()
    return render_template('login.html', error="Not a valid seller account")


@auth_bp.route('/login_helpdesk', methods=['POST'])
def login_helpdesk():
    ensure_admin_schema()
    helpdesk_username = request.form.get('helpdesk_email')
    helpdesk_password = request.form.get('helpdesk_password')

    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM User_Login WHERE email = ?", (helpdesk_username,))
    user = cursor.fetchone()

    if user is None:
        if authenticate_app_user(helpdesk_username, helpdesk_password, 'helpdesk'):
            session['user_email'] = helpdesk_username
            session['account_type'] = '/helpdesk'
            return redirect('/helpdesk')
        conn.close()
        return render_template('login.html', error="Invalid login")

    if hash_password(helpdesk_password) != user[0]:
        conn.close()
        return render_template('login.html', error="Invalid login")

    cursor.execute("SELECT email FROM Helpdesk WHERE email = ?", (helpdesk_username,))
    if cursor.fetchone():
        conn.close()
        ensure_app_user(helpdesk_username, 'helpdesk')
        session['user_email'] = helpdesk_username
        session['account_type'] = '/helpdesk'
        return redirect('/helpdesk')

    conn.close()
    return render_template('login.html', error="Not a helpdesk account")

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    ensure_admin_schema()
    if request.method == 'GET':
        return render_template('register.html')

    role = request.form.get('role')
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    age = request.form.get('age')
    major = request.form.get('major', '').strip() or None
    street_num = request.form.get('street_num')
    street_name = request.form.get('street_name', '').strip()
    zipcode = request.form.get('zipcode')
    bank_routing = request.form.get('bank_routing_number', '').strip()
    bank_account = request.form.get('bank_account_number')

    if not email or not password or not first_name or not last_name:
        return render_template('register.html', error="Please fill out all required fields.")
    if password != confirm_password:
        return render_template('register.html', error="Passwords do not match.")
    if len(password) < 6:
        return render_template('register.html', error="Password must be at least 6 characters.")
    if role not in ('bidder', 'seller'):
        return render_template('register.html', error="Invalid account type selected.")
    if role == 'seller' and (not bank_routing or not bank_account):
        return render_template('register.html', error="Sellers must provide banking information.")

    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT email FROM User_Login WHERE email = ?", (email,))
        if cursor.fetchone():
            return render_template('register.html', error="This email is already registered. Please log in instead.")

        home_address_id = None
        if street_num and street_name and zipcode:
            cursor.execute("SELECT zipcode FROM Zipcode_Info WHERE zipcode = ?", (zipcode,))
            if not cursor.fetchone():
                return render_template('register.html', error=f"Zipcode {zipcode} is not recognized in our system.")

            home_address_id = uuid.uuid4().hex
            cursor.execute(
                '''
                INSERT INTO Address (address_id, zipcode, street_num, street_name)
                VALUES (?, ?, ?, ?)
                ''',
                (home_address_id, zipcode, street_num, street_name),
            )

        cursor.execute("INSERT INTO User_Login (email, password_hash) VALUES (?, ?)", (email, hash_password(password)))
        cursor.execute(
            '''
            INSERT INTO Bidders (email, first_name, last_name, age, home_address_id, major)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (email, first_name, last_name, age or None, home_address_id, major),
        )

        if role == 'seller':
            cursor.execute(
                '''
                INSERT INTO Sellers (email, bank_routing_number, bank_account_number, balance)
                VALUES (?, ?, ?, 0)
                ''',
                (email, bank_routing, bank_account),
            )

        conn.commit()
        ensure_app_user(email, role)
        return render_template('register.html', success=f"Account created successfully as a {role}!")
    except sql.Error as e:
        conn.rollback()
        print(f"Registration database error: {e}")
        return render_template('register.html', error="A database error occurred. Please try again.")
    finally:
        conn.close()