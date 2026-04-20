from urllib.parse import urlparse
from flask import Flask, flash, render_template, request, redirect, session, url_for
import sqlite3 as sql
import hashlib
import uuid
app = Flask(__name__)

def init_db():
    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Notifications (
            notification_id Integer PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            content TEXT NOT NULL,
            link TEXT,
            is_read INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0, 1)),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_email) REFERENCES User_Login(email)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Chat_Threads(
            thread_id INTEGER PRIMARY KEY AUTOINCREMENT,
            bidder_email TEXT NOT NULL,
            seller_email TEXT NOT NULL,
            listing_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (bidder_email, seller_email, listing_id),
            FOREIGN KEY (bidder_email) REFERENCES User_Login(email),
            FOREIGN KEY (seller_email) REFERENCES User_Login(email)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Chat_Messages
        (
            message_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id    INTEGER NOT NULL,
            sender_email TEXT    NOT NULL,
            content      TEXT    NOT NULL,
            sent_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (thread_id) REFERENCES Chat_Threads (thread_id) ON DELETE CASCADE,
            FOREIGN KEY (sender_email) REFERENCES User_Login (email)
        )
    """)

    conn.commit()
    conn.close()

init_db()

def create_notification(user_email, content, link=None):
    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Notifications (user_email, content, link) VALUES (?, ?, ?)",
        (user_email,content,link)
    )
    conn.commit()
    conn.close()

@app.route('/notifications')
def notifications():
    if 'user_email' not in session:
        return redirect('/')

    user_email = session['user_email']

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    cursor.execute('''
        SELECT notification_id, content, link, is_read, created_at
        FROM Notifications
        WHERE user_email = ?
        ORDER BY created_at DESC, notification_id DESC
    ''', (user_email,))

    notifs = []
    for row in cursor.fetchall():
        notifs.append({
            'id': row[0],
            'content': row[1],
            'link': row[2],
            'is_read': row[3],
            'created_at': row[4]
        })

    conn.close()

    return render_template('notifications.html',
                           notifications=notifs,
                           user_email=user_email,
                           account_type=session.get('account_type'))


@app.route('/notifications/mark_read/<int:notif_id>', methods=['POST'])
def mark_notification_read(notif_id):
    if 'user_email' not in session:
        return redirect('/')

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()
    #only marrk self noti
    cursor.execute(
        "UPDATE Notifications SET is_read = 1 WHERE notification_id = ? AND user_email = ?",
        (notif_id, session['user_email'])
    )
    conn.commit()
    conn.close()
    return redirect('/notifications')


@app.route('/notifications/mark_all_read', methods=['POST'])
def mark_all_read():
    if 'user_email' not in session:
        return redirect('/')

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE Notifications SET is_read = 1 WHERE user_email = ?",
        (session['user_email'],)
    )
    conn.commit()
    conn.close()
    return redirect('/notifications')

@app.route('/notifications/delete/<int:notif_id>', methods=['POST'])
def delete_notification(notif_id):
    if 'user_email' not in session:
        return redirect('/')

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM Notifications WHERE notification_id = ? AND user_email = ?",
        (notif_id, session['user_email'])
    )
    conn.commit()
    conn.close()
    return redirect('/notifications')

@app.route('/notifications/delete_all', methods=['POST'])
def delete_all_notifications():
    if 'user_email' not in session:
        return redirect('/')

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM Notifications WHERE user_email = ?",
        (session['user_email'],)
    )
    conn.commit()
    conn.close()
    return redirect('/notifications')

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
@app.route('/seller')
def seller():
    if 'user_email' not in session or session.get('account_type') != '/seller':
        return redirect('/')

    seller_email = session['user_email']

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    #search categories
    cursor.execute("SELECT category_name FROM Categories ORDER BY category_name")
    categories = [r[0] for r in cursor.fetchall()]

    #search goods, price
    cursor.execute('''
        SELECT 
            al.Listing_ID,
            al.Auction_Title,
            al.Product_Name,
            al.Category,
            al.Reserve_Price,
            al.Max_bids,
            al.Status,
            COUNT(b.Bid_ID) AS bid_count,
            MAX(b.Bid_Price) AS current_bid
        FROM Auction_Listings al
        LEFT JOIN Bids b 
            ON al.Listing_ID = b.Listing_ID 
            AND al.Seller_Email = b.Seller_Email
        WHERE al.Seller_Email = ?
        GROUP BY al.Listing_ID
        ORDER BY al.Status DESC, al.Listing_ID DESC
    ''', (seller_email,))

    my_listings = []
    for row in cursor.fetchall():
        my_listings.append({
            'listing_id': row[0],
            'auction_title': row[1],
            'product_name': row[2],
            'category': row[3],
            'reserve_price': row[4],
            'max_bids': row[5],
            'status': row[6],
            'bid_count': row[7],
            'current_bid': row[8]
        })

    conn.close()
    return render_template('seller_home.html',
                           categories=categories,
                           my_listings=my_listings)
@app.route('/list_product', methods=['POST'])
def list_product():
    #only seller upload
    if 'user_email' not in session or session.get('account_type') != '/seller':
        return redirect('/')

    seller_email = session['user_email']
    auction_title = request.form.get('auction_title', '').strip()
    product_name = request.form.get('product_name', '').strip()
    product_description = request.form.get('product_description', '').strip()
    category = request.form.get('category')
    reserve_price = request.form.get('reserve_price')
    quantity = request.form.get('quantity')
    max_bids = request.form.get('max_bids')

    def render_seller(**kwargs):
        conn = sql.connect("dataset_tables.db")
        cursor = conn.cursor()
        cursor.execute("SELECT category_name FROM Categories ORDER BY category_name")
        cats = [r[0] for r in cursor.fetchall()]
        conn.close()
        return render_template('seller_home.html', categories=cats, **kwargs)

    #verify required
    if not all([auction_title, product_name, product_description, category, reserve_price, quantity, max_bids]):
        return render_seller(listing_error="Please fill out all required fields.")

    #verify num
    try:
        reserve_price_num = float(reserve_price)
        quantity_int = int(quantity)
        max_bids_int = int(max_bids)
        if reserve_price_num < 0 or quantity_int < 1 or max_bids_int < 1:
            return render_seller(listing_error="Numeric fields must be positive.")
    except ValueError:
        return render_seller(listing_error="Please enter valid numbers.")

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    try:
        formatted_price = f"${reserve_price_num:,.2f}"

        cursor.execute('''
            INSERT INTO Auction_Listings 
            (Seller_Email, Category, Auction_Title, Product_Name, Product_Description, 
             Quantity, Reserve_Price, Max_bids, Status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (seller_email, category, auction_title, product_name, product_description,
              quantity_int, formatted_price, max_bids_int))

        new_listing_id = cursor.lastrowid
        conn.commit()

        return render_seller(listing_success=f"Listing created successfully! Listing ID: {new_listing_id}")

    except sql.Error as e:
        conn.rollback()
        print(f"List product DB error: {e}")
        return render_seller(listing_error="A database error occurred.")
    finally:
        conn.close()

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

@app.route('/register', methods=['GET', 'POST'])
def register():
    #show the registration page
    if request.method == 'GET':
        return render_template('register.html')

    #process the registration form
    role = request.form.get('role')
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    age = request.form.get('age')
    major = request.form.get('major', '').strip() or None

    #optional address
    street_num = request.form.get('street_num')
    street_name = request.form.get('street_name', '').strip()
    zipcode = request.form.get('zipcode')

    #seller fields
    bank_routing = request.form.get('bank_routing_number', '').strip()
    bank_account = request.form.get('bank_account_number')

    #validation
    if not email or not password or not first_name or not last_name:
        return render_template('register.html',
                               error="Please fill out all required fields.")

    if password != confirm_password:
        return render_template('register.html',
                               error="Passwords do not match.")

    if len(password) < 6:
        return render_template('register.html',
                               error="Password must be at least 6 characters.")

    if role not in ('bidder', 'seller'):
        return render_template('register.html',
                               error="Invalid account type selected.")

    if role == 'seller' and (not bank_routing or not bank_account):
        return render_template('register.html',
                               error="Sellers must provide banking information.")

    #database
    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    try:
        #email is registered？
        cursor.execute("SELECT email FROM User_Login WHERE email = ?", (email,))
        if cursor.fetchone():
            return render_template('register.html',
                                   error="This email is already registered. Please log in instead.")

        #handle optional address
        home_address_id = None
        if street_num and street_name and zipcode:
            cursor.execute("SELECT zipcode FROM Zipcode_Info WHERE zipcode = ?", (zipcode,))
            if not cursor.fetchone():
                return render_template('register.html',
                                       error=f"Zipcode {zipcode} is not recognized in our system.")

            home_address_id = uuid.uuid4().hex
            cursor.execute('''
                INSERT INTO Address (address_id, zipcode, street_num, street_name)
                VALUES (?, ?, ?, ?)
            ''', (home_address_id, zipcode, street_num, street_name))

        #insert into User_Login
        cursor.execute('''
            INSERT INTO User_Login (email, password_hash)
            VALUES (?, ?)
        ''', (email, hash_password(password)))

        #insert into role-specific tables
        cursor.execute('''
            INSERT INTO Bidders (email, first_name, last_name, age, home_address_id, major)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (email, first_name, last_name, age or None, home_address_id, major))

        #if seller, insert into Sellers
        if role == 'seller':
            cursor.execute('''
                INSERT INTO Sellers (email, bank_routing_number, bank_account_number, balance)
                VALUES (?, ?, ?, 0)
            ''', (email, bank_routing, bank_account))

        conn.commit()

        return render_template('register.html',
                               success=f"Account created successfully as a {role}!")

    except sql.Error as e:
        conn.rollback()
        print(f"Registration database error: {e}")
        return render_template('register.html',
                               error="A database error occurred. Please try again.")
    finally:
        conn.close()

@app.route('/settings')
def settings():
    if 'user_email' not in session:
        return redirect('/')

    user_email = session['user_email']
    account_type_raw = session.get('account_type', '').strip('/')

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    #search card
    cursor.execute('''
        SELECT credit_card_num, card_type, expire_month, expire_year
        FROM Credit_Cards WHERE Owner_email = ?
    ''', (user_email,))
    cards = []
    for row in cursor.fetchall():
        cards.append({
            'credit_card_num': row[0],
            'card_type': row[1].strip(),
            'expire_month': row[2],
            'expire_year': row[3],
            'last_four': row[0].split('-')[-1]  # 只显示后 4 位
        })

    #seller? bank info
    cursor.execute("SELECT bank_routing_number, bank_account_number, balance FROM Sellers WHERE email = ?",
                   (user_email,))
    bank_row = cursor.fetchone()
    is_seller = bank_row is not None

    conn.close()

    return render_template('settings.html',
                           user_email=user_email,
                           account_type=account_type_raw,
                           cards=cards,
                           is_seller=is_seller,
                           bank_routing=bank_row[0] if bank_row else None,
                           bank_account=bank_row[1] if bank_row else None,
                           balance=bank_row[2] if bank_row else None)


@app.route('/settings/add_card', methods=['POST'])
def add_card():
    if 'user_email' not in session:
        return redirect('/')

    email = session['user_email']
    card_num = request.form.get('credit_card_num', '').strip()
    card_type = request.form.get('card_type')
    expire_month = request.form.get('expire_month')
    expire_year = request.form.get('expire_year')
    cvv = request.form.get('security_code')

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT 1 FROM Credit_Cards WHERE credit_card_num = ?", (card_num,))
        if cursor.fetchone():
            flash("This card number is already registered.", "card_error")
            conn.close()
            return redirect('/settings')

        cursor.execute('''
            INSERT INTO Credit_Cards 
            (credit_card_num, card_type, expire_month, expire_year, security_code, Owner_email)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (card_num, card_type, int(expire_month), int(expire_year), int(cvv), email))
        conn.commit()
        flash("Card added successfully!", "card_success")
    except sql.Error as e:
        print(f"Add card error: {e}")
        flash("An error occurred while adding the card.", "card_error")
    finally:
        conn.close()

    return redirect('/settings')


@app.route('/settings/delete_card', methods=['POST'])
def delete_card():
    if 'user_email' not in session:
        return redirect('/')

    email = session['user_email']
    card_num = request.form.get('credit_card_num')

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()
    try:
        #can only delete self card
        cursor.execute("DELETE FROM Credit_Cards WHERE credit_card_num=? AND Owner_email=?",
                       (card_num, email))
        conn.commit()
        flash("Card removed.", "card_success")
    except sql.Error:
        flash("An error occurred.", "card_error")
    finally:
        conn.close()

    return redirect('/settings')


@app.route('/settings/update_bank', methods=['POST'])
def update_bank():
    if 'user_email' not in session:
        return redirect('/')

    email = session['user_email']
    routing = request.form.get('bank_routing_number', '').strip()
    account = request.form.get('bank_account_number')

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM Sellers WHERE email = ?", (email,))
        if not cursor.fetchone():
            flash("Only sellers can update bank info.", "bank_error")
            return redirect('/settings')

        cursor.execute("UPDATE Sellers SET bank_routing_number=?, bank_account_number=? WHERE email=?",
                       (routing, int(account), email))
        conn.commit()
        flash("Bank info updated successfully!", "bank_success")
    except (sql.Error, ValueError) as e:
        print(f"Bank update error: {e}")
        flash("An error occurred.", "bank_error")
    finally:
        conn.close()

    return redirect('/settings')

@app.route('/search')
def search():
    if 'user_email' not in session:
        return redirect('/')

    query = request.args.get('q', '').strip()
    selected_category = request.args.get('category', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    price_type = request.args.get('price_type', 'reserve')  # 默认按起始价筛

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    #every cate
    cursor.execute("SELECT category_name FROM Categories ORDER BY category_name")
    categories = [r[0] for r in cursor.fetchall()]

    params = []
    where_clauses = []    # 普通 WHERE 条件
    having_clauses = []   # 聚合字段的 HAVING 条件

    #keyword
    if query:
        where_clauses.append("(al.Auction_Title LIKE ? OR al.Product_Name LIKE ? OR al.Product_Description LIKE ?)")
        kw = f'%{query}%'
        params.extend([kw, kw, kw])

    #cate
    if selected_category:
        where_clauses.append("al.Category = ?")
        params.append(selected_category)

    #price
    price_expr_reserve = "CAST(REPLACE(REPLACE(al.Reserve_Price, '$', ''), ',', '') AS REAL)"
    price_expr_bid = "COALESCE(MAX(b.Bid_Price), 0)"

    if price_type == 'reserve':
        #reserve price
        if min_price:
            try:
                where_clauses.append(f"{price_expr_reserve} >= ?")
                params.append(float(min_price))
            except ValueError:
                pass
        if max_price:
            try:
                where_clauses.append(f"{price_expr_reserve} <= ?")
                params.append(float(max_price))
            except ValueError:
                pass
    else:
        #current bid
        if min_price:
            try:
                having_clauses.append(f"{price_expr_bid} >= ?")
                params.append(float(min_price))
            except ValueError:
                pass
        if max_price:
            try:
                having_clauses.append(f"{price_expr_bid} <= ?")
                params.append(float(max_price))
            except ValueError:
                pass

    sql_query = '''
        SELECT 
            al.Listing_ID,
            al.Auction_Title,
            al.Product_Name,
            al.Category,
            al.Reserve_Price,
            COUNT(b.Bid_ID) AS bid_count,
            MAX(b.Bid_Price) AS current_bid
        FROM Auction_Listings al
        LEFT JOIN Bids b 
            ON al.Listing_ID = b.Listing_ID 
            AND al.Seller_Email = b.Seller_Email
        WHERE al.Status = 1
    '''

    if where_clauses:
        sql_query += " AND " + " AND ".join(where_clauses)

    sql_query += " GROUP BY al.Listing_ID, al.Seller_Email"

    if having_clauses:
        sql_query += " HAVING " + " AND ".join(having_clauses)

    sql_query += " ORDER BY al.Listing_ID DESC"

    cursor.execute(sql_query, params)

    results = []
    for row in cursor.fetchall():
        results.append({
            'listing_id': row[0],
            'auction_title': row[1],
            'product_name': row[2],
            'category': row[3],
            'reserve_price': row[4],
            'bid_count': row[5],
            'current_bid': row[6]
        })

    conn.close()

    return render_template('search.html',
                           results=results,
                           categories=categories,
                           query=query,
                           selected_category=selected_category,
                           min_price=min_price,
                           max_price=max_price,
                           price_type=price_type,
                           user_email=session.get('user_email'),
                           account_type=session.get('account_type'))

@app.route('/chats')
def chats_list():
    #show all conversations
    if 'user_email' not in session:
        return redirect('/')

    user_email = session['user_email']

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    cursor.execute('''
        SELECT 
            ct.thread_id,
            ct.bidder_email,
            ct.seller_email,
            ct.listing_id,
            al.Product_Name,
            al.Auction_Title,
            COUNT(cm.message_id) AS msg_count,
            MAX(cm.sent_at) AS last_msg_time,
            (SELECT content FROM Chat_Messages 
             WHERE thread_id = ct.thread_id 
             ORDER BY sent_at DESC LIMIT 1) AS last_msg_preview
        FROM Chat_Threads ct
        LEFT JOIN Auction_Listings al 
            ON ct.listing_id = al.Listing_ID AND ct.seller_email = al.Seller_Email
        LEFT JOIN Chat_Messages cm ON ct.thread_id = cm.thread_id
        WHERE ct.bidder_email = ? OR ct.seller_email = ?
        GROUP BY ct.thread_id
        ORDER BY last_msg_time DESC NULLS LAST, ct.created_at DESC
    ''', (user_email, user_email))

    threads = []
    for row in cursor.fetchall():
        threads.append({
            'thread_id': row[0],
            'bidder_email': row[1],
            'seller_email': row[2],
            'listing_id': row[3],
            'product_name': row[4] or '(deleted listing)',
            'auction_title': row[5] or '',
            'msg_count': row[6],
            'last_msg_time': row[7],
            'last_msg_preview': row[8] or 'No messages yet',
            'other_party': row[2] if row[1] == user_email else row[1],
            'i_am_bidder': row[1] == user_email
        })

    conn.close()
    return render_template('chats_list.html',
                           threads=threads,
                           user_email=user_email,
                           account_type=session.get('account_type'))


@app.route('/chat/<int:thread_id>', methods=['GET', 'POST'])
def chat_view(thread_id):
    #singal caht window
    if 'user_email' not in session:
        return redirect('/')

    user_email = session['user_email']

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    #security check
    cursor.execute('''
        SELECT ct.bidder_email, ct.seller_email, ct.listing_id, al.Product_Name, al.Auction_Title
        FROM Chat_Threads ct
        LEFT JOIN Auction_Listings al 
            ON ct.listing_id = al.Listing_ID AND ct.seller_email = al.Seller_Email
        WHERE ct.thread_id = ?
    ''', (thread_id,))
    thread = cursor.fetchone()

    if not thread:
        conn.close()
        return "Chat not found", 404

    bidder_email, seller_email, listing_id, product_name, auction_title = thread

    if user_email not in (bidder_email, seller_email):
        conn.close()
        return "Access denied", 403

    #sending
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if content:
            cursor.execute(
                "INSERT INTO Chat_Messages (thread_id, sender_email, content) VALUES (?, ?, ?)",
                (thread_id, user_email, content)
            )
            conn.commit()

            #notify that guy
            other_party = seller_email if user_email == bidder_email else bidder_email
            try:
                create_notification(
                    other_party,
                    f"New message about '{product_name or 'listing #' + str(listing_id)}'",
                    f"/chat/{thread_id}"
                )
            except Exception as e:
                print(f"Notification error: {e}")

            conn.close()
            return redirect(f'/chat/{thread_id}')

    #load all messages
    cursor.execute('''
        SELECT message_id, sender_email, content, sent_at
        FROM Chat_Messages
        WHERE thread_id = ?
        ORDER BY sent_at ASC, message_id ASC
    ''', (thread_id,))

    messages = []
    for row in cursor.fetchall():
        messages.append({
            'id': row[0],
            'sender': row[1],
            'content': row[2],
            'sent_at': row[3],
            'is_mine': row[1] == user_email
        })

    conn.close()

    other_party = seller_email if user_email == bidder_email else bidder_email
    return render_template('chat_view.html',
                           thread_id=thread_id,
                           messages=messages,
                           other_party=other_party,
                           product_name=product_name or f"Listing #{listing_id}",
                           auction_title=auction_title or '',
                           listing_id=listing_id,
                           user_email=user_email,
                           account_type=session.get('account_type'))


@app.route('/chat/start/<seller_email>/<int:listing_id>', methods=['POST'])
def chat_start(seller_email, listing_id):
    if 'user_email' not in session:
        return redirect('/')

    bidder_email = session['user_email']

    #cant chat with self
    if bidder_email == seller_email:
        flash("You cannot chat with yourself.", "chat_error")
        return redirect('/chats')

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    #exist?
    cursor.execute('''
        SELECT thread_id FROM Chat_Threads
        WHERE bidder_email = ? AND seller_email = ? AND listing_id = ?
    ''', (bidder_email, seller_email, listing_id))
    existing = cursor.fetchone()

    if existing:
        thread_id = existing[0]
    else:
        cursor.execute('''
            INSERT INTO Chat_Threads (bidder_email, seller_email, listing_id)
            VALUES (?, ?, ?)
        ''', (bidder_email, seller_email, listing_id))
        thread_id = cursor.lastrowid
        conn.commit()

    conn.close()
    return redirect(f'/chat/{thread_id}')


@app.route('/chat/delete/<int:thread_id>', methods=['POST'])
def chat_delete(thread_id):
    #delete
    if 'user_email' not in session:
        return redirect('/')

    user_email = session['user_email']

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    #security
    cursor.execute(
        "SELECT 1 FROM Chat_Threads WHERE thread_id = ? AND (bidder_email = ? OR seller_email = ?)",
        (thread_id, user_email, user_email)
    )
    if not cursor.fetchone():
        conn.close()
        return "Access denied", 403

    cursor.execute("DELETE FROM Chat_Messages WHERE thread_id = ?", (thread_id,))
    cursor.execute("DELETE FROM Chat_Threads WHERE thread_id = ?", (thread_id,))
    conn.commit()
    conn.close()
    return redirect('/chats')

if __name__ == '__main__':
    #app.run()
    app.run(debug=True)  #enabled to run with TEMPLATES_AUTO_RELOAD
