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

### Bidder homepage

This page supports the bidder-facing auction flow:
- Feature trending auctions to bidders
- Browse products and listings
- View current bids participated in
- Open auction detail pages
- Add and remove listings from the watchlist
- Submit helpdesk requests
- Receive notifications for watched listings and bid activity

### Seller homepage

This page supports the seller-facing auction flow:
- Create new product listings with details, category, hidden reserve price, quantity, and max bids
- Manage seller listings
- Search listings by keyword and category
- Request additional categories through helpdesk
- Receive notifications when auctions conclude
- Update seller payment information from settings

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
New tickets are assigned to the default unassigned queue email `helpdesk@lsu.edu`.
The helpdesk dashboard displays:
- Tickets assigned to the currently logged-in helpdesk staff member
- Unassigned tickets assigned to `helpdesk@lsu.edu`

Helpdesk staff can assign unassigned tickets to themselves from the dashboard.
They can also update ticket status and export the pseudo database view as CSV or XLSX.

The helpdesk routes are split into `routes/helpdesk.py` so that new helpdesk logic does not keep growing `app.py`.
Shared helper functions for account creation, ticket queries, category inserts, and exports are located in `utils.py`.

### Watchlist

The watchlist feature allows bidders to track auction listings.
Users can watch or unwatch listings, view all watched listings from the watchlist page,
and open the auction listing page directly from the watchlist.

### Notifications

The notification feature alerts users about auction and bidding events.
Notifications are connected to the database and can be viewed from the notifications page.

### Settings

The settings page supports account-related updates such as password changes and payment information.
Sellers can update bank payment information from this page.

## Organization
```text
Project_Root/
|-- app.py                    # Main Python/Flask application
|-- README.md                 # Project documentation
|-- resources.md              # Documentation of resources used for project
|-- setup.md                  # Project setup instructions and guidelines
|-- utils.py                  # Shared database helper functions
|-- routes/                   # Route blueprints split out from app.py
|   |-- auth.py               # Login, logout, and registration routes
|   |-- helpdesk.py           # Helpdesk, ticket, category, account, and export routes
|   `-- notif.py              # Notification routes
|-- templates/                # HTML frontend files
|   |-- login.html            # Main login page
|   |-- seller_home.html      # Main homepage for sellers
|   |-- helpdesk_home.html    # Main homepage for helpdesk
|   |-- bidders_home.html     # Main homepage for bidders
|   |-- search.html           # Search page
|   |-- watchlist.html        # Watchlist page
|   |-- notifications.html    # Notifications page
|   `-- settings.html         # Account settings page
`-- static/                   # Static assets
    |-- css/                  # Shared UI polish stylesheet
    `-- images/               # Image files
        `-- docs/             # Images used for README pages
```

---

## Instructions on how to run the code

### Prerequisites
* PyCharm Pro
* Python 3.x installed

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
## Contributing to the Repo (through Github)
> This section is for team members' reference

For instructions on how to set up this project on your device,
along with some useful commands and guidelines when working with git,
please visit the [set-up page](setup.md)

## Resources Used
Links to all resources used in the process of website creation [resources page](resources.md)
