import hashlib
import sqlite3 as sql
import zipfile
import io
import os
import csv
from xml.sax.saxutils import escape
from flask import session

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "dataset_tables.db")
DEFAULT_HELPDESK_EMAIL = "helpdeskteam@lsu.edu"
REQUEST_STATUS = {
    0: "Open",
    1: "In Progress",
    2: "Closed",
}
REQUEST_STATUS_VALUE = {label: value for value, label in REQUEST_STATUS.items()}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = sql.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS Notifications
                   (
                       notification_id Integer PRIMARY KEY AUTOINCREMENT,
                       user_email      TEXT    NOT NULL,
                       content         TEXT    NOT NULL,
                       link            TEXT,
                       is_read         INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0, 1)),
                       created_at      TIMESTAMP        DEFAULT CURRENT_TIMESTAMP,
                       FOREIGN KEY (user_email) REFERENCES User_Login (email)
                   )
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS Watchlist
                   (
                       Bidder_Email TEXT    NOT NULL,
                       Listing_ID   INTEGER NOT NULL,
                       Seller_Email TEXT    NOT NULL,
                       PRIMARY KEY (Bidder_Email, Listing_ID),
                       FOREIGN KEY (Bidder_Email) REFERENCES Bidders (email),
                       FOREIGN KEY (Listing_ID) REFERENCES Auction_Listings (Listing_ID)
                   )
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS Ratings
                   (
                       Rating_ID    INTEGER PRIMARY KEY AUTOINCREMENT,
                       Bidder_Email TEXT    NOT NULL,
                       Seller_Email TEXT    NOT NULL,
                       Date         DATE    NOT NULL,
                       Rating       INTEGER NOT NULL,
                       Rating_Desc  TEXT,
                       FOREIGN KEY (Bidder_Email) REFERENCES User_Login (email),
                       FOREIGN KEY (Seller_Email) REFERENCES User_Login (email)
                   )
                   """)

    cursor.execute("PRAGMA table_info(Ratings)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'Listing_ID' not in columns:
        try:
            cursor.execute("ALTER TABLE Ratings ADD COLUMN Listing_ID INTEGER")
        except sql.Error:
            pass

    cursor.execute("PRAGMA table_info(Auction_Listings)")
    al_columns = [col[1] for col in cursor.fetchall()]

    if 'is_promoted' not in al_columns:
        try:
            cursor.execute("ALTER TABLE Auction_Listings ADD COLUMN is_promoted INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE Auction_Listings ADD COLUMN promotion_timestamp TIMESTAMP")
            cursor.execute("ALTER TABLE Auction_Listings ADD COLUMN promotion_fee REAL")
        except sql.Error:
            pass

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS Listing_Removals
                   (
                       removal_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                       seller_email   TEXT    NOT NULL,
                       listing_id     INTEGER NOT NULL,
                       removal_reason TEXT    NOT NULL,
                       remaining_bids INTEGER NOT NULL,
                       removed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                   )
                   """)

    conn.commit()
    conn.close()

def create_notification(user_email, content, link=None):
    conn = sql.connect(DB_NAME, timeout=20)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Notifications (user_email, content, link) VALUES (?, ?, ?)",
        (user_email,content,link)
    )
    conn.commit()
    conn.close()

# Bidder ##############################################

def db_connect():
    db = sql.connect(DB_NAME)
    db.row_factory = sql.Row
    return db

def bidder_only():
    return 'user_email' in session and session.get('account_type') == '/bidder'

def bidder_msg(kind, text):
    session['bidder_msg'] = {'kind': kind, 'text': text}


def auction_sql(extra_where="", ending=""):
    return f"""
        SELECT
            a.Listing_ID AS listing_id,
            a.Seller_Email AS seller_email,
            COALESCE(NULLIF(a.Auction_Title, ''), a.Product_Name) AS title,
            a.Product_Name AS product_name,
            a.Product_Description AS description,
            a.Category AS category,
            a.Reserve_Price AS reserve_price,
            a.Status AS status_code,
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
        WHERE a.Status = 1
          AND a.Seller_Email <> ?
          {extra_where}
        ORDER BY bid_count DESC, current_bid DESC, a.Listing_ID DESC
        {ending}
    """

def load_my_bids(cur, me, limit=None):
    cur.execute(f"""
        SELECT
            a.Listing_ID AS listing_id,
            a.Seller_Email AS seller_email,
            COALESCE(NULLIF(a.Auction_Title, ''), a.Product_Name) AS title,
            a.Product_Name AS product_name,
            a.Category AS category,
            a.Status AS status_code,
            MAX(CASE WHEN b.Bidder_Email = ? THEN b.Bid_Price END) AS my_bid,
            MAX(CASE WHEN b.Bidder_Email = ? THEN b.Bid_ID END) AS my_latest_bid_id,
            MAX(b.Bid_Price) AS high_bid,
            COUNT(b.Bid_ID) AS bid_count,
            (
                SELECT b2.Bidder_Email
                FROM Bids b2
                WHERE b2.Seller_Email = a.Seller_Email
                  AND b2.Listing_ID = a.Listing_ID
                ORDER BY b2.Bid_Price DESC, b2.Bid_ID ASC
                LIMIT 1
            ) AS leader,
            (
                SELECT t.Transaction_ID
                FROM Transactions t
                WHERE t.Seller_Email = a.Seller_Email
                  AND t.Listing_ID = a.Listing_ID
                  AND t.Bidder_Email = ?
                LIMIT 1
            ) AS won_transaction,
            (
                SELECT r.Rating
                FROM Ratings r
                WHERE r.Bidder_Email = ?
                  AND r.Seller_Email = a.Seller_Email
                  AND r.Listing_ID = a.Listing_ID
                LIMIT 1
            ) AS rating
        FROM Auction_Listings a
        JOIN Bids b
            ON b.Seller_Email = a.Seller_Email
           AND b.Listing_ID = a.Listing_ID
        WHERE EXISTS (
            SELECT 1
            FROM Bids mine
            WHERE mine.Seller_Email = a.Seller_Email
              AND mine.Listing_ID = a.Listing_ID
              AND mine.Bidder_Email = ?
        )
        GROUP BY
            a.Seller_Email,
            a.Listing_ID,
            a.Auction_Title,
            a.Product_Name,
            a.Category,
            a.Status
        ORDER BY my_latest_bid_id DESC, a.Listing_ID DESC
        {limit_clause(limit)}
    """, (me, me, me, me, me))

    rows = []

    for row in cur.fetchall():
        item = dict(row)
        item['status'] = 'Active' if item['status_code'] == 1 else 'Closed'

        if item['won_transaction']:
            item['standing'] = 'Won'
        elif item['status_code'] == 1 and item['leader'] == me:
            item['standing'] = 'Winning'
        elif item['status_code'] == 1:
            item['standing'] = 'Outbid'
        elif item['status_code'] == 2 and item['leader'] == me:
            item['standing'] = 'Awaiting Payment'
        elif item['leader'] == me:
            item['standing'] = 'Highest When Closed'
        else:
            item['standing'] = 'Closed'

        rows.append(item)

    return rows

def load_awaiting_payment_items(cur, me, limit=None):
    cur.execute(f"""
        SELECT
            a.Listing_ID AS listing_id,
            a.Seller_Email AS seller_email,
            COALESCE(NULLIF(a.Auction_Title, ''), a.Product_Name) AS title,
            a.Product_Name AS product_name,
            a.Category AS category,
            MAX(b.Bid_Price) AS amount_due,
            COUNT(b.Bid_ID) AS bid_count,
            MAX(b.Bid_ID) AS latest_bid_id
        FROM Auction_Listings a
        JOIN Bids b
            ON b.Seller_Email = a.Seller_Email
           AND b.Listing_ID = a.Listing_ID
        WHERE a.Status = 2
          AND NOT EXISTS (
              SELECT 1
              FROM Transactions t
              WHERE t.Seller_Email = a.Seller_Email
                AND t.Listing_ID = a.Listing_ID
                AND t.Bidder_Email = ?
          )
          AND (
              SELECT b2.Bidder_Email
              FROM Bids b2
              WHERE b2.Seller_Email = a.Seller_Email
                AND b2.Listing_ID = a.Listing_ID
              ORDER BY b2.Bid_Price DESC, b2.Bid_ID DESC
              LIMIT 1
          ) = ?
        GROUP BY
            a.Seller_Email,
            a.Listing_ID,
            a.Auction_Title,
            a.Product_Name,
            a.Category
        ORDER BY latest_bid_id DESC, a.Listing_ID DESC
        {limit_clause(limit)}
    """, (me, me))

    return cur.fetchall()

def load_completed_items(cur, me, limit=None):
    cur.execute(f"""
        SELECT
            t.Transaction_ID AS transaction_id,
            t.Seller_Email AS seller_email,
            t.Listing_ID AS listing_id,
            t.Date AS sold_date,
            t.Payment AS payment,
            COALESCE(NULLIF(a.Auction_Title, ''), a.Product_Name) AS title,
            a.Product_Name AS product_name,
            r.Rating AS rating,
            r.Rating_Desc AS rating_desc
        FROM Transactions t
        JOIN Auction_Listings a
            ON a.Seller_Email = t.Seller_Email
           AND a.Listing_ID = t.Listing_ID
        LEFT JOIN Ratings r
            ON r.Bidder_Email = t.Bidder_Email
           AND r.Seller_Email = t.Seller_Email
           AND r.Listing_ID = t.Listing_ID
        WHERE t.Bidder_Email = ?
        ORDER BY t.Transaction_ID DESC
        {limit_clause(limit)}
    """, (me,))

    return cur.fetchall()

def limit_clause(limit):
    if limit is None:
        return ""
    return f"LIMIT {max(1, int(limit))}"

def load_ratings(cur, me):
    cur.execute("""
        SELECT
            t.Transaction_ID AS transaction_id,
            t.Seller_Email AS seller_email,
            t.Listing_ID AS listing_id,
            t.Date AS sold_date,
            t.Payment AS payment,
            COALESCE(NULLIF(a.Auction_Title, ''), a.Product_Name) AS title,
            a.Product_Name AS product_name,
            r.Rating AS rating,
            r.Rating_Desc AS rating_desc
        FROM Transactions t
        JOIN Auction_Listings a
            ON a.Seller_Email = t.Seller_Email
           AND a.Listing_ID = t.Listing_ID
        LEFT JOIN Ratings r
            ON r.Bidder_Email = t.Bidder_Email
           AND r.Seller_Email = t.Seller_Email
        WHERE t.Bidder_Email = ?
        ORDER BY t.Transaction_ID DESC
        LIMIT 30
    """, (me,))

    return cur.fetchall()

# Helpdesk ##############################################

def get_connection(row_factory=False):
    conn = sql.connect(DB_NAME)
    if row_factory:
        conn.row_factory = sql.Row
    return conn

def resolve_full_name(email):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT first_name, last_name FROM Bidders WHERE email = ?", (email,))
        bidder = cursor.fetchone()
        if bidder:
            first_name = bidder[0] or ""
            last_name = bidder[1] or ""
            name = f"{first_name} {last_name}".strip()
            if name:
                return name
    except sql.Error:
        pass
    finally:
        conn.close()
    return email.split("@")[0].replace(".", " ").title()

def ensure_app_user(email, role):
    pass

def get_app_user(email):
    conn = get_connection(row_factory=True)
    user = conn.execute(
        """
        SELECT
            ul.email,
            COALESCE(
                NULLIF(TRIM(COALESCE(b.first_name, '') || ' ' || COALESCE(b.last_name, '')), ''),
                h.Position,
                ul.email
            ) AS full_name,
            CASE
                WHEN h.email IS NOT NULL THEN 'helpdesk'
                WHEN s.email IS NOT NULL THEN 'seller'
                WHEN b.email IS NOT NULL THEN 'bidder'
                ELSE 'unknown'
            END AS role,
            'Active' AS user_status,
            '' AS created_at
        FROM User_Login ul
        LEFT JOIN Bidders b ON b.email = ul.email
        LEFT JOIN Sellers s ON s.email = ul.email
        LEFT JOIN Helpdesk h ON h.email = ul.email
        WHERE ul.email = ?
        """,
        (email,),
    ).fetchone()
    conn.close()
    return user

def authenticate_app_user(email, password, role):
    conn = get_connection(row_factory=True)
    row = conn.execute("SELECT password_hash FROM User_Login WHERE email = ?", (email,)).fetchone()
    if not row or row["password_hash"] != hash_password(password):
        conn.close()
        return False
    membership_table = {"bidder": "Bidders", "seller": "Sellers", "helpdesk": "Helpdesk"}.get(role)
    member = conn.execute(f"SELECT 1 FROM {membership_table} WHERE email = ?", (email,)).fetchone()
    conn.close()
    return bool(member)

def split_full_name(full_name):
    parts = full_name.strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])

def create_helpdesk_account(full_name, email, password, role):
    if not all([full_name, email, password, role]):
        return False, "Please complete all account creation fields."
    if role not in ("bidder", "seller", "helpdesk"):
        return False, "Please choose a valid account role."

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO User_Login (email, password_hash) VALUES (?, ?)", (email, hash_password(password)))
        first_name, last_name = split_full_name(full_name)
        if role in ("bidder", "seller"):
            cursor.execute(
                """
                INSERT INTO Bidders (email, first_name, last_name, age, home_address_id, major)
                VALUES (?, ?, ?, NULL, NULL, NULL)
                """,
                (email, first_name, last_name),
            )
        if role == "seller":
            cursor.execute(
                """
                INSERT INTO Sellers (email, bank_routing_number, bank_account_number, balance)
                VALUES (?, ?, ?, 0)
                """,
                (email, "", 0),
            )
        if role == "helpdesk":
            cursor.execute(
                "INSERT INTO Helpdesk (email, Position) VALUES (?, ?)",
                (email, "Helpdesk Staff"),
            )
        conn.commit()
        return True, "Account created successfully."
    except sql.IntegrityError:
        conn.rollback()
        return False, "An account with that email already exists."
    finally:
        conn.close()

def update_real_user(email, full_name, role):
    if not email:
        return False, "Please select a user email to update."

    conn = get_connection()
    cursor = conn.cursor()
    exists = cursor.execute("SELECT 1 FROM User_Login WHERE email = ?", (email,)).fetchone()
    if not exists:
        conn.close()
        return False, "No matching user account was found."

    try:
        if full_name:
            first_name, last_name = split_full_name(full_name)
            if cursor.execute("SELECT 1 FROM Bidders WHERE email = ?", (email,)).fetchone():
                cursor.execute(
                    "UPDATE Bidders SET first_name = ?, last_name = ? WHERE email = ?",
                    (first_name, last_name, email),
                )
            elif cursor.execute("SELECT 1 FROM Helpdesk WHERE email = ?", (email,)).fetchone():
                cursor.execute("UPDATE Helpdesk SET Position = ? WHERE email = ?", (full_name, email))

        if role:
            if role not in ("bidder", "seller", "helpdesk"):
                return False, "Please choose a valid account role."
            first_name, last_name = split_full_name(full_name or resolve_full_name(email))
            if role in ("bidder", "seller"):
                cursor.execute("DELETE FROM Helpdesk WHERE email = ?", (email,))
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO Bidders (email, first_name, last_name, age, home_address_id, major)
                    VALUES (?, ?, ?, NULL, NULL, NULL)
                    """,
                    (email, first_name, last_name),
                )
            if role == "seller":
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO Sellers (email, bank_routing_number, bank_account_number, balance)
                    VALUES (?, ?, ?, 0)
                    """,
                    (email, "", 0),
                )
            else:
                cursor.execute("DELETE FROM Sellers WHERE email = ?", (email,))
            if role == "helpdesk":
                cursor.execute("DELETE FROM Bidders WHERE email = ?", (email,))
                cursor.execute("DELETE FROM Sellers WHERE email = ?", (email,))
                cursor.execute(
                    "INSERT OR IGNORE INTO Helpdesk (email, Position) VALUES (?, ?)",
                    (email, full_name or "Helpdesk Staff"),
                )

        conn.commit()
        return True, "User account updated."
    except sql.Error as e:
        conn.rollback()
        return False, f"Database Error: {e}"
    finally:
        conn.close()

def create_real_category(parent_category, category_name):
    parent_category = parent_category or "Root"
    category_name = (category_name or "").strip()
    if not category_name:
        return False, "Please provide a category name."
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO Categories (category_name, parent_category) VALUES (?, ?)",
            (category_name, parent_category),
        )
        conn.commit()
        return True, f"Successfully added '{category_name}' under '{parent_category}'."
    except sql.IntegrityError:
        return False, f"The category '{category_name}' already exists."
    finally:
        conn.close()

def create_request_ticket(sender_email, request_type, description):
    if not request_type or not description:
        return False, "Please fill out all helpdesk fields."
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO Requests (sender_email, helpdesk_staff_email, request_type, request_desc, request_status)
            VALUES (?, ?, ?, ?, 0)
            """,
            (sender_email, DEFAULT_HELPDESK_EMAIL, request_type, description),
        )
        conn.commit()
        return True, "Your request has been submitted successfully!"
    except sql.Error as e:
        return False, f"Database Error: {e}"
    finally:
        conn.close()


def update_request_ticket(ticket_id, staff_email, status_label, assigned_email=None, assign_to_me=False):
    status_value = REQUEST_STATUS_VALUE.get(status_label, 0)

    assignment = staff_email if assign_to_me else (assigned_email or staff_email)

    conn = get_connection()
    try:
        result = conn.execute(
            """
            UPDATE Requests
            SET request_status       = ?,
                helpdesk_staff_email = ?
            WHERE request_id = ?
              AND (helpdesk_staff_email = ? OR helpdesk_staff_email = ?)
            """,
            (status_value, assignment, ticket_id, staff_email, DEFAULT_HELPDESK_EMAIL),
        )
        conn.commit()
        if result.rowcount:
            return True, f"Ticket #{ticket_id} updated."
        return False, "Ticket update failed (it may be assigned to another staff member)."
    finally:
        conn.close()


def collect_helpdesk_context():
    conn = get_connection(row_factory=True)
    staff_email = session.get("user_email")

    # Fetch ALL users for the Directory Table
    users = conn.execute(
        """
        SELECT
            ul.email,
            COALESCE(
                NULLIF(TRIM(COALESCE(b.first_name, '') || ' ' || COALESCE(b.last_name, '')), ''),
                h.Position,
                ul.email
            ) AS full_name,
            CASE
                WHEN h.email IS NOT NULL THEN 'helpdesk'
                WHEN s.email IS NOT NULL THEN 'seller'
                WHEN b.email IS NOT NULL THEN 'bidder'
                ELSE 'unknown'
            END AS role,
            'Active' AS user_status
        FROM User_Login ul
        LEFT JOIN Bidders b ON b.email = ul.email
        LEFT JOIN Sellers s ON s.email = ul.email
        LEFT JOIN Helpdesk h ON h.email = ul.email
        ORDER BY ul.email
        """
    ).fetchall()

    # Fetch tickets for the logged-in staff AND the team queue (helpdeskteam@lsu.edu)
    ticket_rows = conn.execute(
        """
        SELECT request_id, sender_email, helpdesk_staff_email, request_type, request_desc, request_status
        FROM Requests
        WHERE helpdesk_staff_email IN (?, ?)
        ORDER BY request_id DESC
        """,
        (staff_email, DEFAULT_HELPDESK_EMAIL),
    ).fetchall()

    tickets = []
    for row in ticket_rows:
        tickets.append({
            "id": row["request_id"],
            "sender_email": row["sender_email"],
            "assigned_email": row["helpdesk_staff_email"],
            "is_unassigned": row["helpdesk_staff_email"] == DEFAULT_HELPDESK_EMAIL,
            "category_name": row["request_type"],
            "subject": row["request_type"],
            "description": row["request_desc"],
            "status": REQUEST_STATUS.get(row["request_status"], "Open"),
            "status_code": row["request_status"]
        })

    # Handle hierarchical Categories
    raw_top_categories = conn.execute(
        "SELECT category_name FROM Categories WHERE parent_category = 'Root' ORDER BY category_name"
    ).fetchall()

    top_categories = [row["category_name"] for row in raw_top_categories]

    # Metrics
    stats = conn.execute(
        """
        SELECT 
            (SELECT COUNT(*) FROM User_Login) as u_count,
            (SELECT COUNT(*) FROM Categories) as c_count,
            (SELECT COUNT(*) FROM Requests WHERE request_status != 2) as o_count,
            (SELECT COUNT(*) FROM Helpdesk) as s_count
        """
    ).fetchone()

    conn.close()

    return {
        "users": users,
        "top_categories": top_categories,
        "tickets": tickets,
        "metrics": {
            "total_users": stats["u_count"],
            "categories": stats["c_count"],
            "open_tickets": stats["o_count"],
            "staff_members": stats["s_count"]
        }
    }

# Admin export functions
def build_export_rows():
    conn = get_connection(row_factory=True)
    rows = conn.execute(
        """
        SELECT
            r.request_id,
            r.request_type,
            r.request_desc,
            r.request_status,
            r.sender_email,
            r.helpdesk_staff_email,
            COALESCE(
                NULLIF(TRIM(COALESCE(b.first_name, '') || ' ' || COALESCE(b.last_name, '')), ''),
                r.sender_email
            ) AS sender_name,
            CASE
                WHEN h.email IS NOT NULL THEN 'helpdesk'
                WHEN s.email IS NOT NULL THEN 'seller'
                WHEN b.email IS NOT NULL THEN 'bidder'
                ELSE 'unknown'
            END AS sender_role
        FROM Requests r
        LEFT JOIN User_Login ul ON ul.email = r.sender_email
        LEFT JOIN Bidders b ON b.email = r.sender_email
        LEFT JOIN Sellers s ON s.email = r.sender_email
        LEFT JOIN Helpdesk h ON h.email = r.sender_email
        ORDER BY r.request_id DESC
        """
    ).fetchall()
    conn.close()

    export_rows = []
    for row in rows:
        export_rows.append(
            {
                "Ticket ID": row["request_id"],
                "Subject": row["request_type"],
                "Ticket Category": row["request_type"],
                "Ticket Status": REQUEST_STATUS.get(row["request_status"], "Open"),
                "Priority": "Medium",
                "Created At": "",
                "Updated At": "",
                "Sender Name": row["sender_name"] or "Unknown",
                "Sender Email": row["sender_email"] or "Unknown",
                "Sender Role": row["sender_role"] or "Unknown",
                "Sender Status": "Active",
                "Assigned Staff": row["helpdesk_staff_email"],
                "Category Description": "",
            }
        )
    return export_rows

def build_csv_bytes(rows):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()) if rows else ["Message"])
    writer.writeheader()
    if rows:
        writer.writerows(rows)
    else:
        writer.writerow({"Message": "No records available"})
    return io.BytesIO(buffer.getvalue().encode("utf-8"))

def build_xlsx_bytes(rows):
    headers = list(rows[0].keys()) if rows else ["Message"]
    data_rows = rows if rows else [{"Message": "No records available"}]

    def col_name(index):
        result = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            result = chr(65 + remainder) + result
        return result

    shared_strings = []
    shared_index = {}

    def string_id(value):
        if value not in shared_index:
            shared_index[value] = len(shared_strings)
            shared_strings.append(value)
        return shared_index[value]

    sheet_rows = []
    all_rows = [headers] + [[str(row.get(header, "")) for header in headers] for row in data_rows]
    for row_number, values in enumerate(all_rows, start=1):
        cells = []
        for column_number, value in enumerate(values, start=1):
            cells.append(f'<c r="{col_name(column_number)}{row_number}" t="s"><v>{string_id(value)}</v></c>')
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')

    worksheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">'
        + "".join(f"<si><t>{escape(value)}</t></si>" for value in shared_strings)
        + "</sst>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Helpdesk Export" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
        'Target="sharedStrings.xml"/></Relationships>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>'
    )

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", content_types)
        workbook.writestr("_rels/.rels", root_rels)
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        workbook.writestr("xl/worksheets/sheet1.xml", worksheet_xml)
        workbook.writestr("xl/sharedStrings.xml", shared_xml)
    output.seek(0)
    return output

# CATEGORY TRANSVERSAL ###################################
def get_top_categories(cursor):
    """Fetches all categories that sit directly under 'Root'."""
    cursor.execute('''
                   SELECT category_name
                   FROM Categories
                   WHERE parent_category = 'Root'
                   ORDER BY category_name
                   ''')
    return [r[0] for r in cursor.fetchall() if r[0]]


def get_category_breadcrumbs(cursor, category_name):
    """Traverses upward from a given category to build a breadcrumb trail."""
    if not category_name:
        return []

    breadcrumbs = []
    current_node = category_name

    while current_node:
        breadcrumbs.insert(0, current_node)
        cursor.execute("SELECT parent_category FROM Categories WHERE category_name = ?", (current_node,))
        row = cursor.fetchone()
        current_node = row[0] if row and row[0] else None

    return breadcrumbs


def get_category_descendants(cursor, category_name):
    """Uses a BFS queue to find a category and all of its nested subcategories."""
    if not category_name:
        return []

    descendants = [category_name]
    categories_to_check = [category_name]

    while categories_to_check:
        current = categories_to_check.pop(0)
        cursor.execute("SELECT category_name FROM Categories WHERE parent_category = ?", (current,))
        children = [row[0] for row in cursor.fetchall()]
        descendants.extend(children)
        categories_to_check.extend(children)

    return descendants


def build_category_tree_map(conn):
    """
    Fetches all categories and builds an adjacency list (tree map)
    for rendering full drill-down/accordion menus in templates.
    Returns the full tree map and a list of top-level categories.
    """
    raw_categories = conn.execute(
        "SELECT parent_category, category_name FROM Categories ORDER BY category_name"
    ).fetchall()

    tree_map = {}
    for row in raw_categories:
        # Assuming row_factory is enabled, so we can access by key
        parent = row["parent_category"]
        child = row["category_name"]
        tree_map.setdefault(parent, []).append(child)

    top_categories = tree_map.get('Root', [])

    return tree_map, top_categories