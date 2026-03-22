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
- Bidders → `/bidder`
- Sellers → `/seller`
- Helpdesk staff → `/helpdesk`

An error is shown if the role is not recognized.

Passwords are never stored as plain text and hashing is used throughout to improve security.

## Organization
```text
Project_Root/
├── app.py                    # Main Python/Flask application
├── README.md                 # Project documentation
├── resources.md              # Documentation of resources used for project
├── setup.md                  # Project setup instructions and guidelines
├── templates/                # HTML frontend files
│   ├── login.html            # Main login page
│   ├── seller_home.html      # Main homepage for sellers
│   ├── helpdesk_home.html    # Main homepage for helpdesk
│   └── bidders_home.html     # Main homepage for bidders
└── static/                   # Static assets
    └── images/               # Image files
        └── docs/             # Images used for README pages

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
please visit the  [set-up page](setup.md)

## Resources Used
Links to all resources used in the process of website creation [resources page](resources.md)