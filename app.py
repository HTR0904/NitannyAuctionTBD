from urllib.parse import urlparse
from flask import Flask, flash, render_template, request, redirect, session, url_for
import sqlite3 as sql
import hashlib

app = Flask(__name__)

# Allows HTML pages to be updated by refreshing without having to rerun the code
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Required for session to work
app.secret_key = 'projectTBD_secret_key'

host = 'http://127.0.0.1:5000/'

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()
@app.route('/')
def index():
    #Checks for session first
    if 'user_email' in session and 'account_type' in session:
        # if session exists, instantly redirect to specific dashboard
        return redirect(session['account_type'])
    #Otherwise, render the login page
    return render_template('login.html')

@app.route('/logout')
def logout():
    """
    With session, the browser will now remember login even after we terminate the server
    Session will remain until you close the browser window
    In case of errors or to kill the session without logout fully implemented:
    Type the following into your browser's URL bar: http://127.0.0.1:5000/logout
    """
    session.clear()
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

        # Needed for session: store the user's email
        session['user_email'] = username
        session['account_type'] = '/bidder'
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

        #Needed for session
        session['user_email'] = seller_username
        session['account_type'] = '/seller'
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
        # Needed for session
        session['user_email'] = helpdesk_username
        session['account_type'] = '/helpdesk'
        return redirect('/helpdesk')

    # Else, if account exists with these credential but is not a helpdesk staff (i.e. this is a regular user). Throw an error:
    conn.close()
    return render_template('login.html', error="Not a helpdesk account")


@app.route('/change_password', methods=['POST'])
def change_password():

    user_email = session['user_email']
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_new_password = request.form.get('confirm_new_password')

    # Parse the referrer URL into a template filename (e.g., '/seller' -> 'seller.html')
    # Defaults to 'dev_test.html' if the referrer is the root path '/'
    raw_path = urlparse(request.referrer).path.strip('/')
    template_name = f"{raw_path}.html" if raw_path else "dev_test.html"

    if new_password != confirm_new_password:
        return render_template(template_name, password_error="New passwords do not match.")

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    try:
        cursor.execute('''SELECT password_hash 
                          FROM User_Login 
                          WHERE email = ?
                        ''', (user_email,))
        user = cursor.fetchone()

        if user and user[0] == hash_password(current_password):
            cursor.execute('''
                           UPDATE User_Login
                           SET password_hash = ?
                           WHERE email = ?
                           ''', (hash_password(new_password), user_email))
            conn.commit()

            return render_template(template_name, password_success="Your password has been updated successfully.")
        else:
            return render_template(template_name, password_error="Incorrect current password.")

    except sql.Error as e:
        print(f"Database error: {e}")
        return render_template(template_name, password_error="An error occurred while updating your password.")
    finally:
        conn.close()

@app.route('/submit_ticket', methods=['POST'])
def submit_ticket():

    sender_email = session['user_email']

    req_type = request.form.get('request_type')
    req_desc = request.form.get('request_desc')

    initial_status = 0
    default_staff_email = 'unassigned@helpdesk.com'

    # Parse the referrer URL into a template filename
    raw_path = urlparse(request.referrer).path.strip('/')
    template_name = f"{raw_path}.html" if raw_path else "dev_test.html"

    print(template_name)

    if not req_type or not req_desc:
        return render_template(template_name, helpdesk_req_error="Please fill out all helpdesk fields.")

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    try:
        cursor.execute('''
                       INSERT INTO Requests (sender_email, helpdesk_staff_email, request_type, request_desc,
                                             request_status)
                       VALUES (?, ?, ?, ?, ?)
                       ''', (sender_email, default_staff_email, req_type, req_desc, initial_status))
        conn.commit()
        return render_template(template_name, helpdesk_req_success="Your request has been submitted successfully!")
    except sql.Error as e:
        print(f"Database error: {e}")
        return render_template(template_name, helpdesk_req_error="An error occurred while submitting your request.")
    finally:
        conn.close()
@app.route('/bidder')
def bidder():
    return render_template('bidders_home.html')

@app.route('/seller')
def seller():
    return render_template('seller_home.html')

@app.route('/helpdesk')
def helpdesk():
    return render_template('helpdesk_home.html')

#TODO: reconsolidate this with actual listing logic
@app.route('/listing/<int:listing_id>')
def view_listing(listing_id):
    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()
    # Grab the actual listing using the listing_id
    cursor.execute('''SELECT * 
                      FROM Auction_Listings 
                      WHERE Listing_ID = ?
                   ''', (listing_id,))
    listing = cursor.fetchone()

    if not listing:
        conn.close()
        return "Listing not found", 404 # 404 will trigger acutal browser behaviour

    # Check watchlist status:
    is_watching = False
    if 'user_email' in session and session.get('account_type') == '/bidder':
        cursor.execute('''
                       SELECT 1
                       FROM Watchlist
                       WHERE Bidder_Email = ?
                         AND Listing_ID = ?
                       ''', (session['user_email'], listing_id))
        is_watching = bool(cursor.fetchone())

    conn.close()

    # TODO: update html to be an actual one and not dev_test
    return render_template('dev_test.html', listing=listing, is_watching=is_watching)

@app.route('/toggle_watchlist', methods=['POST'])
def toggle_watchlist():
    # Security: Ensure only bidders can watch
    if 'user_email' not in session or session.get('account_type') != '/bidder':
        flash("You must be logged in as a bidder to use the watchlist.", "auth_error")
        return redirect(url_for('index'))

    bidder_email = session['user_email']
    listing_id = request.form.get('listing_id')
    seller_email = request.form.get('seller_email')

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    try:
        # Check status (watching or not)
        cursor.execute('''
                       SELECT 1
                       FROM Watchlist
                       WHERE Bidder_Email = ?
                         AND Listing_ID = ?
                       ''', (bidder_email, listing_id))

        if cursor.fetchone():
            # UNWATCH
            cursor.execute('''
                           DELETE
                           FROM Watchlist
                           WHERE Bidder_Email = ?
                             AND Listing_ID = ?
                           ''', (bidder_email, listing_id))
            flash("Listing removed from your watchlist.", "watch_success")
        else:
            # WATCH
            cursor.execute('''
                           INSERT INTO Watchlist (Bidder_Email, Listing_ID, Seller_Email)
                           VALUES (?, ?, ?)
                           ''', (bidder_email, listing_id, seller_email))
            flash("Listing added to your watchlist!", "watch_success")

        conn.commit()
    except sql.Error as e:
        print(f"Database error: {e}")
        flash("An error occurred while updating your watchlist.", "watch_error")
    finally:
        conn.close()

    return redirect(request.referrer)


if __name__ == '__main__':
    #app.run()
    app.run(debug=True)  #enabled to run with TEMPLATES_AUTO_RELOAD
