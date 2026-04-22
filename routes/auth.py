from flask import Blueprint, render_template, session, redirect, url_for, request
import uuid
from utils import *
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@auth_bp.route('/login_bidder', methods=['POST'])
def login_bidder():
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
    if request.method == 'GET':
        return render_template('register.html')

    role = request.form.get('role')
    is_vendor = request.form.get('is_vendor') == 'on'
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    if not email or not password or not role:
        return render_template('register.html', error="Please fill out all required fields.")

    if password != confirm_password:
        return render_template('register.html', error="Passwords do not match.")

    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        # Check existing user
        cursor.execute("SELECT email FROM User_Login WHERE email = ?", (email,))
        if cursor.fetchone():
            return render_template('register.html', error="This email is already registered.")

        # Base Login Entry (Common to all)
        cursor.execute("INSERT INTO User_Login (email, password_hash) VALUES (?, ?)",
                       (email, hash_password(password)))

        # Helpdesk Registration
        if role == 'helpdesk':
            position = request.form.get('position', '').strip() or 'Helpdesk Staff'
            cursor.execute("INSERT INTO Helpdesk (email, position) VALUES (?, ?)", (email, position))

            # Create the required staff request
            cursor.execute(
                '''
                INSERT INTO Requests (sender_email, helpdesk_staff_email, request_type, request_desc, request_status)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (email, DEFAULT_HELPDESK_EMAIL, 'Registration', position, 0),  # 0: incomplete
            )

        #  BIDDER & SELLER
        else:
            # Everyone who isn't helpdesk is a Bidder
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            age = request.form.get('age')
            major = request.form.get('major', '').strip() or None

            # Handle Home Address
            home_address_id = None
            h_street_num = request.form.get('street_num')
            h_street_name = request.form.get('street_name', '').strip()
            h_zipcode = request.form.get('zipcode')

            if h_street_num and h_street_name and h_zipcode:
                home_address_id = uuid.uuid4().hex
                cursor.execute(
                    "INSERT INTO Address (address_id, zipcode, street_num, street_name) VALUES (?, ?, ?, ?)",
                    (home_address_id, h_zipcode, h_street_num, h_street_name),
                )

            cursor.execute(
                '''
                INSERT INTO Bidders (email, first_name, last_name, age, home_address_id, major)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (email, first_name, last_name, age or None, home_address_id, major),
            )

            # Seller banking details
            if role == 'seller':
                bank_routing = request.form.get('bank_routing_number', '').strip()
                bank_account = request.form.get('bank_account_number')
                cursor.execute(
                    "INSERT INTO Sellers (email, bank_routing_number, bank_account_number, balance) VALUES (?, ?, ?, 0)",
                    (email, bank_routing, bank_account),
                )

                # Local Vendor forms goes here
                if is_vendor:
                    business_name = request.form.get('business_name', '').strip()
                    phone = request.form.get('customer_service_phone', '').strip()

                    biz_address_id = None
                    v_street_num = request.form.get('v_street_num')
                    v_street_name = request.form.get('v_street_name', '').strip()
                    v_zipcode = request.form.get('v_zipcode')

                    if v_street_num and v_street_name and v_zipcode:
                        biz_address_id = uuid.uuid4().hex
                        cursor.execute(
                            "INSERT INTO Address (address_id, zipcode, street_num, street_name) VALUES (?, ?, ?, ?)",
                            (biz_address_id, v_zipcode, v_street_num, v_street_name),
                        )

                    cursor.execute(
                        '''
                        INSERT INTO Local_Vendors (Email, Business_Name, Business_Address_ID,
                                                   Customer_Service_Phone_Number)
                        VALUES (?, ?, ?, ?)
                        ''',
                        (email, business_name, biz_address_id, phone),
                    )

        conn.commit()
        ensure_app_user(email, role)
        return render_template('register.html', success=f"Account created as {role}!")

    except sql.Error as e:
        conn.rollback()
        return render_template('register.html', error=f"Database error: {str(e)}")
    finally:
        conn.close()