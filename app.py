from flask import Flask, flash, render_template, request, redirect, session, url_for
import sqlite3 as sql
import hashlib
import uuid
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

    if new_password != confirm_new_password:
        flash("New passwords do not match.", "password_error")
        return redirect('/settings')

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
            flash("Your password has been updated successfully.", "password_success")
        else:
            flash("Incorrect current password.", "password_error")

    except sql.Error as e:
        print(f"Database error: {e}")
        flash("An error occurred while updating your password.", "password_error")
    finally:
        conn.close()

    return redirect('/settings')

def db_connect():
    db = sql.connect("dataset_tables.db")
    db.row_factory = sql.Row
    return db


def bidder_only():
    return 'user_email' in session and session.get('account_type') == '/bidder'

@app.route('/bidder')
def bidder():
    if not bidder_only():
        return redirect('/')
    # TODO: auction logic
    return None


@app.route('/bidder/search')
def bidder_search():
   #TODO
   return


@app.route('/auction/<int:listing_id>')
def auction_detail(listing_id):
    #TODO: implement

    """
    Return something like this:
    return render_template(
        'auction_detail.html',
        user_email=me,
        item=item,
        bids=bid_history,
        my_bid=my_bid,
        card_count=card_count,
        is_watching=is_watching,
        message=session.pop('bidder_msg', None)
    )
    """
    return


@app.route('/place_bid', methods=['POST'])
def place_bid():
   #TODO: implement
   listing_id = "123"
   return redirect(url_for('auction_detail', listing_id=listing_id))


@app.route('/submit_rating', methods=['POST'])
def submit_rating():
    #TODO: implement
    return redirect(url_for('bidder') + '#ratings')
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


@app.route('/contact')
def contact():
    if 'user_email' not in session:
        return redirect('/')

    # Check if the URL has ?tab=category
    is_category = request.args.get('tab') == 'category'

    return render_template('contact.html', is_category=is_category)

@app.route('/submit_ticket', methods=['POST'])
def submit_ticket():
    if 'user_email' not in session:
        return redirect('/')

    sender_email = session['user_email']
    req_type = request.form.get('request_type')

    initial_status = 0
    # Per schema: initially assign to pseudo staff
    assigned_staff_email = 'helpdeskteam@lsu.edu'

    # Handle the difference between the two HTML forms right here in Python
    if req_type == 'AddCategory':
        cat_name = request.form.get('cat_name')
        cat_reason = request.form.get('cat_reason')

        if not cat_name or not cat_reason:
            return render_template('contact.html', is_category=True,
                                   helpdesk_req_error="Please fill out all category fields.")

        # Format the description string for the database
        req_desc = f"Requested Category: {cat_name}\nReason: {cat_reason}"
        is_category_form = True  # Used to re-render the correct tab on failure/success

    else:
        req_desc = request.form.get('request_desc')
        is_category_form = False

        if not req_type or not req_desc:
            return render_template('contact.html', is_category=False,
                                   helpdesk_req_error="Please fill out all helpdesk fields.")

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    try:
        # Insert the ticket with the pseudo staff assignment
        cursor.execute('''
                       INSERT INTO Requests (sender_email, helpdesk_staff_email, request_type, request_desc,
                                             request_status)
                       VALUES (?, ?, ?, ?, ?)
                       ''', (sender_email, assigned_staff_email, req_type, req_desc, initial_status))

        conn.commit()
        return render_template('contact.html', is_category=is_category_form,
                               helpdesk_req_success="Your request has been submitted successfully!")

    except sql.Error as e:
        print(f"Database error: {e}")
        return render_template('contact.html', is_category=is_category_form,
                               helpdesk_req_error="An error occurred while submitting your request.")
    finally:
        conn.close()
@app.route('/helpdesk')
def helpdesk():
    return render_template('helpdesk_home.html')

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

    return redirect(request.referrer or url_for('bidder'))


@app.route('/watchlist')
def watchlist():
    # Only logged-in bidders can view this page
    if not bidder_only():
        return redirect('/')

    me = session['user_email']
    db = db_connect()
    cur = db.cursor()

    try:
        # Fetch all watched listings and calculate their current bid/count
        cur.execute("""
                    SELECT a.Listing_ID                                          AS listing_id,
                           a.Seller_Email                                        AS seller_email,
                           COALESCE(NULLIF(a.Auction_Title, ''), a.Product_Name) AS title,
                           a.Product_Name                                        AS product_name,
                           a.Category                                            AS category,
                           a.Status                                              AS status_code,
                           COALESCE(MAX(b.Bid_Price), 0)                         AS current_bid,
                           COUNT(b.Bid_Price)                                    AS bid_count
                    FROM Auction_Listings a
                             JOIN Watchlist w
                                  ON a.Listing_ID = w.Listing_ID
                             LEFT JOIN Bids b
                                       ON b.Listing_ID = a.Listing_ID
                                           AND b.Seller_Email = a.Seller_Email
                    WHERE w.Bidder_Email = ?
                    GROUP BY a.Listing_ID, a.Seller_Email, a.Auction_Title,
                             a.Product_Name, a.Category, a.Status
                    ORDER BY a.Status = 1 DESC, a.Listing_ID DESC
                    """, (me,))

        watched_items = cur.fetchall()

    except sql.Error as e:
        print(f"Database error fetching watchlist: {e}")
        watched_items = []
        flash("An error occurred while loading your watchlist.", "watch_error")

    finally:
        db.close()

    # 3. Pass the data to the template
    return render_template('watchlist.html', watchlist=watched_items)

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

if __name__ == '__main__':
    #app.run()
    app.run(debug=True)  #enabled to run with TEMPLATES_AUTO_RELOAD
