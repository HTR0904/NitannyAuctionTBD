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
