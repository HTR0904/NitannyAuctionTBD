import hashlib
import sqlite3 as sql
import zipfile
import io
import csv
from xml.sax.saxutils import escape
from flask import session

DB_NAME = "dataset_tables.db"
DEFAULT_HELPDESK_EMAIL = "helpdesk@lsu.edu"
REQUEST_STATUS = {
    0: "Open",
    1: "In Progress",
    2: "Closed",
}
REQUEST_STATUS_VALUE = {label: value for value, label in REQUEST_STATUS.items()}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

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

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS Watchlist (
            Bidder_Email TEXT NOT NULL,
            Listing_ID INTEGER NOT NULL,
            Seller_Email TEXT NOT NULL,
            PRIMARY KEY (Bidder_Email, Listing_ID),
            FOREIGN KEY (Bidder_Email) REFERENCES Bidders(email),
            FOREIGN KEY (Listing_ID) REFERENCES Auction_Listings(Listing_ID)
        )
    """)

    conn.commit()
    conn.close()

def create_notification(user_email, content, link=None):
    conn = sql.connect("dataset_tables.db", timeout=20)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Notifications (user_email, content, link) VALUES (?, ?, ?)",
        (user_email,content,link)
    )
    conn.commit()
    conn.close()

# Bidder ##############################################

def db_connect():
    db = sql.connect("dataset_tables.db")
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



def load_my_bids(cur, me):
    cur.execute("""
        SELECT
            a.Listing_ID AS listing_id,
            a.Seller_Email AS seller_email,
            COALESCE(NULLIF(a.Auction_Title, ''), a.Product_Name) AS title,
            a.Product_Name AS product_name,
            a.Category AS category,
            a.Status AS status_code,
            MAX(CASE WHEN b.Bidder_Email = ? THEN b.Bid_Price END) AS my_bid,
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
            ) AS won_transaction
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
        ORDER BY a.Status = 1 DESC, a.Listing_ID DESC
    """, (me, me, me))

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
        elif item['leader'] == me:
            item['standing'] = 'Highest When Closed'
        else:
            item['standing'] = 'Closed'

        rows.append(item)

    return rows


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
    # Historical routes call this after login. The real membership tables are the
    # source of truth now, so this is intentionally non-destructive.
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
            SET request_status = ?, helpdesk_staff_email = ?
            WHERE request_id = ?
              AND (helpdesk_staff_email = ? OR helpdesk_staff_email = ?)
            """,
            (status_value, assignment, ticket_id, staff_email, DEFAULT_HELPDESK_EMAIL),
        )
        conn.commit()
        if result.rowcount:
            return True, f"Ticket #{ticket_id} updated."
        return False, "Ticket not found, or it is assigned to another helpdesk staff member."
    finally:
        conn.close()

def collect_helpdesk_context():
    conn = get_connection(row_factory=True)

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
            'Active' AS user_status,
            '' AS created_at
        FROM User_Login ul
        LEFT JOIN Bidders b ON b.email = ul.email
        LEFT JOIN Sellers s ON s.email = ul.email
        LEFT JOIN Helpdesk h ON h.email = ul.email
        ORDER BY ul.email
        """
    ).fetchall()

    # Fetch ALL Categories
    raw_categories = conn.execute(
        "SELECT parent_category, category_name FROM Categories ORDER BY category_name"
    ).fetchall()

    # Build a Full Tree Map (Parent -> [Children])
    # This map will contain EVERYTHING, including the 'Root' key.
    tree_map = {}
    for row in raw_categories:
        parent = row["parent_category"]
        child = row["category_name"]

        if parent not in tree_map:
            tree_map[parent] = []
        tree_map[parent].append(child)

    # Identify Top-Level Categories (Direct children of 'Root')
    # These are the ones that will become the primary Accordion cards.
    top_categories = tree_map.get('Root', [])

    staff_email = session.get("user_email")
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
            "status_code": row["request_status"],
            "priority": "Medium",
            "created_at": "",
            "updated_at": "",
        })
    all_ticket_statuses = conn.execute("SELECT request_status FROM Requests").fetchall()
    staff_count = conn.execute("SELECT COUNT(*) AS total FROM Helpdesk").fetchone()["total"]
    category_count = conn.execute("SELECT COUNT(*) AS total FROM Categories").fetchone()["total"]
    user_count = conn.execute("SELECT COUNT(*) AS total FROM User_Login").fetchone()["total"]
    conn.close()

    metrics = {
        "total_users": user_count,
        "open_tickets": sum(1 for ticket in all_ticket_statuses if ticket["request_status"] != 2),
        "categories": category_count,
        "staff_members": staff_count,
    }

    return {
        "users": users,
        "tree_map": tree_map,
        "top_categories": top_categories,
        "tickets": tickets,
        "metrics": metrics
    }

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

# Admin Export functions

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