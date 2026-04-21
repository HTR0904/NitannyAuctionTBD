from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for

from utils import (
    DEFAULT_HELPDESK_EMAIL,
    build_csv_bytes,
    build_export_rows,
    build_xlsx_bytes,
    collect_helpdesk_context,
    create_helpdesk_account,
    create_real_category,
    create_request_ticket,
    get_app_user,
    update_real_user,
    update_request_ticket,
)

helpdesk_bp = Blueprint("helpdesk", __name__)


def helpdesk_only():
    return "user_email" in session and session.get("account_type") == "/helpdesk"


@helpdesk_bp.route("/submit_ticket", methods=["POST"])
def submit_ticket():
    if "user_email" not in session:
        return redirect("/")

    req_type = request.form.get("request_type")
    is_category_form = req_type == "AddCategory"

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
    if not helpdesk_only():
        flash("Please log in to continue.", "auth_error")
        return redirect(url_for("index"))

    context = collect_helpdesk_context()
    context["current_user"] = get_app_user(session["user_email"])
    context["default_helpdesk_email"] = DEFAULT_HELPDESK_EMAIL
    return render_template("helpdesk_home.html", **context)


@helpdesk_bp.route("/helpdesk/create_account", methods=["POST"])
def create_helpdesk_account_route():
    if not helpdesk_only():
        flash("You must be logged in as helpdesk to manage admin tools.", "auth_error")
        return redirect(url_for("index"))

    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "bidder").strip()
    created, message = create_helpdesk_account(full_name, email, password, role)
    flash(message, "success" if created else "danger")
    return redirect("/helpdesk")


@helpdesk_bp.route("/helpdesk/create_category", methods=["POST"])
def create_category():
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
    if not helpdesk_only():
        flash("You must be logged in as helpdesk to update users.", "auth_error")
        return redirect(url_for("index"))

    updated, message = update_real_user(
        request.form.get("user_email", "").strip().lower(),
        request.form.get("full_name", "").strip(),
        request.form.get("role", "").strip(),
    )
    flash(message, "success" if updated else "danger")
    return redirect("/helpdesk")


@helpdesk_bp.route("/helpdesk/update_ticket/<int:ticket_id>", methods=["POST"])
def update_ticket(ticket_id):
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


@helpdesk_bp.route("/helpdesk/export/<fmt>")
def export_helpdesk(fmt):
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
