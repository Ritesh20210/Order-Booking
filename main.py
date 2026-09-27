import flet as ft
import pg8000.dbapi
import ssl
from datetime import datetime

# --- CLOUD DATABASE SETUP ---
def init_db():
    # Neon.tech database setup for pure Python (Android compatible)
    ssl_context = ssl.create_default_context()
    
    conn = pg8000.dbapi.connect(
        user="neondb_owner",
        password="npg_EAdGHMcR4Bf5",
        host="ep-dawn-tooth-b356n6lx-pooler.c-4.ap-southeast-1.aws.neon.tech",
        database="neondb",
        port=5432,
        ssl_context=ssl_context
    )
    
    conn.autocommit = True # Ensures data saves immediately to the cloud
    c = conn.cursor()
    
    # Postgres uses SERIAL for auto-increment and ON CONFLICT DO NOTHING
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name TEXT UNIQUE, role TEXT, wallet NUMERIC DEFAULT 0);
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY, 
            date TEXT, platform TEXT, qty INTEGER, commission NUMERIC, boy_name TEXT, status TEXT
        );
    """)
    c.execute("INSERT INTO users (id, name, role) VALUES (1, 'Admin', 'admin') ON CONFLICT (id) DO NOTHING;")
    c.execute("INSERT INTO users (id, name, role) VALUES (2, 'Ritesh (Boy)', 'boy') ON CONFLICT (id) DO NOTHING;")
    
    return conn, c

conn, c = init_db()

# --- MAIN APP LOGIC ---
def main(page: ft.Page):
    page.title = "Order & Commission App"
    page.theme_mode = ft.ThemeMode.LIGHT
    
    page.window.width = 400
    page.window.height = 700

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
        
        # Add Order
        platform = ft.Dropdown(options=[ft.dropdown.Option("Myntra"), ft.dropdown.Option("Meesho"), ft.dropdown.Option("Flipkart")], label="Platform")
        qty = ft.TextField(label="Quantity", keyboard_type=ft.KeyboardType.NUMBER)
        comm = ft.TextField(label="Commission (₹)", keyboard_type=ft.KeyboardType.NUMBER)
        boy = ft.Dropdown(options=[ft.dropdown.Option("Ritesh (Boy)")], label="Assign To")
        
        def add_order(e):
            if platform.value and qty.value and comm.value and boy.value:
                today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                c.execute("INSERT INTO orders (date, platform, qty, commission, boy_name, status) VALUES (%s,%s,%s,%s,%s,%s)", 
                          (today_str, platform.value, int(qty.value), float(comm.value), boy.value, 'Pending'))
                
                page.snack_bar = ft.SnackBar(ft.Text("Order Added & Synced to Cloud!"), open=True)
                page.update()
                load_admin_view()
        
        # Advance
        adv_amt = ft.TextField(label="Advance Amount (₹)", keyboard_type=ft.KeyboardType.NUMBER)
        def give_advance(e):
            if adv_amt.value and boy.value:
                c.execute("UPDATE users SET wallet = wallet - %s WHERE name=%s", (float(adv_amt.value), boy.value))
                load_admin_view()

        # Status Update
        def mark_status(order_id, amount, b_name, new_status):
            c.execute("UPDATE orders SET status=%s WHERE id=%s", (new_status, order_id))
            if new_status == 'Received':
                c.execute("UPDATE users SET wallet = wallet + %s WHERE name=%s", (amount, b_name))
            load_admin_view()

        # Manage Orders (with Search)
        search_bar = ft.TextField(label="Search by ID or Platform...", on_change=lambda e: filter_orders(e.control.value))
        orders_list = ft.ListView(expand=True, spacing=10)
        
        def render_orders(search_text=""):
            orders_list.controls.clear()
            # Postgres ILIKE for case-insensitive search and id::TEXT casting
            query = "SELECT id, date, platform, qty, commission, boy_name, status FROM orders WHERE platform ILIKE %s OR id::TEXT LIKE %s ORDER BY id DESC"
            c.execute(query, (f"%{search_text}%", f"%{search_text}%"))
            for row in c.fetchall():
                o_id, o_date, plat, q, com, b_name, stat = row
                status_color = ft.Colors.ORANGE if stat == 'Pending' else (ft.Colors.GREEN if stat == 'Received' else ft.Colors.RED)
                
                btn_row = ft.Row([
                    ft.Button("Receive", on_click=lambda e, oid=o_id, amt=com, bn=b_name: mark_status(oid, amt, bn, 'Received'), disabled=(stat!='Pending')),
                    ft.Button("Cancel", on_click=lambda e, oid=o_id, amt=com, bn=b_name: mark_status(oid, amt, bn, 'Cancelled'), disabled=(stat!='Pending'), color=ft.Colors.RED)
                ]) if stat == 'Pending' else ft.Text(f"Status: {stat}", color=status_color, weight=ft.FontWeight.BOLD)

                orders_list.controls.append(
                    ft.Card(content=ft.Container(padding=10, content=ft.Column([
                        ft.Text(f"#{o_id} {plat} - {o_date}", weight=ft.FontWeight.BOLD),
                        ft.Text(f"Qty: {q} | Comm: ₹{com} | Assigned to: {b_name}"),
                        btn_row
                    ])))
                )
            page.update()

        def filter_orders(search_text):
            render_orders(search_text)
            
        render_orders()

        # --- REPORTS TAB ---
        start_date = ft.TextField(label="Start Date (YYYY-MM-DD)", width=150)
        end_date = ft.TextField(label="End Date (YYYY-MM-DD)", width=150)
        report_results = ft.ListView(expand=True)
        total_report_comm = ft.Text("Total Cleared: ₹0.00", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN)

        def generate_report(e):
            report_results.controls.clear()
            c.execute("""
                SELECT id, date, platform, commission FROM orders 
                WHERE date >= %s AND date <= %s AND status='Received' 
                ORDER BY date DESC
            """, (start_date.value, end_date.value + " 23:59"))
            
            total = 0.0
            for row in c.fetchall():
                o_id, d, p, com = row
                total += float(com)
                report_results.controls.append(ft.Text(f"{d} - #{o_id} {p}: ₹{com}"))
            
            total_report_comm.value = f"Total Cleared: ₹{total}"
            page.update()

        report_col = ft.Column([
            ft.Row([start_date, end_date]),
            ft.Button("Generate Report", on_click=generate_report),
            ft.Divider(),
            total_report_comm,
            report_results
        ])

        page.add(
            ft.AppBar(title=ft.Text("Admin Dashboard"), bgcolor=ft.Colors.BLUE_200, actions=[ft.IconButton(ft.Icons.LOGOUT, on_click=lambda e: load_login())]),
            ft.Tabs(
                selected_index=0,
                length=4, 
                expand=True,
                content=ft.Column(
                    expand=True,
                    controls=[
                        ft.TabBar(
                            tabs=[
                                ft.Tab(label="Add"),
                                ft.Tab(label="Orders"),
                                ft.Tab(label="Ledger"),
                                ft.Tab(label="Reports"),
                            ]
                        ),
                        ft.TabBarView(
                            expand=True,
                            controls=[
                                ft.Column([platform, qty, comm, boy, ft.Button("Dispatch Order", on_click=add_order)]),
                                ft.Column([search_bar, orders_list]),
                                ft.Column([boy, adv_amt, ft.Button("Issue Advance", on_click=give_advance)]),
                                report_col
                            ]
                        )
                    ]
                )
            )
        )

    # --- ORDER BOY VIEW ---
    def load_boy_view(boy_name="Ritesh (Boy)"):
        page.controls.clear()
        
        wallet = get_wallet(boy_name)
        pending = get_pending(boy_name)

        stats = ft.Row([
            ft.Container(content=ft.Column([ft.Text("Cleared Wallet"), ft.Text(f"₹{wallet}", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN)]), padding=10, bgcolor=ft.Colors.GREEN_50, border_radius=10, expand=True),
            ft.Container(content=ft.Column([ft.Text("Pending Comm."), ft.Text(f"₹{pending}", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE)]), padding=10, bgcolor=ft.Colors.ORANGE_50, border_radius=10, expand=True),
        ])

        orders_list = ft.ListView(expand=True, spacing=10)
        c.execute("SELECT id, date, platform, qty, commission, status FROM orders WHERE boy_name=%s ORDER BY id DESC", (boy_name,))
        for row in c.fetchall():
            o_id, o_date, plat, q, com, stat = row
            status_color = ft.Colors.ORANGE if stat == 'Pending' else (ft.Colors.GREEN if stat == 'Received' else ft.Colors.RED)
            orders_list.controls.append(
                ft.Card(content=ft.Container(padding=10, content=ft.Column([
                    ft.Text(f"#{o_id} {plat} - {o_date}", weight=ft.FontWeight.BOLD),
                    ft.Text(f"Qty: {q} | Commission: ₹{com} | Status: {stat}", color=status_color)
                ])))
            )

        page.add(
            ft.AppBar(title=ft.Text(f"My Orders"), bgcolor=ft.Colors.GREEN_200, actions=[ft.IconButton(ft.Icons.LOGOUT, on_click=lambda e: load_login())]),
            stats,
            ft.Divider(),
            ft.Text("Order Feed:", weight=ft.FontWeight.BOLD),
            orders_list
        )

    # --- AUTO-LOGIN VIEW ---
    def load_login():
        page.controls.clear()
        
        def check_pin(e):
            pin = e.control.value
            if pin == "26":          
                load_boy_view()
            elif pin == "99":        
                load_admin_view()

        pin_input = ft.TextField(
            label="Enter PIN",
            password=True,
            can_reveal_password=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            text_align=ft.TextAlign.CENTER,
            width=200,
            on_change=check_pin
        )

        page.add(
            ft.Column([
                ft.Icon(ft.Icons.LOCK, size=60, color=ft.Colors.BLUE_GREY),
                ft.Text("Enter Passcode", size=24, weight=ft.FontWeight.BOLD),
                pin_input
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
        )
        pin_input.focus()

    load_login()

ft.run(main)
