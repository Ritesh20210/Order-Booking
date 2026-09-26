import flet as ft
import pg8000.dbapi
import ssl
from datetime import datetime

# Global Database Variables
conn = None
c = None

def main(page: ft.Page):
    # --- APP CONFIGURATION ---
    page.title = "Order & Commission App"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ft.colors.TEAL, use_material3=True)
    page.padding = 0
    page.bgcolor = ft.colors.BLUE_GREY_50

    # --- VIBRATION (HAPTIC FEEDBACK) ---
    haptic = ft.HapticFeedback()
    page.overlay.append(haptic)

    def trigger_success_notification():
        haptic.heavy_impact()

    def show_toast(message, color=ft.colors.GREEN):
        page.snack_bar = ft.SnackBar(
            ft.Text(message, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD), 
            bgcolor=color, 
            behavior=ft.SnackBarBehavior.FLOATING,
            shape=ft.RoundedRectangleBorder(radius=10)
        )
        page.snack_bar.open = True
        page.update()

    # --- HELPER FUNCTIONS ---
    def get_wallet(boy_name):
        c.execute("SELECT wallet FROM users WHERE name=%s", (boy_name,))
        res = c.fetchone()
        return float(res[0]) if res and res[0] else 0.0

    def get_pending(boy_name):
        c.execute("SELECT SUM(commission) FROM orders WHERE boy_name=%s AND status='Pending'", (boy_name,))
        res = c.fetchone()
        return float(res[0]) if res and res[0] else 0.0

    # --- ADMIN VIEW ---
    def load_admin_view():
        page.controls.clear()
        
        platform = ft.Dropdown(options=[ft.dropdown.Option("Myntra"), ft.dropdown.Option("Meesho"), ft.dropdown.Option("Flipkart")], label="Platform", filled=True)
        qty = ft.TextField(label="Quantity", keyboard_type=ft.KeyboardType.NUMBER, prefix_icon=ft.icons.NUMBERS, filled=True)
        comm = ft.TextField(label="Commission (₹)", keyboard_type=ft.KeyboardType.NUMBER, prefix_icon=ft.icons.CURRENCY_RUPEE, filled=True)
        boy = ft.Dropdown(options=[ft.dropdown.Option("Ritesh (Boy)")], label="Assign To", filled=True)
        
        def add_order(e):
            if platform.value and qty.value and comm.value and boy.value:
                today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                c.execute("INSERT INTO orders (date, platform, qty, commission, boy_name, status) VALUES (%s,%s,%s,%s,%s,%s)", 
                          (today_str, platform.value, int(qty.value), float(comm.value), boy.value, 'Pending'))
                trigger_success_notification()
                show_toast("Order Added & Synced to Cloud!")
                platform.value = qty.value = comm.value = boy.value = None
                load_admin_view()
            else:
                show_toast("Please fill all fields!", ft.colors.RED)

        add_tab_content = ft.Container(
            padding=20,
            content=ft.Column([
                ft.Text("Dispatch New Order", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.TEAL_800),
                ft.Divider(height=20, color=ft.colors.TRANSPARENT),
                platform, qty, comm, boy,
                ft.Container(height=10),
                ft.ElevatedButton("Dispatch Order", icon=ft.icons.SEND, on_click=add_order, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=15), expand=True, bgcolor=ft.colors.TEAL, color=ft.colors.WHITE)
            ])
        )
        
        adv_amt = ft.TextField(label="Advance Amount (₹)", keyboard_type=ft.KeyboardType.NUMBER, prefix_icon=ft.icons.MONEY, filled=True)
        boy_adv = ft.Dropdown(options=[ft.dropdown.Option("Ritesh (Boy)")], label="Select Boy", filled=True)
        
        def give_advance(e):
            if adv_amt.value and boy_adv.value:
                c.execute("UPDATE users SET wallet = wallet - %s WHERE name=%s", (float(adv_amt.value), boy_adv.value))
                trigger_success_notification()
                show_toast(f"Advance ₹{adv_amt.value} given to {boy_adv.value}!")
                load_admin_view()

        ledger_tab_content = ft.Container(
            padding=20,
            content=ft.Column([
                ft.Text("Issue Advance Payment", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.TEAL_800),
                ft.Divider(height=20, color=ft.colors.TRANSPARENT),
                boy_adv, adv_amt,
                ft.Container(height=10),
                ft.ElevatedButton("Pay Advance", icon=ft.icons.PAYMENT, on_click=give_advance, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=15), bgcolor=ft.colors.TEAL, color=ft.colors.WHITE)
            ])
        )

        def mark_status(order_id, amount, b_name, new_status):
            c.execute("UPDATE orders SET status=%s WHERE id=%s", (new_status, order_id))
            if new_status == 'Received':
                c.execute("UPDATE users SET wallet = wallet + %s WHERE name=%s", (amount, b_name))
                trigger_success_notification()
                show_toast(f"Order #{order_id} Received!")
            else:
                show_toast(f"Order #{order_id} Cancelled!", ft.colors.RED)
            load_admin_view()

        search_bar = ft.TextField(label="Search by ID or Platform...", prefix_icon=ft.icons.SEARCH, on_change=lambda e: filter_orders(e.control.value), filled=True)
        orders_list = ft.ListView(expand=True, spacing=15, padding=10)
        
        def render_orders(search_text=""):
            orders_list.controls.clear()
            query = "SELECT id, date, platform, qty, commission, boy_name, status FROM orders WHERE platform ILIKE %s OR id::TEXT LIKE %s ORDER BY id DESC"
            c.execute(query, (f"%{search_text}%", f"%{search_text}%"))
            for row in c.fetchall():
                o_id, o_date, plat, q, com, b_name, stat = row
                
                is_pending = stat == 'Pending'
                status_color = ft.colors.ORANGE if is_pending else (ft.colors.GREEN if stat == 'Received' else ft.colors.RED)
                status_icon = ft.icons.HOURGLASS_EMPTY if is_pending else (ft.icons.CHECK_CIRCLE if stat == 'Received' else ft.icons.CANCEL)

                btn_row = ft.Row([
                    ft.ElevatedButton("Receive", icon=ft.icons.CHECK, on_click=lambda e, oid=o_id, amt=com, bn=b_name: mark_status(oid, amt, bn, 'Received'), bgcolor=ft.colors.GREEN, color=ft.colors.WHITE, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))),
                    ft.ElevatedButton("Cancel", icon=ft.icons.CLOSE, on_click=lambda e, oid=o_id, amt=com, bn=b_name: mark_status(oid, amt, bn, 'Cancelled'), bgcolor=ft.colors.RED, color=ft.colors.WHITE, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
                ]) if is_pending else ft.Row([ft.Icon(status_icon, color=status_color), ft.Text(f"{stat}", color=status_color, weight=ft.FontWeight.BOLD, size=16)])

                orders_list.controls.append(
                    ft.Card(
                        elevation=4,
                        shape=ft.RoundedRectangleBorder(radius=15),
                        content=ft.Container(
                            padding=15, 
                            border_left=ft.border.BorderSide(6, status_color),
                            content=ft.Column([
                                ft.Row([ft.Text(f"#{o_id} {plat}", weight=ft.FontWeight.BOLD, size=18), ft.Text(o_date, color=ft.colors.GREY, size=12)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Divider(height=10),
                                ft.Row([ft.Text(f"Qty: {q}", size=14), ft.Text(f"Comm: ₹{com}", size=14, weight=ft.FontWeight.BOLD), ft.Text(f"Boy: {b_name}", size=14)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Container(height=5),
                                btn_row
                            ])
                        )
                    )
                )
            page.update()

        def filter_orders(search_text):
            render_orders(search_text)
            
        render_orders()
        orders_tab_content = ft.Container(padding=10, content=ft.Column([search_bar, orders_list], expand=True))

        start_date = ft.TextField(label="Start (YYYY-MM-DD)", width=170, prefix_icon=ft.icons.DATE_RANGE, filled=True)
        end_date = ft.TextField(label="End (YYYY-MM-DD)", width=170, prefix_icon=ft.icons.DATE_RANGE, filled=True)
        report_results = ft.ListView(expand=True, spacing=10)
        total_report_comm = ft.Text("Total Cleared: ₹0.00", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN_700)

        def generate_report(e):
            report_results.controls.clear()
            if not start_date.value or not end_date.value:
                show_toast("Enter both dates!", ft.colors.RED)
                return
                
            c.execute("""
                SELECT id, date, platform, commission FROM orders 
                WHERE date >= %s AND date <= %s AND status='Received' 
                ORDER BY date DESC
            """, (start_date.value, end_date.value + " 23:59"))
            
            total = 0.0
            for row in c.fetchall():
                o_id, d, p, com = row
                total += float(com)
                report_results.controls.append(
                    ft.ListTile(leading=ft.Icon(ft.icons.CHECK_CIRCLE, color=ft.colors.GREEN), title=ft.Text(f"#{o_id} {p}"), subtitle=ft.Text(d), trailing=ft.Text(f"₹{com}", weight=ft.FontWeight.BOLD, size=16))
                )
            
            total_report_comm.value = f"Total Cleared: ₹{total}"
            trigger_success_notification()
            page.update()

        report_tab_content = ft.Container(
            padding=15, 
            content=ft.Column([
                ft.Row([start_date, end_date], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.ElevatedButton("Generate Report", icon=ft.icons.INSERT_CHART, on_click=generate_report, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=15), bgcolor=ft.colors.TEAL, color=ft.colors.WHITE),
                ft.Divider(),
                ft.Container(content=total_report_comm, padding=10, bgcolor=ft.colors.GREEN_50, border_radius=10),
                report_results
            ])
        )

        page.add(
            ft.AppBar(
                title=ft.Text("Admin Hub", weight=ft.FontWeight.BOLD, color=ft.colors.WHITE), 
                bgcolor=ft.colors.TEAL_700, 
                center_title=True,
                actions=[ft.IconButton(ft.icons.LOGOUT, icon_color=ft.colors.WHITE, on_click=lambda e: load_login())]
            ),
            ft.Tabs(
                selected_index=0,
                animation_duration=300,
                expand=True,
                tabs=[
                    ft.Tab(text="Add", icon=ft.icons.ADD_BOX, content=add_tab_content),
                    ft.Tab(text="Orders", icon=ft.icons.LIST_ALT, content=orders_tab_content),
                    ft.Tab(text="Ledger", icon=ft.icons.ACCOUNT_BALANCE_WALLET, content=ledger_tab_content),
                    ft.Tab(text="Reports", icon=ft.icons.BAR_CHART, content=report_tab_content),
                ]
            )
        )

    # --- ORDER BOY VIEW ---
    def load_boy_view(boy_name="Ritesh (Boy)"):
        page.controls.clear()
        
        wallet = get_wallet(boy_name)
        pending = get_pending(boy_name)

        def mark_status_boy(order_id, amount, b_name):
            c.execute("UPDATE orders SET status='Received' WHERE id=%s", (order_id,))
            c.execute("UPDATE users SET wallet = wallet + %s WHERE name=%s", (amount, b_name))
            trigger_success_notification()
            show_toast(f"Commission ₹{amount} Added to Wallet!")
            load_boy_view(b_name)

        stats = ft.Row([
            ft.Card(elevation=6, expand=True, color=ft.colors.GREEN_50, shape=ft.RoundedRectangleBorder(radius=15), content=ft.Container(padding=15, content=ft.Column([ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET, color=ft.colors.GREEN), ft.Text("Cleared", size=12, color=ft.colors.GREY_700), ft.Text(f"₹{wallet}", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN_800)]))),
            ft.Card(elevation=6, expand=True, color=ft.colors.ORANGE_50, shape=ft.RoundedRectangleBorder(radius=15), content=ft.Container(padding=15, content=ft.Column([ft.Icon(ft.icons.PENDING_ACTIONS, color=ft.colors.ORANGE), ft.Text("Pending", size=12, color=ft.colors.GREY_700), ft.Text(f"₹{pending}", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.ORANGE_800)]))),
        ], spacing=15)

        orders_list = ft.ListView(expand=True, spacing=15)
        c.execute("SELECT id, date, platform, qty, commission, status FROM orders WHERE boy_name=%s ORDER BY id DESC", (boy_name,))
        for row in c.fetchall():
            o_id, o_date, plat, q, com, stat = row
            
            is_pending = stat == 'Pending'
            status_color = ft.colors.ORANGE if is_pending else (ft.colors.GREEN if stat == 'Received' else ft.colors.RED)
            status_icon = ft.icons.HOURGLASS_EMPTY if is_pending else (ft.icons.CHECK_CIRCLE if stat == 'Received' else ft.icons.CANCEL)
            
            action_ui = ft.ElevatedButton(
                "Receive Payment", 
                icon=ft.icons.CHECK_CIRCLE, 
                on_click=lambda e, oid=o_id, amt=com, bn=boy_name: mark_status_boy(oid, amt, bn), 
                bgcolor=ft.colors.GREEN, 
                color=ft.colors.WHITE, 
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
            ) if is_pending else ft.Row([ft.Icon(status_icon, color=status_color, size=18), ft.Text(stat, color=status_color, weight=ft.FontWeight.BOLD)])

            orders_list.controls.append(
                ft.Card(
                    elevation=3,
                    shape=ft.RoundedRectangleBorder(radius=12),
                    content=ft.Container(
                        padding=15, border_left=ft.border.BorderSide(5, status_color),
                        content=ft.Column([
                            ft.Row([ft.Text(f"#{o_id} {plat}", weight=ft.FontWeight.BOLD, size=16), ft.Text(o_date, color=ft.colors.GREY, size=12)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Divider(height=10),
                            ft.Row([
                                ft.Text(f"Qty: {q}  |  ₹{com}", weight=ft.FontWeight.W_500),
                                action_ui
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                        ])
                    )
                )
            )

        page.add(
            ft.AppBar(title=ft.Text(f"Hi, Ritesh!", weight=ft.FontWeight.BOLD, color=ft.colors.WHITE), bgcolor=ft.colors.GREEN_700, actions=[ft.IconButton(ft.icons.LOGOUT, icon_color=ft.colors.WHITE, on_click=lambda e: load_login())]),
            ft.Container(
                padding=20,
                expand=True,
                content=ft.Column([
                    stats,
                    ft.Divider(height=30, color=ft.colors.TRANSPARENT),
                    ft.Text("Your Live Orders Feed", size=18, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_GREY_800),
                    orders_list
                ])
            )
        )

    # --- AUTO-LOGIN VIEW ---
    def load_login():
        page.controls.clear()
        
        def check_pin(e):
            pin = e.control.value
            if pin == "26":          
                trigger_success_notification()
                load_boy_view()
            elif pin == "69":        
                trigger_success_notification()
                load_admin_view()
            elif len(pin) > 2:
                show_toast("Invalid PIN!", ft.colors.RED)
                e.control.value = ""
                page.update()

        pin_input = ft.TextField(
            label="Enter 2-Digit PIN",
            password=True,
            can_reveal_password=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            text_align=ft.TextAlign.CENTER,
            width=250,
            prefix_icon=ft.icons.LOCK_OUTLINE,
            filled=True,
            on_change=check_pin,
            max_length=2
        )

        login_card = ft.Card(
            elevation=10,
            shape=ft.RoundedRectangleBorder(radius=20),
            content=ft.Container(
                padding=40,
                width=320,
                bgcolor=ft.colors.WHITE,
                border_radius=20,
                content=ft.Column([
                    ft.Icon(ft.icons.VERIFIED_USER_ROUNDED, size=80, color=ft.colors.TEAL),
                    ft.Text("Secure Login", size=26, weight=ft.FontWeight.BOLD, color=ft.colors.TEAL_900),
                    ft.Text("Enter your pin to continue", size=14, color=ft.colors.GREY_600),
                    ft.Divider(height=30, color=ft.colors.TRANSPARENT),
                    pin_input
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            )
        )

        page.add(
            ft.Container(
                expand=True,
                bgcolor=ft.colors.TEAL_400,
                content=ft.Column([login_card], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            )
        )

    # --- SYNCHRONOUS BOOT SEQUENCE (CRASH-FREE) ---
    loading_ui = ft.Container(
        expand=True,
        bgcolor=ft.colors.BLUE_GREY_50,
        content=ft.Column([
            ft.ProgressRing(color=ft.colors.TEAL),
            ft.Container(height=20),
            ft.Text("Connecting to Secure Cloud...", size=16, weight=ft.FontWeight.BOLD, color=ft.colors.TEAL_800)
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )
    page.add(loading_ui)
    page.update()

    try:
        global conn, c
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        conn = pg8000.dbapi.connect(
            user="neondb_owner",
            password="npg_EAdGHMcR4Bf5",
            host="ep-dawn-tooth-b356n6lx-pooler.c-4.ap-southeast-1.aws.neon.tech",
            database="neondb",
            port=5432,
            ssl_context=ssl_context
        )
        conn.autocommit = True
        c = conn.cursor()
        
        c.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name TEXT UNIQUE, role TEXT, wallet NUMERIC DEFAULT 0);")
        c.execute("CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, date TEXT, platform TEXT, qty INTEGER, commission NUMERIC, boy_name TEXT, status TEXT);")
        c.execute("INSERT INTO users (id, name, role) VALUES (1, 'Admin', 'admin') ON CONFLICT (id) DO NOTHING;")
        c.execute("INSERT INTO users (id, name, role) VALUES (2, 'Ritesh (Boy)', 'boy') ON CONFLICT (id) DO NOTHING;")
        
        load_login()
    except Exception as e:
        page.controls.clear()
        page.add(
            ft.Container(
                expand=True, 
                content=ft.Column([
                    ft.Icon(ft.icons.WIFI_OFF, size=60, color=ft.colors.RED),
                    ft.Text("Database Connection Failed!", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.RED),
                    ft.Text(f"Detail: {e}", text_align=ft.TextAlign.CENTER)
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            )
        )
        page.update()

# SAFE RUNNER FOR ANDROID & PC
if hasattr(ft, 'app'):
    ft.app(target=main)
