# Nitanny Auction

## Context
Nittany Auction is an online platform designed to connect
buyers and sellers through an auction system.
Users can list products, place bids, track watched items, and communicate directly with sellers.

The platform supports multiple account roles: Bidders, Sellers, Helpdesk Staff.

## Features
### User Authentication

Uses Python with SQLite to handle user login against the database.

The system looks up the user by email in the table where login credentials are stored.
If no matching user is found, an error message is returned.

If a match is found, the stored password hash is retrieved and compared against
the SHA-256 hash of the input password.
If the hashes do not match, login fails.

If they match, the user is redirected based on their role:
- Bidders -> `/bidder`
- Sellers -> `/seller`
- Helpdesk staff -> `/helpdesk`

An error is shown if the role is not recognized.

Passwords are never stored as plain text and hashing is used throughout to improve security.

### User Registration
The registration system uses a single dynamic frontend within `register.html` to manage the account creation process. 
A role-selection mechanism allows users to toggle between Bidder, Seller, and Helpdesk account types, 
which triggers the JavaScript function `selectRole` to manage 
the visibility of specific form sections. 
This function also updates the `required` attributes for relevant input fields to ensure data integrity before the form is submitted. 
Sellers are also provided with a specialized toggle to register as a Local Vendor.

On the backend, the system processes registration data through the `auth.register` route 
located in `auth.py`. The application first verifies that the input email is not already registered in the `User_Login` table and enforces password security by generating a SHA-256 hash using the `hash_password` utility before any data is committed. While the system populates the `User_Login` table for all users, the subsequent relational logic diverges by role. Helpdesk registration involves an insertion into the `Helpdesk` table and the simultaneous creation of a registration-type ticket in the `Requests` table with an initial status of incomplete for administrative review.

For Bidder and Seller accounts, the system manages physical location data by inserting home address details into a dedicated `Address` table using unique UUIDs generated via `uuid.uuid4().hex`. Because the platform treats Sellers as a functional subset of Bidders, the application ensures that seller registrations populate both the `Bidders` and `Sellers` tables. If a seller registers as a Local Vendor, the backend performs an additional address insertion for the business location and records commercial details in the `Local_Vendors` table. After successfully committing these database transactions, the system calls the `ensure_app_user` helper and triggers a Bootstrap modal in `register.html` to confirm account creation and direct the user to the login portal.

### Bidder Functionality

This module implements core bidder actions including authentication, auction browsing, bid placement, and transaction history. The primary logic is distributed between `app.py` for routing, `utils.py` for database operations, and the frontend templates for the dashboard and history views.

**Bidder Home Page**
Managed by the `@app.route('/bidder')` route, this serves as the main dashboard following a successful login. The interface aggregates critical user data, including trending auctions, the three most recent auctions in which the bidder is participating, items awaiting payment, and a summary of completed transactions. The backend also queries the `Credit_Cards` table to verify if the user has a saved payment method, displaying a reminder if no card is found.

**Bidding History Page**
The `@app.route('/bidding_history')` route renders a comprehensive record of all auction activity associated with the bidder's account. This allows users to track their engagement with both active and closed listings in one consolidated view.

**Auction Detail Page**
Detailed information for individual listings is provided through the `@app.route('/auction/<seller_email>/<int:listing_id>')` route. This page presents exhaustive metadata, including product descriptions, category classifications, and hidden reserve price indicators. It calculates real-time financial metrics such as the current high bid and the minimum next bid. The interface also displays seller ratings, bid history, and tracking status via the watchlist integration.

**Placing a Bid**
The `@app.route('/place_bid', methods=['POST'])` route handles the bidding process and enforces several business logic constraints. The system verifies that the user is logged in as a bidder, ensures the bid amount is a whole-dollar integer, and confirms the auction is active. Additional security logic prevents bidders from placing consecutive bids on the same item and validates that each new bid exceeds the current highest bid.

**Awaiting Payment Items**
Auctions are classified as "Awaiting Payment" when the status is set to 2 (Sold), the user is the winning bidder, and no transaction record exists. This functionality is supported by the `load_awaiting_payment_items` utility. These items appear on the bidder dashboard with direct links to the checkout process.

**Checkout and Payment**
The checkout interface, accessed via `@app.route('/checkout/<seller_email>/<int:listing_id>')`, is restricted to winning bidders with pending payments. Financial processing is finalized through the `@app.route('/process_payment', methods=['POST'])` route, which records the transaction and updates the seller's balance accordingly.

**Completed Items**
The `load_completed_items` function retrieves data for finalized transactions, including transaction IDs, payment amounts, and sold dates. This view also tracks whether the bidder has provided a seller rating for the specific listing. These records are displayed on the home dashboard and within the bidding history for user reference.

### Seller homepage

This page supports the seller-facing auction flow:
- Create new product listings with details, category, hidden reserve price, quantity, and max bids
- Manage seller listings
- Search listings by keyword and category
- Request additional categories through helpdesk
- Receive notifications when auctions conclude
- Update seller payment information from settings

### Listing Management (Seller)

The "Manage My Listings" area on `seller_home.html` shows all listings in four tabs. Each tab has a count.
- **Active** (Status = 1): open for bidding
- **Pending Review** (Status = 3): ended below reserve price, waiting for seller
- **Sold** (Status = 2): sold already
- **Inactive** (Status = 0): taken off by the seller

The `/list_product` route gives each seller their own `Listing_ID` count. The SQL is `SELECT COALESCE(MAX(Listing_ID), 0) + 1 FROM Auction_Listings WHERE Seller_Email = ?`. So each seller's IDs start from 1. Reserve prices are saved like `$X,XXX.XX` to match the seed data.
**Edit Listing** is at `/edit_listing/<listing_id>`. It has two rules:
- Sold listings cannot be edited.
- Active listings can only be edited when `bid_count == 0`. If anyone has already placed a bid, the Edit button is turned off with a tooltip.

**Remove Listing** is at `/remove_listing/<listing_id>`. The seller fills in a reason in a modal box. The system saves the reason and the `remaining_bids` value (= `Max_bids - bid_count` at that moment) in a new `Listing_Removals` table. The listing's status is set to 0 (Inactive).

**Pending Auction Review** is at `/auction_decide/<listing_id>`. It handles auctions that hit `Max_bids` but stay below the reserve price. These are set to Status = 3 (Pending Review). They show up in the Pending Review tab and in the "Auction Results" box at the bottom of `seller_home.html`. The seller can:
- **Accept** the top bid: listing becomes Sold (Status = 2). The winning bidder gets a notification.
- **Reject** the top bid: listing becomes Inactive (Status = 0). The bidder gets a notification.

### Helpdesk homepage

This page supports the main helpdesk/admin tasks from the project checklist:
- Account creation
- User management
- Category management
- Ticket intake and assignment
- Pseudo database export

Helpdesk account creation writes to the real account tables instead of a dummy table.
New accounts are inserted into `User_Login` and then into the correct role table:
- Bidder accounts are inserted into `Bidders`
- Seller accounts are inserted into `Bidders` and `Sellers`
- Helpdesk accounts are inserted into `Helpdesk`

Category management inserts new categories into the real `Categories` table.
Helpdesk staff can choose a parent category and add a child category underneath it.

Tickets are stored in the real `Requests` table.
New tickets are assigned to the default unassigned queue email `helpdeskteam@lsu.edu`.
The helpdesk dashboard displays:
- Tickets assigned to the currently logged-in helpdesk staff member
- Unassigned tickets assigned to `helpdeskteam@lsu.edu`

Helpdesk staff can assign unassigned tickets to themselves from the dashboard.
They can also update ticket status and export the pseudo database view as CSV or XLSX.

The helpdesk routes are split into `routes/helpdesk.py` so that new helpdesk logic does not keep growing `app.py`.
Shared helper functions for account creation, ticket queries, category inserts, and exports are located in `utils.py`.

### Category Hierarchy and Dynamic Dropdown

The platform implements a nested category hierarchy to organize listings. The application uses AJAX to render options dynamically, rather than loading all categories simultaneously. 

When a category is selected from a dropdown menu, a jQuery listener triggers a `change` event and sends a `GET` request to `/get_subcategories`. 

The Flask route queries the `Categories` table for the direct children of the selected category and returns the results as a JSON array. The frontend JavaScript parses this data and appends a new `<select>` dropdown to the interface. The most specific selected value is stored in a hidden `#final_category_input` field for form submission.

This structure is used for the following feature:

#### Helpdesk (Category Management)
Staff use the cascading dropdown menus to navigate the existing tree and select a parent node. 
They can then input a new category name, which is inserted into the database as a child of the selected node. 
The UI also provides a visual map of the category tree that fetches subcategories via AJAX when a node is expanded.

#### Seller (Listing Creation):
The "List a Product" form prompts sellers to select a top-level category and proceed through generated subcategories to 
specify the product classification before submission.

#### Search Filtering:
The dynamic dropdowns enable users to filter search results by specific subcategories. 
The backend utilizes a BFS function (`get_category_descendants`) to identify the selected category and map its nested descendants.
These descendants are appended to an SQL `IN` clause to ensure queries for a parent category return items from all corresponding subcategories. 
`get_category_breadcrumbs` traverses the database hierarchy upward to generate a visual of the filter path.
`/search` also supports keyword search and price range filter. The keyword search looks in auction title, product name, and description. 
The price filter can switch between **reserve price** and **current highest bid**. For reserve price, the SQL uses `CAST(REPLACE(REPLACE(Reserve_Price, '$', ''), ',', '') AS REAL)` because the price is saved as text with dollar signs. 
For current bid, the filter is in the `HAVING` clause with `MAX(Bid_Price)` because it is a group value.

### Notifications

The notification system uses a `Notifications` table. A helper called `create_notification(user_email, content, link)` is called from many places (new bids, outbid events, auction ended, seller decisions, and so on). 
A context processor adds the unread count to every template. So the bell icon in the navbar is always up to date.

On `/notifications`, users can mark one notification as read, mark all as read, delete one, or delete all. Each notification can have a link. Clicking it jumps to the right page.

### Watchlist

The watchlist feature allows bidders to track specific auction listings and monitor their progress without immediately placing a bid. 
Bidders can add or remove listings from their watchlist using a toggle button on individual auction detail pages, 
which then consolidates these tracked items into a dedicated watchlist dashboard. 
This interface enables users to quickly navigate back to auctions of interest.

`Watchlist` table in the database enables tracking of watcher relationship by mapping the bidder's email to the listing ID and seller email. 
A template component, `watch_button.html`, handles the UI logic by checking the current watch status and displaying either a "Watching" or "Add to Watchlist" button. 
When a user interacts with this component `/toggle_watchlist` route handles the database insertions or deletions and provides feedback through success or error flash messages.

The watchlist dashboard provides overview of all auction items and auction status
Also utilizes  the notification system to ensure watchers receive alerts when a new bid is placed or when a tracked auction officially concludes.

### Settings

`/settings` puts all account updates in one page:
- **Password change**: checks the current password (using SHA-256 hash) before saving a new one.
- **Credit cards**: users can add and delete saved cards. Only the last four digits are shown for safety.
- **Bank info** (sellers only): sellers can update their routing and account numbers. The values are saved to the `Sellers` table.
- **Logout**: ends the session and goes back to the login page.

## Schema Extensions

On startup, `init_db()` in `utils.py` creates two extra tables:

```sql
CREATE TABLE IF NOT EXISTS Notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT NOT NULL,
    content TEXT NOT NULL,
    link TEXT,
    is_read INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0, 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_email) REFERENCES User_Login(email)
);

CREATE TABLE IF NOT EXISTS Listing_Removals (
    removal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_email TEXT NOT NULL,
    listing_id INTEGER NOT NULL,
    removal_reason TEXT NOT NULL,
    remaining_bids INTEGER NOT NULL,
    removed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

The `Notifications` table supports the notification feature. The `Listing_Removals` table saves the audit record for listing removals. 
It keeps the seller's reason and the remaining bids at the time of removal. This data stays even if the listing is changed or deleted later.

We also added a new value `3` to `Auction_Listings.Status`. This means *Pending Seller Review* — auctions that ended below reserve price and wait for the seller to accept or reject. 
The old values are still used: `0` (Inactive), `1` (Active), and `2` (Sold).

## Organization
```text
Project_Root/
├── app.py                    # Main Python/Flask application
├── dataset_tables.db         # SQLite database file
├── README.md                 # Project documentation
├── resources.md              # Documentation of resources used for project
├── utils.py                  # Shared database helper functions
├── routes/                   # Route blueprints split out from app.py
│   ├── __init__.py           # Python package initializer
│   ├── auth.py               # Login, logout, and registration routes
│   ├── helpdesk.py           # Helpdesk, ticket, and administrative routes
│   └── notif.py              # Notification and alert routes
├── static/                   # Static assets
│   └── css/                  # Stylesheet directory
│       └── ui-polish.css     # Shared UI polish stylesheet
└── templates/                # HTML frontend files
    ├── components/           # Reusable HTML template fragments
    │   ├── navbar.html       # Global navigation bar component (for bidder and seller)
    │   └── watch_button.html # Reusable button for watchlist toggling
    ├── auction_detail.html   # Detailed view of individual listings
    ├── bidders_home.html     # Main dashboard for bidders
    ├── bidding_history.html  # Record of user bidding activity
    ├── checkout.html         # Payment and transaction processing page
    ├── contact.html          # Support and category request submission page
    ├── edit_listing.html     # Seller interface for modifying active listings
    ├── helpdesk_home.html    # Main dashboard for helpdesk staff
    ├── login.html            # User authentication portal
    ├── notifications.html    # User notification history
    ├── register.html         # New account registration page
    ├── search.html           # Search and filtering page
    ├── seller_home.html      # Main dashboard for sellers
    ├── settings.html         # Account and payment management page
    └── watchlist.html        # Tracked auction listings page
```

---

## Instructions on how to initialize database
1. Open MySql.
2. Create table framework.
3. Import csv files into their respected table.
4. Save as db file. 

## Instructions on how to run the code

### Prerequisites
* PyCharm Pro
* Python 3.x installed (recommended Python 3.13)

### Loading the Files into PyCharm Professional
1. Open PyCharm Professional.
2. Select File > Open and select the project folder containing app.py.
3. PyCharm should automatically detect the Flask environment. If prompted to create a virtual environment, select Yes.

### Running the Code
1. Open app.py in the editor.
2. Click the Run button (green arrow) or right-click within app.py and select Run 'app'.
   (*Notice: On the first run, the terminal may prompt you to install the Flask module. Please do so then try running the app again.*)
3. The terminal will display a local link (currently set as http://127.0.0.1:5000/).
4. Click the link to open the Nittany Auction login portal in your browser.

---

## Resources Used
Links to all resources used in the process of project development [resources page](resources.md)
