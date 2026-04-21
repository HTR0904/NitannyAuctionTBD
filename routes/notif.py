from flask import Blueprint, render_template, session, redirect, url_for, request
from utils import *

notif_bp = Blueprint('notif', __name__)

@notif_bp.route('/')
def notifications():
    if 'user_email' not in session:
        return redirect(url_for('index'))

    user_email = session['user_email']

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    cursor.execute('''
        SELECT notification_id, content, link, is_read, created_at
        FROM Notifications
        WHERE user_email = ?
        ORDER BY created_at DESC, notification_id DESC
    ''', (user_email,))

    notifs = []
    for row in cursor.fetchall():
        notifs.append({
            'id': row[0],
            'content': row[1],
            'link': row[2],
            'is_read': row[3],
            'created_at': row[4]
        })

    conn.close()

    return render_template('notifications.html',
                           notifications=notifs,
                           user_email=user_email,
                           account_type=session.get('account_type'))


@notif_bp.route('/mark_read/<int:notif_id>', methods=['POST'])
def mark_read(notif_id):
    if 'user_email' not in session:
        return redirect(url_for('index'))

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()
    #only marrk self noti
    cursor.execute(
        "UPDATE Notifications SET is_read = 1 WHERE notification_id = ? AND user_email = ?",
        (notif_id, session['user_email'])
    )
    conn.commit()
    conn.close()
    return redirect(url_for('.notifications'))


@notif_bp.route('/mark_all_read', methods=['POST'])
def mark_all_read():
    if 'user_email' not in session:
        return redirect(url_for('index'))

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE Notifications SET is_read = 1 WHERE user_email = ?",
        (session['user_email'],)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('.notifications'))

@notif_bp.route('/delete/<int:notif_id>', methods=['POST'])
def delete(notif_id):
    if 'user_email' not in session:
        return redirect(url_for('index'))

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM Notifications WHERE notification_id = ? AND user_email = ?",
        (notif_id, session['user_email'])
    )
    conn.commit()
    conn.close()
    return redirect(url_for('.notifications'))

@notif_bp.route('/delete_all', methods=['POST'])
def delete_all():
    if 'user_email' not in session:
        return redirect(url_for('index'))

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM Notifications WHERE user_email = ?",
        (session['user_email'],)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('.notifications'))


@notif_bp.app_context_processor
def inject_notifications_count():
    if 'user_email' in session:
        try:
            db = db_connect()
            cur = db.cursor()

            # Count unread notifications (is_read = 0)
            cur.execute("""
                        SELECT COUNT(*) as count
                        FROM Notifications
                        WHERE user_email = ?
                          AND is_read = 0
                        """, (session['user_email'],))

            result = cur.fetchone()
            db.close()

            return dict(unread_notifs_count=result['count'] if result else 0)
        except Exception as e:
            print(f"Notification Badge Error: {e}")
            return dict(unread_notifs_count=0)

    # If no one is logged in, the count is 0
    return dict(unread_notifs_count=0)