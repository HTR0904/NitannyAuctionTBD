import hashlib
import sqlite3 as sql
import zipfile
import io
import csv
from xml.sax.saxutils import escape
from datetime import datetime
from flask import session

DB_NAME = "dataset_tables.db"
USERS_TABLE = "app_users"
CATEGORIES_TABLE = "app_categories"
TICKETS_TABLE = "app_helpdesk_tickets"

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

def ensure_admin_schema():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS {USERS_TABLE} (
            email TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('bidder', 'seller', 'helpdesk')),
            user_status TEXT NOT NULL DEFAULT 'Active',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS {CATEGORIES_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS {TICKETS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_email TEXT NOT NULL,
            assigned_email TEXT NOT NULL,
            category_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            priority TEXT NOT NULL DEFAULT 'Medium',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    seed_users = [
        ("bidder@nittanyauction.com", "Campus Bidder", hash_password("password123"), "bidder"),
        ("seller@nittanyauction.com", "Campus Seller", hash_password("password123"), "seller"),
        ("helpdesk@nittanyauction.com", "Helpdesk Admin", hash_password("password123"), "helpdesk"),
    ]
    for email, full_name, password_hash, role in seed_users:
        cursor.execute(
            f"""
            INSERT OR IGNORE INTO {USERS_TABLE} (email, full_name, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email, full_name, password_hash, role, now),
        )

    seed_categories = [
        ("Electronics", "Devices, gadgets, and peripherals."),
        ("Books", "Textbooks, novels, and study materials."),
        ("Furniture", "Dorm and apartment furniture."),
        ("Helpdesk", "Account, listing, and system support requests."),
    ]
    for name, description in seed_categories:
        cursor.execute(
            f"""
            INSERT OR IGNORE INTO {CATEGORIES_TABLE} (name, description, created_by, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (name, description, "helpdesk@nittanyauction.com", now),
        )

    conn.commit()
    conn.close()

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
    ensure_admin_schema()
    conn = get_connection(row_factory=True)
    cursor = conn.cursor()
    try:
        password_row = cursor.execute(
            "SELECT password_hash FROM User_Login WHERE email = ?",
            (email,),
        ).fetchone()
        password_hash = password_row["password_hash"] if password_row else hash_password("password123")
        cursor.execute(
            f"""
            INSERT OR IGNORE INTO {USERS_TABLE} (email, full_name, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                email,
                resolve_full_name(email),
                password_hash,
                role,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        cursor.execute(f"UPDATE {USERS_TABLE} SET role = ? WHERE email = ?", (role, email))
        conn.commit()
    finally:
        conn.close()

def get_app_user(email):
    ensure_admin_schema()
    conn = get_connection(row_factory=True)
    user = conn.execute(f"SELECT * FROM {USERS_TABLE} WHERE email = ?", (email,)).fetchone()
    conn.close()
    return user

def authenticate_app_user(email, password, role):
    user = get_app_user(email)
    return bool(user and user["password_hash"] == hash_password(password) and user["role"] == role)

def create_helpdesk_account(full_name, email, password, role):
    if not all([full_name, email, password, role]):
        return False, "Please complete all account creation fields."

    ensure_admin_schema()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""
            INSERT INTO {USERS_TABLE} (email, full_name, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email, full_name, hash_password(password), role, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        return True, "Account created successfully."
    except sql.IntegrityError:
        return False, "An account with that email already exists."
    finally:
        conn.close()

def collect_helpdesk_context():
    ensure_admin_schema()
    conn = get_connection(row_factory=True)

    # Fetch Users
    users = conn.execute(
        f"SELECT email, full_name, role, user_status, created_at FROM {USERS_TABLE} ORDER BY created_at DESC"
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

    tickets = conn.execute(
        f"""
        SELECT id, sender_email, assigned_email, category_name, subject, description, status, priority,
               created_at, updated_at
        FROM {TICKETS_TABLE}
        ORDER BY created_at DESC
        """
    ).fetchall()
    conn.close()

    metrics = {
        "total_users": len(users),
        "open_tickets": sum(1 for ticket in tickets if ticket["status"] != "Closed"),
        "categories": len(raw_categories),
        "staff_members": sum(1 for user in users if user["role"] == "helpdesk"),
    }

    return {
        "users": users,
        "tree_map": tree_map,
        "top_categories": top_categories,
        "tickets": tickets,
        "metrics": metrics
    }

def build_export_rows():
    ensure_admin_schema()
    conn = get_connection(row_factory=True)
    rows = conn.execute(
        f"""
        SELECT
            t.id AS ticket_id,
            t.subject,
            t.category_name,
            t.status,
            t.priority,
            t.created_at,
            t.updated_at,
            sender.full_name AS sender_name,
            sender.email AS sender_email,
            sender.role AS sender_role,
            sender.user_status AS sender_status,
            t.assigned_email,
            c.description AS category_description
        FROM {TICKETS_TABLE} t
        LEFT JOIN {USERS_TABLE} sender ON sender.email = t.sender_email
        LEFT JOIN {CATEGORIES_TABLE} c ON c.name = t.category_name
        ORDER BY t.created_at DESC
        """
    ).fetchall()
    conn.close()

    export_rows = []
    for row in rows:
        export_rows.append(
            {
                "Ticket ID": row["ticket_id"],
                "Subject": row["subject"],
                "Ticket Category": row["category_name"],
                "Ticket Status": row["status"],
                "Priority": row["priority"],
                "Created At": row["created_at"],
                "Updated At": row["updated_at"],
                "Sender Name": row["sender_name"] or "Unknown",
                "Sender Email": row["sender_email"] or "Unknown",
                "Sender Role": row["sender_role"] or "Unknown",
                "Sender Status": row["sender_status"] or "Unknown",
                "Assigned Staff": row["assigned_email"],
                "Category Description": row["category_description"] or "",
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
