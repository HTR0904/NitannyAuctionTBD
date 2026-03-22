from flask import Flask, render_template, request, redirect, url_for
import sqlite3 as sql
import hashlib

app = Flask(__name__)

#Allows HTML pages to be updated by refreshing without having to rerun the code
app.config['TEMPLATES_AUTO_RELOAD'] = True

host = 'http://127.0.0.1:5000/'

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()
@app.route('/')
def index():
    # Renders the login page
    return render_template('login.html')

@app.route('/login_bidder', methods=['POST'])
def login_user():
    username = request.form.get('bidder_email')
    password = request.form.get('bidder_password')

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    cursor.execute("""
                   SELECT password_hash
                   FROM User_Login
                   WHERE email = ?
                   """, (username,))
    user = cursor.fetchone()
    # check if credentials match, if not return an error like  "Invalid username or password."
    if user is None:
        conn.close()
        return render_template('login.html', error="Invalid username or password")

    stored_hash = user[0]
    if hash_password(password) != stored_hash:
        conn.close()
        return render_template('login.html', error="Invalid username or password")

    # Check user account type (bidder or seller) and determine which HTML page to redirect them to it:
    cursor.execute("""
                   SELECT email
                   FROM Bidders
                   WHERE email = ?
                   """, (username,))
    if cursor.fetchone():
        conn.close()
        return redirect('/bidder')

    # Else, if account exists with these credential exists but no valid accounts type found (i.e. a helpdesk staff). Throw an error:
    conn.close()
    return render_template('login.html', error="Not a valid bidder account")


@app.route('/login_seller', methods=['POST'])
def login_seller():
    seller_username = request.form.get('seller_email')
    seller_password = request.form.get('seller_password')

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    cursor.execute("""
                   SELECT password_hash
                   FROM User_Login
                   WHERE email = ?
                   """, (seller_username,))

    user = cursor.fetchone()

    if user is None:
        conn.close()
        return render_template('login.html', error="Invalid login")

    stored_hash = user[0]

    # check if credentials match, if not return an error
    if hash_password(seller_password) != stored_hash:
        conn.close()
        return render_template('login.html', error="Invalid login")

    # Check user account type is a helpdesk account then redirect them to the HTML page.
    cursor.execute("""
                   SELECT email
                   FROM Sellers
                   WHERE email = ?
                   """, (seller_username,))
    if cursor.fetchone():
        conn.close()
        return redirect('/seller')

    # Else, if account exists with these credential but is not a helpdesk staff (i.e. this is a regular user). Throw an error:
    conn.close()
    return render_template('login.html', error="Not a valid seller account")

@app.route('/login_helpdesk', methods=['POST'])
def login_helpdesk():
    helpdesk_username = request.form.get('helpdesk_email')
    helpdesk_password = request.form.get('helpdesk_password')

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    cursor.execute("""
                   SELECT password_hash
                   FROM User_Login
                   WHERE email = ?
                   """, (helpdesk_username,))

    user = cursor.fetchone()

    if user is None:
        conn.close()
        return render_template('login.html', error="Invalid login")

    stored_hash = user[0]

    # check if credentials match, if not return an error
    if hash_password(helpdesk_password) != stored_hash:
        conn.close()
        return render_template('login.html', error="Invalid login")

    # Check user account type is a helpdesk account then redirect them to the HTML page.
    cursor.execute("""
                   SELECT email
                   FROM Helpdesk
                   WHERE email = ?
                   """, (helpdesk_username,))
    if cursor.fetchone():
        conn.close()
        return redirect('/helpdesk')

    # Else, if account exists with these credential but is not a helpdesk staff (i.e. this is a regular user). Throw an error:
    conn.close()
    return render_template('login.html', error="Not a helpdesk account")

@app.route('/bidder')
def bidder():
    return render_template('bidders_home.html')

@app.route('/seller')
def seller():
    return render_template('seller_home.html')

@app.route('/helpdesk')
def helpdesk():
    return render_template('helpdesk_home.html')

if __name__ == '__main__':
    #app.run()
    app.run(debug=True)  #enabled to run with TEMPLATES_AUTO_RELOAD
