from flask import Flask, flash, render_template, request, redirect, url_for, jsonify
from utils import *
import sqlite3 as sql
from routes.auth import auth_bp
from routes.helpdesk import helpdesk_bp
from routes.notif import notif_bp
app = Flask(__name__)
app.register_blueprint(auth_bp)
app.register_blueprint(helpdesk_bp)
app.register_blueprint(notif_bp, url_prefix='/notifications')
with app.app_context():
    init_db()

# Allows HTML pages to be updated by refreshing without having to rerun the code
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Required for session to work
app.secret_key = 'projectTBD_secret_key'

host = 'http://127.0.0.1:5000/'


@app.context_processor
def inject_global_variables():
    """
    Injects variables into all Jinja templates automatically.
    This prevents us from having to pass 'current_user' manually in every render_template().
    """
    global_vars = {
        'current_user': None,
        'unread_notifs_count': 0
    }

    if 'user_email' in session:
        user_email = session['user_email']

        # Inject the user object (for the navbar name)
        global_vars['current_user'] = get_app_user(user_email)

        # Inject unread notifications globally so the bell icon always works!
        try:
            db = db_connect()
            cur = db.cursor()
            cur.execute("SELECT COUNT(*) AS count FROM Notifications WHERE user_email = ? AND is_read = 0",
                        (user_email,))
            global_vars['unread_notifs_count'] = cur.fetchone()['count']
            db.close()
        except Exception:
            pass  # In case DB errors out

    return global_vars

@app.route('/')
def index():
    if 'user_email' in session and 'account_type' in session:
        return redirect(session['account_type'])
    return render_template('login.html')

@app.route('/change_password', methods=['POST'])
def change_password():
    user_email = session['user_email']
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_new_password = request.form.get('confirm_new_password')

    if new_password != confirm_new_password:
        flash("New passwords do not match.", "password_error")
        return redirect('/settings')

    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT password_hash FROM User_Login WHERE email = ?", (user_email,))
        user = cursor.fetchone()
        if user and user[0] == hash_password(current_password):
            cursor.execute("UPDATE User_Login SET password_hash = ? WHERE email = ?", (hash_password(new_password), user_email))
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


@app.route('/bidder')
def bidder():
    if not bidder_only():
        return redirect('/')

    me = session['user_email']
    db = db_connect()
    cur = db.cursor()

    cur.execute("""
                SELECT COUNT(*) AS total
                FROM Credit_Cards
                WHERE Owner_email = ?
                """, (me,))
    card_count = cur.fetchone()['total']

    cur.execute(auction_sql(ending="LIMIT 3"), (me,))
    trending = cur.fetchall()

    my_bids = load_my_bids(cur, me)
    ratings = load_ratings(cur, me)

    db.close()

    return render_template(
        'bidders_home.html',
        mode='home',
        user_email=me,
        query='',
        message=session.pop('bidder_msg', None),
        card_count=card_count,
        trending_listings=trending,
        my_bids=my_bids,
        completed_transactions=ratings,
        current_user=get_app_user(session['user_email']))

@app.route('/auction/<seller_email>/<int:listing_id>')
def auction_detail(seller_email, listing_id):
    if not bidder_only():
        return redirect('/')

    me = session['user_email']
    db = db_connect()
    cur = db.cursor()

    # Check if user has any saved cards
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM Credit_Cards
        WHERE Owner_email = ?
    """, (me,))
    card_count = cur.fetchone()['total']

    # Fetch Auction Details with Seller/Vendor Name support
    cur.execute("""
        SELECT
            a.Listing_ID AS listing_id,
            a.Seller_Email AS seller_email,
            COALESCE(NULLIF(a.Auction_Title, ''), a.Product_Name) AS title,
            a.Product_Name AS product_name,
            a.Product_Description AS description,
            a.Category AS category,
            a.Max_bids AS max_bids,
            a.Reserve_Price AS reserve_price,
            a.Status AS status_code,
            -- Logic to determine Seller Name vs Business Name 
            COALESCE(lv.Business_Name, bdr.first_name || ' ' || bdr.last_name) AS seller_name,
            (
                SELECT COALESCE(MAX(b.Bid_Price), 0)
                FROM Bids b
                WHERE b.Seller_Email = a.Seller_Email
                  AND b.Listing_ID = a.Listing_ID
            ) AS current_bid,
            (
                SELECT COUNT(*)
                FROM Bids b
                WHERE b.Seller_Email = a.Seller_Email
                  AND b.Listing_ID = a.Listing_ID
            ) AS bid_count,
            (
                SELECT COALESCE(MAX(b.Bid_Price), 0) + 1
                FROM Bids b
                WHERE b.Seller_Email = a.Seller_Email
                  AND b.Listing_ID = a.Listing_ID
            ) AS min_bid,
            (
                SELECT ROUND(AVG(r.Rating), 1)
                FROM Ratings r
                WHERE r.Seller_Email = a.Seller_Email
            ) AS seller_rating,
            (
                SELECT COUNT(*)
                FROM Ratings r
                WHERE r.Seller_Email = a.Seller_Email
            ) AS rating_count
        FROM Auction_Listings a
        LEFT JOIN Local_Vendors lv ON a.Seller_Email = lv.Email 
        LEFT JOIN Bidders bdr ON a.Seller_Email = bdr.email 
        WHERE a.Listing_ID = ? AND a.Seller_Email = ? 
    """, (listing_id, seller_email))
    item = cur.fetchone()

    if item is None:
        db.close()
        bidder_msg('danger', 'Auction not found.')
        return redirect(url_for('bidder'))

    # Fetch Bid History
    cur.execute("""
        SELECT Bidder_Email AS bidder_email, Bid_Price AS bid_price
        FROM Bids
        WHERE Seller_Email = ?
          AND Listing_ID = ?
        ORDER BY Bid_Price DESC, Bid_ID ASC
        LIMIT 10
    """, (seller_email, listing_id))
    bid_history = cur.fetchall()

    # Fetch the current user's highest bid for this item
    cur.execute("""
        SELECT MAX(Bid_Price) AS my_bid
        FROM Bids
        WHERE Seller_Email = ?
          AND Listing_ID = ?
          AND Bidder_Email = ?
    """, (seller_email, listing_id, me))
    my_bid = cur.fetchone()['my_bid']

    # Check Watchlist status
    cur.execute("""
        SELECT 1
        FROM Watchlist
        WHERE Bidder_Email = ?
          AND Listing_ID = ?
          AND Seller_Email = ?
    """, (me, listing_id, seller_email))
    is_watching = bool(cur.fetchone())

    # Check if a transaction exists (Uses Buyer_Email from schema)
    cur.execute("""
        SELECT 1
        FROM Transactions
        WHERE Listing_ID = ? 
          AND Seller_Email = ? 
          AND Bidder_Email = ?
    """, (listing_id, seller_email, me))
    has_paid = bool(cur.fetchone())

    db.close()

    return render_template(
        'auction_detail.html',
        user_email=me,
        item=item,
        bids=bid_history,
        my_bid=my_bid,
        card_count=card_count,
        is_watching=is_watching,
        has_paid=has_paid,
        message=session.pop('bidder_msg', None)
    )

@app.route('/place_bid', methods=['POST'])
def place_bid():
    if not bidder_only():
        return redirect('/')

    me = session['user_email']
    listing_id = request.form.get('listing_id', type=int)
    seller_email_input = request.form.get('seller_email')

    try:
        price = int(request.form.get('bid_price', ''))
    except ValueError:
        bidder_msg('danger', 'Please enter a valid whole-dollar bid.')
        return redirect(url_for('auction_detail', seller_email=seller_email_input, listing_id=listing_id))

    db = db_connect()
    cur = db.cursor()

    try:
        cur.execute("""
                    SELECT Seller_Email,
                           Status,
                           Max_bids,
                           Reserve_Price,
                           COALESCE(NULLIF(Auction_Title, ''), Product_Name) as title
                    FROM Auction_Listings
                    WHERE Listing_ID = ?
                      AND Seller_Email = ?
                    """, (listing_id, seller_email_input))
        item = cur.fetchone()

        if not item or item['Status'] != 1:
            bidder_msg('danger', 'Auction not active.')
            return redirect(url_for('bidder'))

        seller = item['Seller_Email']
        max_allowed = item['Max_bids']
        title = item['title']
        detail_url = url_for('auction_detail', seller_email=seller, listing_id=listing_id)

        # Check for Previous High Bidder
        cur.execute("""
                    SELECT Bidder_Email
                    FROM Bids
                    WHERE Listing_ID = ?
                      AND Seller_Email = ?
                    ORDER BY Bid_Price DESC, Bid_ID DESC
                    LIMIT 1
                    """, (listing_id, seller))
        prev_row = cur.fetchone()
        prev_high_bidder = prev_row['Bidder_Email'] if prev_row else None

        # CONSECUTIVE BID CHECK
        if prev_high_bidder == me:
            bidder_msg('danger', 'You are already the highest bidder. You must wait for another bidder before bidding again.')
            return redirect(detail_url)

        # Enforce the $1 increment rule
        cur.execute("""
                    SELECT COALESCE(MAX(Bid_Price), 0) + 1 AS needed
                    FROM Bids
                    WHERE Seller_Email = ?
                      AND Listing_ID = ?
                    """, (seller, listing_id))
        needed = cur.fetchone()['needed']

        if price < needed:
            bidder_msg('danger', f'Your bid must be at least ${needed}.')
            return redirect(detail_url)

        cur.execute("""
                    INSERT INTO Bids (Seller_Email, Listing_ID, Bidder_Email, Bid_Price)
                    VALUES (?, ?, ?, ?)
                    """, (seller, listing_id, me, price))

        auction_ended = False
        reserve_met = False

        cur.execute("SELECT COUNT(*) as cnt FROM Bids WHERE Listing_ID=? AND Seller_Email=?", (listing_id, seller))
        if cur.fetchone()['cnt'] >= max_allowed:
            auction_ended = True

            try:
                # Handle cases where reserve might be stored as a string with symbols
                res_clean = str(item['Reserve_Price']).replace('$', '').replace(',', '')
                res_val = float(res_clean)
            except:
                res_val = 0.0

            if price >= res_val:
                reserve_met = True
                cur.execute("UPDATE Auction_Listings SET Status = 2 WHERE Listing_ID = ? AND Seller_Email = ?",
                            (listing_id, seller))
            else:
                cur.execute("UPDATE Auction_Listings SET Status = 0 WHERE Listing_ID = ? AND Seller_Email = ?",
                            (listing_id, seller))
        db.commit()

        # TRIGGER NOTIFICATIONS
        # Notify Watchers
        cur.execute("SELECT Bidder_Email FROM Watchlist WHERE Listing_ID=? AND Seller_Email=?", (listing_id, seller))
        watchers = [row['Bidder_Email'] for row in cur.fetchall()]
        for watcher in watchers:
            if watcher != me:
                create_notification(watcher, f"New bid on '{title}': ${price}", detail_url)
            if auction_ended:
                create_notification(watcher, f"Auction for '{title}' is now closed.", detail_url)

        # Notify Previous Bidder (The one just outbid)
        if prev_high_bidder and prev_high_bidder != me:
            create_notification(prev_high_bidder, f"You were outbid on '{title}'! Current bid: ${price}.", detail_url)

        if auction_ended:
            # Notify Seller
            if reserve_met:
                create_notification(seller, f"SOLD! '{title}' hit max bids and met reserve. Sold to {me} for ${price}.",
                                    url_for('seller'))
                # Inform Bidder Reserve Met
                create_notification(me, f"You won '{title}'! Your bid of ${price} met the reserve price.", detail_url)
            else:
                create_notification(seller,
                                    f"Auction Ended: '{title}' reached max bids but did NOT meet reserve. High bid: ${price}.",
                                    url_for('seller'))
                # Inform Bidder Reserve Not Met
                create_notification(me,
                                    f"Auction ended for '{title}'. Your bid of ${price} did not meet the reserve price.",
                                    detail_url)

            # Notify Other Participants
            cur.execute("SELECT DISTINCT Bidder_Email FROM Bids WHERE Listing_ID=? AND Seller_Email=?",
                        (listing_id, seller))
            for p in cur.fetchall():
                p_email = p['Bidder_Email']
                if p_email not in [me, seller]:
                    create_notification(p_email, f"The auction for '{title}' has ended.", detail_url)

        bidder_msg('success', 'Bid placed successfully.')

    except Exception as e:
        db.rollback()
        print(f"Bidding Error: {e}")
        bidder_msg('danger', 'A database error occurred.')
    finally:
        db.close()

    return redirect(url_for('auction_detail', seller_email=seller_email_input, listing_id=listing_id))
@app.route('/submit_rating', methods=['POST'])
def submit_rating():
    if not bidder_only():
        return redirect('/')

    me = session['user_email']
    seller = request.form.get('seller_email')
    listing_id = request.form.get('listing_id', type=int)
    stars = request.form.get('rating', type=int)
    note = request.form.get('rating_desc', '').strip()

    db = db_connect()
    cur = db.cursor()

    try:
        # Verify payment exists
        cur.execute("""
                    SELECT 1
                    FROM Transactions
                    WHERE Seller_Email = ?
                      AND Listing_ID = ?
                      AND Bidder_Email = ?
                    """, (seller, listing_id, me))

        if not cur.fetchone():
            bidder_msg('danger', 'You must complete payment before rating.')
            return redirect(url_for('auction_detail', seller_email=seller, listing_id=listing_id))

        # Check if this specific listing has already been rated by this bidder
        cur.execute("""
                    SELECT 1
                    FROM Ratings
                    WHERE Bidder_Email = ?
                      AND Listing_ID = ?
                    """, (me, listing_id))

        if cur.fetchone():
            bidder_msg('warning', 'You have already rated this transaction.')
        else:
            # Insert rating with Listing_ID to keep track
            cur.execute("""
                        INSERT INTO Ratings (Bidder_Email, Seller_Email, Listing_ID, Date, Rating, Rating_Desc)
                        VALUES (?, ?, ?, date('now'), ?, ?)
                        """, (me, seller, listing_id, stars, note or None))
            db.commit()
            bidder_msg('success', 'Rating submitted! Thanks for the feedback.')

    except Exception as e:
        db.rollback()
        print("Rating Error:", e)
        bidder_msg('danger', 'Database error while saving rating.')
    finally:
        db.close()

    return redirect(url_for('auction_detail', seller_email=seller, listing_id=listing_id))

@app.route('/seller')
def seller():
    if 'user_email' not in session or session.get('account_type') != '/seller':
        return redirect('/')

    seller_email = session['user_email']
    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()

    # Skip the 'Root' root node and fetch its direct children for the starting dropdown
    cursor.execute('''
        SELECT category_name 
        FROM Categories 
        WHERE parent_category = 'Root' 
        ORDER BY category_name
    ''')
    top_categories = [r[0] for r in cursor.fetchall() if r[0]]

    cursor.execute(
        '''
        SELECT al.Listing_ID,
               al.Auction_Title,
               al.Product_Name,
               al.Category,
               al.Reserve_Price,
               al.Max_bids,
               al.Status,
               COUNT(b.Bid_ID)  AS bid_count,
               MAX(b.Bid_Price) AS current_bid
        FROM Auction_Listings al
                 LEFT JOIN Bids b ON al.Listing_ID = b.Listing_ID AND al.Seller_Email = b.Seller_Email
        WHERE al.Seller_Email = ?
        GROUP BY al.Listing_ID
        ORDER BY al.Status DESC, al.Listing_ID DESC
        ''',
        (seller_email,),
    )

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
            'current_bid': row[8],
        })

    conn.close()

    return render_template(
        'seller_home.html',
        top_categories=top_categories,
        my_listings=my_listings,
        current_user=get_app_user(session['user_email']),
    )


@app.route('/list_product', methods=['POST'])
def list_product():
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
        conn = sql.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT category_name FROM Categories ORDER BY category_name")
        cats = [row[0] for row in cursor.fetchall()]
        conn.close()
        return render_template(
            'seller_home.html',
            categories=cats,
            my_listings=[],
            current_user=get_app_user(session['user_email']),
            **kwargs,
        )

    if not all([auction_title, product_name, product_description, category, reserve_price, quantity, max_bids]):
        return render_seller(listing_error="Please fill out all required fields.")

    try:
        reserve_price_num = float(reserve_price)
        quantity_int = int(quantity)
        max_bids_int = int(max_bids)
        if reserve_price_num < 0 or quantity_int < 1 or max_bids_int < 1:
            return render_seller(listing_error="Numeric fields must be positive.")
    except ValueError:
        return render_seller(listing_error="Please enter valid numbers.")

    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        formatted_price = f"${reserve_price_num:,.2f}"

        # FIX: Manually calculate the next Listing_ID for this specific seller
        cursor.execute("SELECT COALESCE(MAX(Listing_ID), 0) + 1 FROM Auction_Listings WHERE Seller_Email = ?",
                       (seller_email,))
        new_listing_id = cursor.fetchone()[0]

        cursor.execute(
            '''
            INSERT INTO Auction_Listings
            (Listing_ID, Seller_Email, Category, Auction_Title, Product_Name, Product_Description,
             Quantity, Reserve_Price, Max_bids, Status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''',
            (new_listing_id, seller_email, category, auction_title, product_name, product_description, quantity_int,
             formatted_price, max_bids_int),
        )
        conn.commit()
        return render_seller(listing_success=f"Listing created successfully! Listing ID: {new_listing_id}")
    except sql.Error as e:
        conn.rollback()
        print(f"List product DB error: {e}")
        return render_seller(listing_error="A database error occurred.")
    finally:
        conn.close()

@app.route('/checkout/<seller_email>/<int:listing_id>')
def checkout(seller_email, listing_id):
    if not bidder_only():
        return redirect('/')

    me = session['user_email']
    db = db_connect()
    cur = db.cursor()

    # Fetch Auction Item
    cur.execute("""
        SELECT
            a.Listing_ID AS listing_id,
            a.Seller_Email AS seller_email,
            COALESCE(NULLIF(a.Auction_Title, ''), a.Product_Name) AS title,
            a.Product_Name AS product_name,
            a.Status AS status_code
        FROM Auction_Listings a
        WHERE a.Listing_ID = ? AND a.Seller_Email = ?
    """, (listing_id, seller_email))
    item = cur.fetchone()

    # Ensure the auction is actually closed/sold (Status 2)
    if not item or item['status_code'] != 2:
        db.close()
        bidder_msg('danger', 'This auction is not ready for checkout.')
        return redirect(url_for('bidder'))

    # 2. Verify User is the Winner and Get Amount Due
    cur.execute("""
        SELECT Bidder_Email, Bid_Price
        FROM Bids
        WHERE Listing_ID = ? AND Seller_Email = ?
        ORDER BY Bid_Price DESC LIMIT 1
    """, (listing_id, seller_email))
    winning_bid = cur.fetchone()

    if not winning_bid or winning_bid['Bidder_Email'] != me:
        db.close()
        bidder_msg('danger', 'You are not the winning bidder for this auction.')
        return redirect(url_for('auction_detail', listing_id=listing_id))

    amount_due = winning_bid['Bid_Price']

    # Check if payment was already made (Transaction already exists)
    cur.execute("""
        SELECT 1 FROM Transactions
        WHERE Listing_ID = ? AND Seller_Email = ? AND Bidder_Email = ?
    """, (listing_id, seller_email, me))
    if cur.fetchone():
        db.close()
        bidder_msg('info', 'You have already paid for this item.')
        return redirect(url_for('auction_detail', listing_id=listing_id))

    # Fetch User's Credit Cards
    # A credit card is owned by one bidder only
    cur.execute("""
        SELECT credit_card_num, card_type, expire_month, expire_year
        FROM Credit_Cards
        WHERE Owner_email = ?
    """, (me,))
    cards = []
    for row in cur.fetchall():
        cards.append({
            'credit_card_num': row['credit_card_num'],
            'card_type': row['card_type'].strip(),
            'expire_month': row['expire_month'],
            'expire_year': row['expire_year'],
            'last_four': row['credit_card_num'][-4:]
        })

    db.close()

    return render_template(
        'checkout.html',
        item=item,
        amount_due=amount_due,
        cards=cards,
        message=session.pop('bidder_msg', None)
    )


@app.route('/process_payment', methods=['POST'])
def process_payment():
    if not bidder_only():
        return redirect('/')

    me = session['user_email']
    listing_id = request.form.get('listing_id', type=int)
    seller_email = request.form.get('seller_email')
    amount_due = request.form.get('payment_amount', type=float)
    selected_card = request.form.get('selected_card')

    db = db_connect()
    cur = db.cursor()

    try:
        # Handle "New Card" entry
        if selected_card == 'new':
            card_type = request.form.get('card_type')
            cc_num = request.form.get('credit_card_num')
            exp_m = request.form.get('expire_month')
            exp_y = request.form.get('expire_year')
            cvv = request.form.get('security_code')

            # Insert the new card into the database first
            cur.execute("""
                        INSERT INTO Credit_Cards (credit_card_num, card_type, expire_month, expire_year, security_code,
                                                  Owner_email)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """, (cc_num, card_type, exp_m, exp_y, cvv, me))

            # Use this new card for the transaction
            selected_card = cc_num
        else:
            # Existing logic: Verify the selected saved card belongs to the user
            cur.execute("""
                        SELECT 1
                        FROM Credit_Cards
                        WHERE credit_card_num = ?
                          AND Owner_email = ?
                        """, (selected_card, me))

            if not cur.fetchone():
                bidder_msg('danger', 'Invalid payment method selected.')
                return redirect(url_for('checkout', seller_email=seller_email, listing_id=listing_id))

        # Process Transaction
        cur.execute("""
                    INSERT INTO Transactions (Seller_Email, Listing_ID, Bidder_Email, Date, Payment)
                    VALUES (?, ?, ?, date('now'), ?)
                    """, (seller_email, listing_id, me, amount_due))

        db.commit()
        bidder_msg('success', 'Payment successful! Transaction complete.')
        create_notification(seller_email, f"Payment of ${amount_due} received from {me} for listing #{listing_id}.",
                            url_for('seller'))

    except Exception as e:
        db.rollback()
        print(f"Payment Error: {e}")
        bidder_msg('danger', 'A database error occurred during payment.')
    finally:
        db.close()

    # FIX: Added seller_email to the redirect
    return redirect(url_for('auction_detail', seller_email=seller_email, listing_id=listing_id))
@app.route('/contact')
def contact():
    if 'user_email' not in session:
        return redirect('/')

    # Check if the URL has ?tab=category
    is_category = request.args.get('tab') == 'category'

    return render_template('contact.html', is_category=is_category)

@app.route('/toggle_watchlist', methods=['POST'])
def toggle_watchlist():
    if 'user_email' not in session or session.get('account_type') != '/bidder':
        flash("You must be logged in as a bidder to use the watchlist.", "auth_error")
        return redirect(url_for('index'))

    bidder_email = session['user_email']
    listing_id = request.form.get('listing_id')
    seller_email = request.form.get('seller_email')

    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''
            SELECT 1
            FROM Watchlist
            WHERE Bidder_Email = ?
              AND Listing_ID = ?
            ''',
            (bidder_email, listing_id),
        )

        if cursor.fetchone():
            cursor.execute(
                '''
                DELETE FROM Watchlist
                WHERE Bidder_Email = ?
                  AND Listing_ID = ?
                ''',
                (bidder_email, listing_id),
            )
            flash("Listing removed from your watchlist.", "watch_success")
        else:
            cursor.execute(
                '''
                INSERT INTO Watchlist (Bidder_Email, Listing_ID, Seller_Email)
                VALUES (?, ?, ?)
                ''',
                (bidder_email, listing_id, seller_email),
            )
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
    if not bidder_only():
        return redirect('/')

    me = session['user_email']
    db = db_connect()
    cur = db.cursor()

    try:
        # Fetch watched listings with seller identity and bid progress
        cur.execute("""
            SELECT a.Listing_ID                                          AS listing_id,
                   a.Seller_Email                                        AS seller_email,
                   COALESCE(NULLIF(a.Auction_Title, ''), a.Product_Name) AS title,
                   a.Product_Name                                        AS product_name,
                   a.Category                                            AS category,
                   a.Status                                              AS status_code,
                   a.Max_bids                                            AS max_bids,
                   COALESCE(MAX(b.Bid_Price), 0)                         AS current_bid,
                   COUNT(b.Bid_ID)                                       AS bid_count,
                   -- Determine if seller is a Local Vendor or Individual Bidder
                   COALESCE(lv.Business_Name, bdr.first_name || ' ' || bdr.last_name) AS seller_name
            FROM Auction_Listings a
                     JOIN Watchlist w
                          ON a.Listing_ID = w.Listing_ID
                              AND a.Seller_Email = w.Seller_Email
                     LEFT JOIN Bids b
                               ON b.Listing_ID = a.Listing_ID
                                   AND b.Seller_Email = a.Seller_Email
                     LEFT JOIN Local_Vendors lv 
                               ON a.Seller_Email = lv.Email
                     LEFT JOIN Bidders bdr 
                               ON a.Seller_Email = bdr.email
            WHERE w.Bidder_Email = ?
            GROUP BY a.Listing_ID, a.Seller_Email, a.Auction_Title,
                     a.Product_Name, a.Category, a.Status, a.Max_bids,
                     lv.Business_Name, bdr.first_name, bdr.last_name
            ORDER BY a.Status = 1 DESC, a.Listing_ID DESC
        """, (me,))

        watched_items = cur.fetchall()

        # Added: Fetch unread notifications for the navbar badge
        cur.execute("SELECT COUNT(*) AS count FROM Notifications WHERE user_email = ? AND is_read = 0", (me,))
        unread_count = cur.fetchone()['count']

    except sql.Error as e:
        print(f"Database error fetching watchlist: {e}")
        watched_items = []
        unread_count = 0
        flash("An error occurred while loading your watchlist.", "watch_error")

    finally:
        db.close()

    return render_template(
        'watchlist.html',
        watchlist=watched_items,
        unread_notifs_count=unread_count
    )

@app.route('/settings')
def settings():
    if 'user_email' not in session:
        return redirect('/')

    user_email = session['user_email']
    account_type_raw = session.get('account_type', '').strip('/')

    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT credit_card_num, card_type, expire_month, expire_year
        FROM Credit_Cards WHERE Owner_email = ?
        ''',
        (user_email,),
    )
    cards = []
    for row in cursor.fetchall():
        cards.append({
            'credit_card_num': row[0],
            'card_type': row[1].strip(),
            'expire_month': row[2],
            'expire_year': row[3],
            'last_four': row[0].split('-')[-1],
        })

    cursor.execute("SELECT bank_routing_number, bank_account_number, balance FROM Sellers WHERE email = ?", (user_email,))
    bank_row = cursor.fetchone()
    is_seller = bank_row is not None

    conn.close()
    return render_template(
        'settings.html',
        user_email=user_email,
        account_type=account_type_raw,
        cards=cards,
        is_seller=is_seller,
        bank_routing=bank_row[0] if bank_row else None,
        bank_account=bank_row[1] if bank_row else None,
        balance=bank_row[2] if bank_row else None,
    )


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

    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM Credit_Cards WHERE credit_card_num = ?", (card_num,))
        if cursor.fetchone():
            flash("This card number is already registered.", "card_error")
            conn.close()
            return redirect('/settings')

        cursor.execute(
            '''
            INSERT INTO Credit_Cards
            (credit_card_num, card_type, expire_month, expire_year, security_code, Owner_email)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (card_num, card_type, int(expire_month), int(expire_year), int(cvv), email),
        )
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

    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Credit_Cards WHERE credit_card_num=? AND Owner_email=?", (card_num, email))
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

    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM Sellers WHERE email = ?", (email,))
        if not cursor.fetchone():
            flash("Only sellers can update bank info.", "bank_error")
            return redirect('/settings')

        cursor.execute("UPDATE Sellers SET bank_routing_number=?, bank_account_number=? WHERE email=?", (routing, int(account), email))
        conn.commit()
        flash("Bank info updated successfully!", "bank_success")
    except (sql.Error, ValueError) as e:
        print(f"Bank update error: {e}")
        flash("An error occurred.", "bank_error")
    finally:
        conn.close()

    return redirect('/settings')


@app.route('/get_subcategories')
def get_subcategories():
    parent = request.args.get('parent')

    if not parent:
        return jsonify({"subcategories": []})

    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()

    # Query ONLY the direct children of the requested parent
    cursor.execute("SELECT category_name FROM Categories WHERE parent_category = ?", (parent,))
    subcategories = [row[0] for row in cursor.fetchall()]
    conn.close()

    return jsonify({"subcategories": subcategories})

@app.route('/search')
def search():
    if 'user_email' not in session:
        return redirect('/')

    query = request.args.get('q', '').strip()
    selected_category = request.args.get('category', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    price_type = request.args.get('price_type', 'reserve')

    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()

    # Fetch top-level categories
    cursor.execute('''
                   SELECT category_name
                   FROM Categories
                   WHERE parent_category = 'Root'
                   ORDER BY category_name
                   ''')
    top_categories = [r[0] for r in cursor.fetchall() if r[0]]

    params = []
    where_clauses = []
    having_clauses = []
    breadcrumbs = []

    # Keyword Filter: Title, Product Name, Description, or Seller Name
    if query:
        # Search listing details and seller names (Business Name or First/Last Name)
        where_clauses.append("""
            (al.Auction_Title LIKE ? 
             OR al.Product_Name LIKE ? 
             OR al.Product_Description LIKE ? 
             OR lv.Business_Name LIKE ? 
             OR bdr.first_name LIKE ? 
             OR bdr.last_name LIKE ?)
        """)
        kw = f'%{query}%'
        params.extend([kw, kw, kw, kw, kw, kw])

    # Category Filter with Recursive Lookup
    if selected_category:
        current_node = selected_category
        while current_node:
            breadcrumbs.insert(0, current_node)
            cursor.execute("SELECT parent_category FROM Categories WHERE category_name = ?", (current_node,))
            row = cursor.fetchone()
            current_node = row[0] if row and row[0] else None

        descendants = [selected_category]
        categories_to_check = [selected_category]
        while categories_to_check:
            current = categories_to_check.pop(0)
            cursor.execute("SELECT category_name FROM Categories WHERE parent_category = ?", (current,))
            children = [row[0] for row in cursor.fetchall()]
            descendants.extend(children)
            categories_to_check.extend(children)

        placeholders = ', '.join(['?'] * len(descendants))
        where_clauses.append(f"al.Category IN ({placeholders})")
        params.extend(descendants)

    # Price Filter Logic
    price_expr_reserve = "CAST(REPLACE(REPLACE(al.Reserve_Price, '$', ''), ',', '') AS REAL)"
    price_expr_bid = "COALESCE(MAX(b.Bid_Price), 0)"

    if price_type == 'reserve':
        if min_price:
            where_clauses.append(f"{price_expr_reserve} >= ?")
            params.append(float(min_price))
        if max_price:
            where_clauses.append(f"{price_expr_reserve} <= ?")
            params.append(float(max_price))
    else:
        if min_price:
            having_clauses.append(f"{price_expr_bid} >= ?")
            params.append(float(min_price))
        if max_price:
            having_clauses.append(f"{price_expr_bid} <= ?")
            params.append(float(max_price))

    # Joining Local_Vendors and Bidders to get seller identity
    sql_query = '''
                SELECT al.Listing_ID, 
                       al.Seller_Email, 
                       al.Auction_Title, 
                       al.Product_Name, 
                       al.Category, 
                       al.Reserve_Price, 
                       COUNT(b.Bid_ID)  AS bid_count, 
                       MAX(b.Bid_Price) AS current_bid,
                       COALESCE(lv.Business_Name, bdr.first_name || ' ' || bdr.last_name) AS seller_name
                FROM Auction_Listings al
                         LEFT JOIN Local_Vendors lv ON al.Seller_Email = lv.Email
                         LEFT JOIN Bidders bdr ON al.Seller_Email = bdr.email
                         LEFT JOIN Bids b
                                   ON al.Listing_ID = b.Listing_ID
                                       AND al.Seller_Email = b.Seller_Email
                WHERE al.Status = 1 
                '''

    if where_clauses:
        sql_query += " AND " + " AND ".join(where_clauses)

    sql_query += " GROUP BY al.Listing_ID, al.Seller_Email, lv.Business_Name, bdr.first_name, bdr.last_name"

    if having_clauses:
        sql_query += " HAVING " + " AND ".join(having_clauses)

    sql_query += " ORDER BY al.Listing_ID DESC"

    cursor.execute(sql_query, params)

    results = []
    for row in cursor.fetchall():
        results.append({
            'listing_id': row[0],
            'seller_email': row[1],
            'auction_title': row[2],
            'product_name': row[3],
            'category': row[4],
            'reserve_price': row[5],
            'bid_count': row[6],
            'current_bid': row[7],
            'seller_name': row[8]
        })

    conn.close()

    return render_template('search.html',
                           results=results,
                           top_categories=top_categories,
                           breadcrumbs=breadcrumbs,
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

    conn = sql.connect(DB_NAME)
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

    conn = sql.connect(DB_NAME)
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

    conn = sql.connect(DB_NAME)
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

    conn = sql.connect(DB_NAME)
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
    app.run(debug=True)  #enabled to run with TEMPLATES_AUTO_RELOAD
