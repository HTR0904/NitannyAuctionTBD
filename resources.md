## Web Framework & Python Logic
Flask was used as the primary web framework for backend routing, session management, and server-side logic.

### Session Management & Flashing
Used for storing the logged-in user's state, account type, and passing temporary alert messages: https://flask.palletsprojects.com/en/2.3.x/api/#sessions

### Application Blueprints
Used to organize and separate routing logic for the helpdesk, authentication, and notifications: https://flask.palletsprojects.com/en/2.3.x/blueprints/

### CSV and File Operations
Used the built-in `csv`, `io`, and `zipfile` modules to generate and format helpdesk ticket data exports: https://docs.python.org/3/library/csv.html

## HTML and Jinja
Jinja2 was used to dynamically render frontend HTML pages using backend database variables.

### Template Inheritance & Context Processors
Used to send global variables (e.g. `current_user`) to all template files automatically: https://jinja.palletsprojects.com/en/3.1.x/api/#jinja2.Environment.context_processor

### Control Structures
Loops and conditionals (`{% for %}`, `{% if %}`) to display dynamic tables, search results, and auction statuses: https://jinja.palletsprojects.com/en/3.1.x/templates/#list-of-control-structures

## Database & SQL Queries
SQLite3 was used for the relational database management system. Queries were used to render user dashboards and manage transactions.

### Relational Joins
Used `LEFT JOIN` and `INNER JOIN` to fetch data across tables within single queries: https://www.sqlite.org/lang_select.html#joins

## JavaScript / AJAX / Additional Page Logic
jQuery and Flask were used to implement the category dropdown feature.

### AJAX
Used for HTTP GET requests to load subcategories: https://api.jquery.com/jQuery.getJSON/

### Event Delegation
Used for attaching event listeners to dynamically generated dropdown menus: https://api.jquery.com/on/#direct-and-delegated-events

### JSON Responses (for AJAX)
Used to convert Python lists into JSON for AJAX: https://flask.palletsprojects.com/en/2.3.x/api/#flask.json.jsonify

### DOM
- Used to target lower-level category dropdowns: https://api.jquery.com/nextAll/
- Used to clear orphaned subcategories from the UI: https://api.jquery.com/remove/

## UI Elements
Bootstrap was used for the website’s UI design and layout.
https://getbootstrap.com/docs/5.3/getting-started/introduction/

### Alerts
Used for login error messages, flash notifications, and success alerts: https://getbootstrap.com/docs/4.1/components/alerts/

### Modals
Used for confirmation dialogs to prevent accidental deletions: https://getbootstrap.com/docs/4.1/components/modal/

### Navigation & Layout
- Navigation menus and responsive search bar: https://getbootstrap.com/docs/4.1/components/navbar/
- Grid system (Rows and Columns) for page layouts: https://getbootstrap.com/docs/4.1/layout/grid/
- Large hero components (Jumbotrons) for dashboard headers: https://getbootstrap.com/docs/4.0/components/jumbotron/

### Data Display
- Tables for displaying auction listings, user directories, and support tickets: https://getbootstrap.com/docs/4.1/content/tables/
- Badges and Pills for status indicators, notification counts, and category tags: https://getbootstrap.com/docs/4.1/components/badge/
- Nav Tabs for categorizing listings on the seller dashboard into Active, Sold, and Inactive groups: https://getbootstrap.com/docs/4.1/components/navs/#tabs

### Interactive Elements
- Input Groups for the unified search and filtering interface: https://getbootstrap.com/docs/4.1/components/input-group/
- Notification bell icon integrated into the navbar: https://icons.getbootstrap.com/icons/bell/