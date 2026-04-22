from datetime import datetime
from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for
from utils import *

# Helpdesk routes live in their own blueprint so app.py stays focused on the
# general app routes while this file owns admin tickets, users, categories, and exports.
helpdesk_bp = Blueprint("helpdesk", __name__)


def helpdesk_only():
    """Return True only when the current session belongs to a logged-in helpdesk user."""
    return "user_email" in session and session.get("account_type") == "/helpdesk"


@helpdesk_bp.route("/submit_ticket", methods=["POST"])
def submit_ticket():
    """Create a helpdesk ticket from the shared contact/category request form."""
    if "user_email" not in session:
        return redirect("/")

    req_type = request.form.get("request_type")
    is_category_form = req_type == "AddCategory"

    # Category requests use two visible fields, but the Requests table stores one
    # description column, so combine the category name and reason before saving.
    if is_category_form:
        cat_name = request.form.get("cat_name", "").strip()
        cat_reason = request.form.get("cat_reason", "").strip()
        description = f"Requested Category: {cat_name}\nReason: {cat_reason}" if cat_name and cat_reason else ""
    else:
        description = request.form.get("request_desc", "").strip()

    created, message = create_request_ticket(session["user_email"], req_type, description)
    return render_template(
        "contact.html",
        is_category=is_category_form,
        helpdesk_req_success=message if created else None,
        helpdesk_req_error=None if created else message,
    )

@helpdesk_bp.route("/helpdesk")
def helpdesk():
    """Render the dashboard with only relevant tickets and real database summaries."""
    if not helpdesk_only():
        flash("Please log in to continue.", "auth_error")
        return redirect(url_for("index"))

    # collect_helpdesk_context reads real database tables and filters tickets to
    # this staff member plus the shared unassigned helpdesk queue.
    context = collect_helpdesk_context()

    # Mark queue tickets for the template so it can show the "Assign to me" action.
    if "tickets" in context:
        for ticket in context["tickets"]:
            if ticket.get("assigned_email") == DEFAULT_HELPDESK_EMAIL:
                ticket["is_unassigned"] = True
            else:
                ticket["is_unassigned"] = False

    context["current_user"] = get_app_user(session["user_email"])
    context["default_helpdesk_email"] = DEFAULT_HELPDESK_EMAIL

    return render_template("helpdesk_home.html", **context)


@helpdesk_bp.route("/helpdesk/create_account", methods=["POST"])
def create_helpdesk_account_route():
    """Create a bidder, seller, or helpdesk account through the real account tables."""
    if not helpdesk_only():
        flash("You must be logged in as helpdesk to manage admin tools.", "auth_error")
        return redirect(url_for("index"))

    # The helpdesk form captures first and last name separately for readability,
    # while the helper accepts one full_name and splits it for the Bidders table.
    f_name = request.form.get("first_name", "").strip()
    l_name = request.form.get("last_name", "").strip()
    full_name = f"{f_name} {l_name}".strip()

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "bidder").strip()
    created, message = create_helpdesk_account(full_name, email, password, role)
    flash(message, "success" if created else "danger")
    return redirect("/helpdesk")


@helpdesk_bp.route("/helpdesk/create_category", methods=["POST"])
def create_category():
    """Insert a new child category under the selected parent in Categories."""
    if not helpdesk_only():
        return redirect("/")

    created, message = create_real_category(
        request.form.get("existing_parent"),
        request.form.get("child_category", "").strip(),
    )
    flash(message, "success" if created else "danger")
    return redirect("/helpdesk")


@helpdesk_bp.route("/helpdesk/update_user", methods=["POST"])
def update_user():
    """Update a user's role using the real role membership tables."""
    if not helpdesk_only():
        flash("You must be logged in as helpdesk to update users.", "auth_error")
        return redirect(url_for("index"))

    email = request.form.get("user_email", "").strip().lower()
    role = request.form.get("role", "").strip()
    updated, message = update_real_user(email, "", role)

    flash(message, "success" if updated else "danger")
    return redirect("/helpdesk")


@helpdesk_bp.route("/helpdesk/update_ticket/<int:ticket_id>", methods=["POST"])
def update_ticket(ticket_id):
    """Update ticket status or assignment, including assigning queue tickets to self."""
    if not helpdesk_only():
        flash("You must be logged in as helpdesk to update tickets.", "auth_error")
        return redirect(url_for("index"))

    updated, message = update_request_ticket(
        ticket_id=ticket_id,
        staff_email=session["user_email"],
        status_label=request.form.get("status", "Open").strip(),
        assigned_email=request.form.get("assigned_email", "").strip(),
        assign_to_me=request.form.get("assign_to_me") == "1",
    )
    flash(message, "success" if updated else "danger")
    return redirect("/helpdesk")

@helpdesk_bp.route("/helpdesk/approve_registration/<int:ticket_id>", methods=["POST"])
def approve_registration(ticket_id):
    """Approve a staff registration request by adding the sender to Helpdesk."""
    if not helpdesk_only():
        flash("Unauthorized access.", "danger")
        return redirect(url_for("index"))

    import sqlite3 as sql
    from utils import DB_NAME, hash_password

    conn = sql.connect(DB_NAME)
    conn.row_factory = sql.Row
    cursor = conn.cursor()

    try:
        ticket = cursor.execute(
            "SELECT sender_email, request_desc FROM Requests WHERE request_id = ?",
            (ticket_id,)
        ).fetchone()

        if not ticket:
            flash("Request not found.", "danger")
            return redirect("/helpdesk")

        email = ticket["sender_email"]
        position = ticket["request_desc"]

        cursor.execute(
            "INSERT OR IGNORE INTO Helpdesk (email, position) VALUES (?, ?)",
            (email, position)
        )

        cursor.execute(
            "UPDATE Requests SET request_status = 1, helpdesk_staff_email = ? WHERE request_id = ?",
            (session["user_email"], ticket_id)
        )

        conn.commit()
        flash(f"Staff account for {email} approved successfully.", "success")
    except sql.Error as e:
        conn.rollback()
        flash(f"Error during approval: {e}", "danger")
    finally:
        conn.close()

    return redirect("/helpdesk")

@helpdesk_bp.route("/helpdesk/export/<fmt>")
def export_helpdesk(fmt):
    """Download the current pseudo database view as CSV or XLSX."""
    if not helpdesk_only():
        flash("You must be logged in as helpdesk to export data.", "auth_error")
        return redirect(url_for("index"))

    rows = build_export_rows()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "csv":
        return send_file(
            build_csv_bytes(rows),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"helpdesk_export_{timestamp}.csv",
        )
    if fmt == "xlsx":
        return send_file(
            build_xlsx_bytes(rows),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"helpdesk_export_{timestamp}.xlsx",
        )
    flash("Unsupported export format.", "danger")
    return redirect("/helpdesk")
