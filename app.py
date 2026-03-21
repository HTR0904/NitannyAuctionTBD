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

@app.route('/login_user', methods=['POST'])
def login_user():
    username = request.form.get('user_email')
    password = request.form.get('user_password')

    conn = sql.connect("auction.db")
    cursor = conn.cursor()

    '''
    Commented out until db implemented
    cursor.execute("""
                   SELECT password_hash, role
                   FROM user_login
                   WHERE email = ?
                   """, (username,))
    '''
    user = cursor.fetchone()
    conn.close()

    # check if credentials match, if not return an error like  "Invalid username or password."
    if user is None:
        return render_template('login.html', error="Invalid username or password")

    stored_hash, role = user

    if hash_password(password) != stored_hash:
        return render_template('login.html', error="Invalid username or password")

    # Check user account type (bidder or seller) and determine which HTML page to redirect them to it:
    if role == "bidder":
        return redirect('/bidder')
    elif role == "seller":
        return redirect('/seller')
    else:
        # Else, if account exists with these credential exists but no valid accounts type found (i.e. a helpdesk staff). Throw an error:
        return render_template('login.html', error="Not a valid user account")

@app.route('/login_helpdesk', methods=['POST'])
def login_helpdesk():
    helpdesk_username = request.form.get('helpdesk_email')
    helpdesk_password = request.form.get('helpdesk_password')

    conn = sql.connect("auction.db")
    cursor = conn.cursor()

    '''
    Commented out until db implemented
    cursor.execute("""
                   SELECT password_hash, role
                   FROM user_login
                   WHERE email = ?
                   """, (helpdesk_username,))

    '''
    user = cursor.fetchone()
    conn.close()

    if user is None:
        return render_template('login.html', error="Invalid login")

    stored_hash, role = user

    # check if credentials match, if not return an error
    if hash_password(helpdesk_password) != stored_hash:
        return render_template('login.html', error="Invalid login")

    # Check user account type is a helpdesk account then redirect them to the HTML page.
    if role == "helpdesk":
        return redirect('/helpdesk')
    else:
        # Else, if account exists with these credential but is not a helpdesk staff (i.e. this is a regular user). Throw an error:
        return render_template('login.html', error="Not a helpdesk account")

if __name__ == '__main__':
    #app.run()
    app.run(debug=True)  #enabled to run with TEMPLATES_AUTO_RELOAD
