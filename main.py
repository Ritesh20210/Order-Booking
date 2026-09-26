import os
import ssl
from datetime import datetime

import flet as ft
import pg8000.dbapi


# ============================================================
# ORDER BOOKING APP - FIXED SINGLE FILE
# ============================================================
# IMPORTANT:
# 1. Put your NEW Neon DB password in NEON_PASSWORD below.
# 2. Do NOT publish this file with your database password.
# 3. Install:
# pip install flet pg8000
# ============================================================

NEON_USER = "neondb_owner"
NEON_PASSWORD = os.getenv("NEON_PASSWORD", "PUT_YOUR_NEW_NEON_PASSWORD_HERE")
NEON_HOST = "ep-dawn-tooth-b356n6lx-pooler.c-4.ap-southeast-1.aws.neon.tech"
NEON_DATABASE = "neondb"
NEON_PORT = 5432

conn = None
db_cursor = None


# ---------------- DATABASE ----------------

def close_db():
    global conn, db_cursor
    try:
        if db_cursor:
            db_cursor.close()
    except Exception:
        pass
    try:
        if conn:
            conn.close()
    except Exception:
        pass
    db_cursor = None
    conn = None


def init_db():
    """Connect to Neon and create required tables."""
    global conn, db_cursor

    # Reuse a working connection.
    if conn is not None and db_cursor is not None:
        try:
            db_cursor.execute("SELECT 1")
            return
        except Exception:
            close_db()

    if not NEON_PASSWORD or NEON_PASSWORD == "PUT_YOUR_NEW_NEON_PASSWORD_HERE":
        raise RuntimeError(
            "Database password is not configured. "
            "Set NEON_PASSWORD or replace PUT_YOUR_NEW_NEON_PASSWORD_HERE."
        )

    ssl_context = ssl.create_default_context()

    # NOTE:
    # This disables certificate verification. It is kept here for
    # compatibility with the original Android setup, but production
    # deployments should use proper certificate verification.
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    conn = pg8000.dbapi.connect(
        user=NEON_USER,
        password=NEON_PASSWORD,
        host=NEON_HOST,
        database=NEON_DATABASE,
        port=NEON_PORT,
        ssl_context=ssl_context,
        timeout=15,
    )
    conn.autocommit = False
    db_cursor = conn.cursor()

    db_cursor.execute(""" CREATE TABLE IF NOT EXISTS users ( id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL, role TEXT NOT NULL, wallet NUMERIC(12,2) DEFAULT 0 ) """)

    db_cursor.execute(""" CREATE TABLE IF NOT EXISTS orders ( id SERIAL PRIMARY KEY, date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, platform TEXT NOT NULL, qty INTEGER NOT NULL CHECK (qty > 0), commission NUMERIC(12,2) NOT NULL CHECK (commission >= 0), boy_name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending' ) """)

    db_cursor.execute(""" CREATE INDEX IF NOT EXISTS idx_orders_boy ON orders (boy_name) """)

    db_cursor.execute(""" CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status) """)

    db_cursor.execute(""" INSERT INTO users (id, name, role, wallet) VALUES (1, 'Admin', 'admin', 0) ON CONFLICT (id) DO NOTHING """)

    db_cursor.execute(""" INSERT INTO users (id, name, role, wallet) VALUES (2, 'Ritesh (Boy)', 'boy', 0) ON CONFLICT (id) DO NOTHING """)

    conn.commit()


def ensure_db():
    """Check connection and reconnect when necessary."""
    global conn, db_cursor

    if conn is None or db_cursor is None:
        init_db()
        return

    try:
        db_cursor.execute("SELECT 1")
    except Exception:
        close_db()
        init_db()


def db_execute(sql, params=(), fetch=False, many=False):
    """Small database helper with automatic reconnect."""
    ensure_db()

    try:
        if many:
            db_cursor.executemany(sql, params)
        else:
            db_cursor.execute(sql, params)

        if fetch:
            return db_cursor.fetchall()

        conn.commit()
        return None

    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

        # One reconnect attempt.
        close_db()
        init_db()

        if many:
            db_cursor.executemany(sql, params)
        else:
            db_cursor.execute(sql, params)

        if fetch:
            return db_cursor.fetchall()

        conn.commit()
        return None


def get_wallet(boy_name):
    rows = db_execute(
        "SELECT wallet FROM users WHERE name=%s",
        (boy_name,),
        fetch=True,
    )
    if rows and rows[0][0] is not None:
        return float(rows[0][0])
    return 0.0


def get_pending(boy_name):
    rows = db_execute(
        """ SELECT COALESCE(SUM(commission), 0) FROM orders WHERE boy_name=%s AND status='Pending' """,
        (boy_name,),
        fetch=True,
    )
    return float(rows[0][0] or 0) if rows else 0.0


# ---------------- APP ----------------

def main(page: ft.Page):

    page.title = "Order Booking App"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = "#ECEFF1"

    try:
        page.theme = ft.Theme(
            color_scheme_seed=ft.Colors.TEAL,
            use_material3=True,
        )
    except Exception:
        pass

    # ---------------- COMMON UI ----------------

    def show_toast(message, color=None):
        if color is None:
            color = ft.Colors.GREEN

        page.snack_bar = ft.SnackBar(
            content=ft.Text(
                message,
                color=ft.Colors.WHITE,
                weight=ft.FontWeight.BOLD,
            ),
            bgcolor=color,
            behavior=ft.SnackBarBehavior.FLOATING,
        )
        page.snack_bar.open = True
        page.update()

    def clear_page():
        page.controls.clear()

    def logout(e=None):
        load_login()

    def error_message(ex):
        text = str(ex)
        if len(text) > 500:
            text = text[:500] + "..."
        return text

    # ---------------- ADMIN ----------------

    def load_admin_view():

        clear_page()

        # ===== ADD ORDER =====

        platform = ft.Dropdown(
            label="Platform",
            filled=True,
            options=[
                ft.dropdown.Option("Myntra"),
                ft.dropdown.Option("Meesho"),
                ft.dropdown.Option("Flipkart"),
                ft.dropdown.Option("Amazon"),
                ft.dropdown.Option("Other"),
            ],
        )

        qty = ft.TextField(
            label="Quantity",
            keyboard_type=ft.KeyboardType.NUMBER,
            filled=True,
        )

        commission = ft.TextField(
            label="Commission (₹)",
            keyboard_type=ft.KeyboardType.NUMBER,
            filled=True,
        )

        boy = ft.Dropdown(
            label="Assign To",
            filled=True,
            options=[
                ft.dropdown.Option("Ritesh (Boy)"),
            ],
        )

        def add_order(e):

            if not all([
                platform.value,
                qty.value,
                commission.value,
                boy.value,
            ]):
                show_toast(
                    "Please fill all fields!",
                    ft.Colors.RED,
                )
                return

            try:
                quantity = int(qty.value)
                comm_value = float(commission.value)

                if quantity <= 0:
                    raise ValueError("Quantity must be greater than 0.")

                if comm_value < 0:
                    raise ValueError("Commission cannot be negative.")

                now = datetime.now()

                db_execute(
                    """ INSERT INTO orders (date, platform, qty, commission, boy_name, status) VALUES (%s,%s,%s,%s,%s,%s) """,
                    (
                        now,
                        platform.value,
                        quantity,
                        comm_value,
                        boy.value,
                        "Pending",
                    ),
                )

                show_toast("Order Added & Synced!")

                platform.value = None
                qty.value = ""
                commission.value = ""
                boy.value = None

                page.update()

                # Refresh order list if it is currently visible.
                render_orders()

            except ValueError as ex:
                show_toast(str(ex), ft.Colors.RED)

            except Exception as ex:
                show_toast(
                    "Could not add order: " + error_message(ex),
                    ft.Colors.RED,
                )

        add_tab_content = ft.Container(
            padding=20,
            content=ft.Column(
                [
                    ft.Text(
                        "Dispatch New Order",
                        size=22,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.TEAL_800,
                    ),
                    ft.Divider(height=15),
                    platform,
                    qty,
                    commission,
                    boy,
                    ft.Container(height=5),
                    ft.ElevatedButton(
                        "Dispatch Order",
                        icon=ft.Icons.SEND,
                        on_click=add_order,
                        bgcolor=ft.Colors.TEAL,
                        color=ft.Colors.WHITE,
                        expand=True,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
            ),
        )

        # ===== LEDGER / ADVANCE =====

        adv_amt = ft.TextField(
            label="Advance Amount (₹)",
            keyboard_type=ft.KeyboardType.NUMBER,
            filled=True,
        )

        boy_adv = ft.Dropdown(
            label="Select Boy",
            filled=True,
            options=[
                ft.dropdown.Option("Ritesh (Boy)"),
            ],
        )

        def give_advance(e):

            if not adv_amt.value or not boy_adv.value:
                show_toast(
                    "Please fill all fields!",
                    ft.Colors.RED,
                )
                return

            try:
                amount = float(adv_amt.value)

                if amount <= 0:
                    raise ValueError("Advance must be greater than 0.")

                db_execute(
                    """ UPDATE users SET wallet = wallet - %s WHERE name=%s """,
                    (amount, boy_adv.value),
                )

                show_toast(
                    f"Advance ₹{amount:.2f} given to {boy_adv.value}!"
                )

                adv_amt.value = ""
                boy_adv.value = None
                page.update()

            except ValueError as ex:
                show_toast(str(ex), ft.Colors.RED)

            except Exception as ex:
                show_toast(
                    "Advance failed: " + error_message(ex),
                    ft.Colors.RED,
                )

        ledger_tab_content = ft.Container(
            padding=20,
            content=ft.Column(
                [
                    ft.Text(
                        "Issue Advance Payment",
                        size=22,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.TEAL_800,
                    ),
                    ft.Divider(height=15),
                    boy_adv,
                    adv_amt,
                    ft.ElevatedButton(
                        "Pay Advance",
                        icon=ft.Icons.PAYMENT,
                        on_click=give_advance,
                        bgcolor=ft.Colors.TEAL,
                        color=ft.Colors.WHITE,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
            ),
        )

        # ===== ORDERS =====

        search_bar = ft.TextField(
            label="Search by ID / Platform",
            prefix_icon=ft.Icons.SEARCH,
            filled=True,
        )

        orders_list = ft.ListView(
            expand=True,
            spacing=10,
            padding=5,
        )

        def mark_status( order_id, new_status, ):

            try:
                # Transaction prevents double payment.
                ensure_db()

                db_cursor.execute(
                    """ SELECT commission, boy_name, status FROM orders WHERE id=%s FOR UPDATE """,
                    (order_id,),
                )

                row = db_cursor.fetchone()

                if not row:
                    conn.rollback()
                    show_toast(
                        "Order not found.",
                        ft.Colors.RED,
                    )
                    return

                amount, boy_name, current_status = row

                if current_status != "Pending":
                    conn.rollback()
                    show_toast(
                        f"Order already {current_status}.",
                        ft.Colors.ORANGE,
                    )
                    render_orders(search_bar.value or "")
                    return

                db_cursor.execute(
                    """ UPDATE orders SET status=%s WHERE id=%s AND status='Pending' """,
                    (new_status, order_id),
                )

                if new_status == "Received":
                    db_cursor.execute(
                        """ UPDATE users SET wallet = wallet + %s WHERE name=%s """,
                        (amount, boy_name),
                    )

                conn.commit()

                if new_status == "Received":
                    show_toast(
                        f"Order #{order_id} received. ₹{float(amount):.2f} added."
                    )
                else:
                    show_toast(
                        f"Order #{order_id} cancelled.",
                        ft.Colors.RED,
                    )

                render_orders(search_bar.value or "")

            except Exception as ex:
                try:
                    conn.rollback()
                except Exception:
                    pass

                show_toast(
                    "Status update failed: " + error_message(ex),
                    ft.Colors.RED,
                )

        def render_orders(search_text=""):

            orders_list.controls.clear()

            try:
                text = (search_text or "").strip()

                db_execute(
                    """ SELECT id, date, platform, qty, commission, boy_name, status FROM orders WHERE platform ILIKE %s OR CAST(id AS TEXT) ILIKE %s ORDER BY id DESC """,
                    (
                        f"%{text}%",
                        f"%{text}%",
                    ),
                    fetch=True,
                )

                rows = db_execute(
                    """ SELECT id, date, platform, qty, commission, boy_name, status FROM orders WHERE platform ILIKE %s OR CAST(id AS TEXT) ILIKE %s ORDER BY id DESC """,
                    (
                        f"%{text}%",
                        f"%{text}%",
                    ),
                    fetch=True,
                )

                if not rows:
                    orders_list.controls.append(
                        ft.Container(
                            padding=30,
                            content=ft.Text(
                                "No orders found.",
                                text_align=ft.TextAlign.CENTER,
                                color=ft.Colors.GREY_600,
                            ),
                        )
                    )

                for row in rows:

                    o_id, o_date, plat, q, com, b_name, stat = row

                    is_pending = stat == "Pending"

                    if stat == "Pending":
                        status_color = ft.Colors.ORANGE
                    elif stat == "Received":
                        status_color = ft.Colors.GREEN
                    else:
                        status_color = ft.Colors.RED

                    try:
                        date_text = o_date.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        date_text = str(o_date)

                    if is_pending:
                        btn_row = ft.Row(
                            [
                                ft.ElevatedButton(
                                    "Receive",
                                    icon=ft.Icons.CHECK,
                                    on_click=lambda e, oid=o_id:
                                        mark_status(oid, "Received"),
                                    bgcolor=ft.Colors.GREEN,
                                    color=ft.Colors.WHITE,
                                    expand=True,
                                ),
                                ft.ElevatedButton(
                                    "Cancel",
                                    icon=ft.Icons.CLOSE,
                                    on_click=lambda e, oid=o_id:
                                        mark_status(oid, "Cancelled"),
                                    bgcolor=ft.Colors.RED,
                                    color=ft.Colors.WHITE,
                                    expand=True,
                                ),
                            ]
                        )
                    else:
                        btn_row = ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE
                                    if stat == "Received"
                                    else ft.Icons.CANCEL,
                                    color=status_color,
                                ),
                                ft.Text(
                                    stat,
                                    color=status_color,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ]
                        )

                    orders_list.controls.append(
                        ft.Card(
                            elevation=3,
                            content=ft.Container(
                                padding=12,
                                border=ft.border.only(
                                    left=ft.BorderSide(
                                        5,
                                        status_color,
                                    )
                                ),
                                content=ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Text(
                                                    f"#{o_id} {plat}",
                                                    weight=ft.FontWeight.BOLD,
                                                    size=17,
                                                    expand=True,
                                                ),
                                                ft.Text(
                                                    date_text,
                                                    color=ft.Colors.GREY,
                                                    size=11,
                                                ),
                                            ]
                                        ),
                                        ft.Divider(height=8),
                                        ft.Row(
                                            [
                                                ft.Text(f"Qty: {q}"),
                                                ft.Text(
                                                    f"Comm: ₹{float(com):.2f}",
                                                    weight=ft.FontWeight.BOLD,
              
