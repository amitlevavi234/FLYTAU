
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime, timedelta, date
from db import get_db_connection
from utils import (
    parse_phones,
    mysql_time_to_timedelta,
    combine_date_time,
    get_new_flight_session,
    require_manager,
    next_flight_num,
    any_phone_belongs_to_manager,
    is_valid_name,
    validate_phone_list,
    is_valid_passport,
    compute_cancellation_fee,
    dt_from_date_time,
    next_order_id,
    is_valid_hebrew_name,
    crew_week_rule_ok,
    create_seats_for_aircraft,
    update_flight_full_status,
    auto_complete_flights,
    four_day_availability_ok,
    seat_layout,
)





app = Flask(__name__)
app.secret_key = "flytau_secret_key"

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False



@app.route("/orders/cancel/<order_id>", methods=["GET", "POST"])

def cancel_order(order_id):
    """
    Cancels an active order (guest or registered) if it belongs to the user.
    Shows a confirmation page, then updates order status and price after cancellation fee.
    """
    user_type = session.get("user_type")
    if user_type not in ["guest", "registered"]:
        flash("Please access orders from My Orders page.", "error")
        return redirect(url_for("flight_search"))

    db = get_db_connection()
    cur = db.cursor(dictionary=True)


    cur.execute("""
        SELECT
          o.O_ID, o.O_STATUS, o.ORDER_PRICE, o.G_MAIL, o.R_MAIL,
          f.DEPARTURE_DATE, f.DEPARTURE_TIME,
          f.FLIGHT_NUM
        FROM F_ORDER o
        JOIN FLIGHT f ON o.FLIGHT_NUM=f.FLIGHT_NUM
        WHERE o.O_ID=%s
        LIMIT 1
    """, (order_id,))
    o = cur.fetchone()

    if not o:
        cur.close(); db.close()
        flash("Order not found.", "error")
        return redirect(url_for("my_orders"))


    if user_type == "registered":
        if o["R_MAIL"] != session.get("email"):
            cur.close(); db.close()
            flash("You cannot cancel this order.", "error")
            return redirect(url_for("my_orders"))
    else:

        guest_email = session.get("guest_order_email")
        if not guest_email or o["G_MAIL"] != guest_email:
            cur.close(); db.close()
            flash("Please search your order again first.", "error")
            return redirect(url_for("my_orders"))

    if o["O_STATUS"] != "ACTIVE":
        cur.close(); db.close()
        flash("Only ACTIVE orders can be cancelled.", "error")
        return redirect(url_for("my_orders"))

    fee, new_price = compute_cancellation_fee(o["DEPARTURE_DATE"], o["DEPARTURE_TIME"], o["ORDER_PRICE"])


    if request.method == "GET":
        cur.close(); db.close()
        return render_template("cancel_confirm.html", order=o, fee=fee, new_price=new_price)


    cur.execute("""
        UPDATE F_ORDER
        SET O_STATUS='CUSTOMER_CANCELLED',
            ORDER_PRICE=%s,
            CANACELATION_DATE_TIME=NOW()
        WHERE O_ID=%s AND O_STATUS='ACTIVE'
    """, (new_price, order_id))
    update_flight_full_status(cur, o["FLIGHT_NUM"])
    db.commit()

    cur.close(); db.close()

    flash(f"Order cancelled. Cancellation fee: {fee:.2f}", "success")
    return redirect(url_for("my_orders"))


@app.route("/")
def home():
    """
    Main entry page of the site.
    Just redirects to the flight search screen.
    """
    return redirect(url_for("flight_search"))



@app.route("/login", methods=["GET", "POST"])

def login():
    """
    Logs in a registered user using email and password.
    If success, saves user info in session and sends them to the registered home page.
    """
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    if not email or not password:
        flash("Incorrect email or password.", "error")
        return redirect(url_for("login"))

    db = get_db_connection()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT * FROM `REGISTER` WHERE R_MAIL=%s AND R_PASSWORD=%s", (email, password))
    user = cur.fetchone()

    cur.close()
    db.close()

    if not user:
        flash("Incorrect email or password.", "error")
        return redirect(url_for("login"))

    session.clear()
    session["user_type"] = "registered"
    session["email"] = user["R_MAIL"]
    session["first_name"] = user["E_FIRST_NAME"]

    return redirect(url_for("registered_home"))



@app.route("/manager/login", methods=["GET", "POST"])
def manager_login():
    """
    Logs in a manager using manager ID and password.
    If success, saves manager info in session and sends them to the manager flight board.
    """
    if request.method == "GET":
        return render_template("manager_login.html")

    manager_id = request.form.get("manager_id", "").strip()
    password = request.form.get("password", "").strip()

    if not manager_id or not password:
        flash("Incorrect ID or password. Please try again.", "error")
        return redirect(url_for("manager_login"))

    db = get_db_connection()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT * FROM MANAGER WHERE ID_M=%s AND M_PASSWORD=%s", (manager_id, password))
    manager = cur.fetchone()

    cur.close()
    db.close()

    if not manager:
        flash("Incorrect ID or password. Please try again.", "error")
        return redirect(url_for("manager_login"))

    session.clear()
    session["user_type"] = "manager"
    session["manager_id"] = manager["ID_M"]
    session["first_name"] = manager.get("H_FIRST_NAME", "Manager")

    return redirect(url_for("manager_flights"))



@app.route("/register/user", methods=["GET", "POST"])
def register_user():
    """
    Creates a new registered user account.
    Validates input (name/phones/passport/birthdate) and inserts user + phones into the database.
    """
    if request.method == "GET":
        return render_template("register_user.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    birth_date = request.form.get("birth_date", "").strip()
    passport_num = request.form.get("passport_num", "").strip()
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    phones_raw = request.form.get("phones", "")
    phones = parse_phones(phones_raw)


    if not all([email, password, birth_date, passport_num, first_name, last_name]) or len(phones) == 0:
        flash("All fields are required (including at least one phone number).", "error")
        return redirect(url_for("register_user"))


    if not is_valid_name(first_name) or not is_valid_name(last_name):
        flash("First and last names must contain letters only.", "error")
        return redirect(url_for("register_user"))


    if not validate_phone_list(phones):
        flash("Phone numbers must contain only digits and be 9–10 digits long.", "error")
        return redirect(url_for("register_user"))


    if not is_valid_passport(passport_num):
        flash("Passport number must contain only letters and digits (6–9 characters).", "error")
        return redirect(url_for("register_user"))


    try:
        birth_date_obj = date.fromisoformat(birth_date)
    except ValueError:
        flash("Invalid birth date.", "error")
        return redirect(url_for("register_user"))

    if birth_date_obj > date.today():
        flash("Birth date cannot be in the future.", "error")
        return redirect(url_for("register_user"))

    if not all([email, password, birth_date, passport_num, first_name, last_name]):
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("register_user"))

    if any_phone_belongs_to_manager(phones):
        flash("One of the phone numbers belongs to a manager. Registration is not allowed.", "error")
        return redirect(url_for("register_user"))

    db = get_db_connection()
    cur = db.cursor()


    cur.execute("SELECT 1 FROM `REGISTER` WHERE R_MAIL=%s", (email,))
    if cur.fetchone():
        cur.close()
        db.close()
        flash("This email is already registered. Please log in.", "error")
        return redirect(url_for("register_user"))


    try:
        cur.execute(
            "INSERT INTO `REGISTER` (R_MAIL, R_PASSWORD, BIRTH_DATE, PASSPORT_NUM, REGITER_DATE, E_FIRST_NAME, E_LAST_NAME) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (email, password, birth_date, passport_num, date.today(), first_name, last_name)
        )
    except Exception:
        cur.close()
        db.close()
        flash("Registration failed. Please try again.", "error")
        return redirect(url_for("register_user"))


    for phone in phones:
        try:
            cur.execute("INSERT INTO REGISTER_PHONE (R_MAIL, PHONE_NUM) VALUES (%s,%s)", (email, phone))
        except Exception:
            pass


    cur.close()
    db.close()


    flash("Registration successful. Please log in.", "success")
    return redirect(url_for("login"))



@app.route("/home/guest")
def guest_home():
    """
    Shows the guest home page.
    If you are not a guest in session, it redirects you to login.
    """
    if session.get("user_type") != "guest":
        return redirect(url_for("login"))
    return render_template("guest_home.html")


@app.route("/home/registered")
def registered_home():
    """
    Shows the registered user home page.
    If you are not logged in as registered, it redirects you to login.
    """
    if session.get("user_type") != "registered":
        return redirect(url_for("login"))
    return render_template("registered_home.html")




@app.route("/flights/search", methods=["GET", "POST"])
def flight_search():
    """
    Shows the flight search page and handles searching flights by filters.
    On POST: validates inputs, checks route exists, then returns matching ACTIVE flights.
    """
    auto_complete_flights()

    if session.get("user_type") == "manager":
        return redirect(url_for("manager_flights"))

    if session.get("user_type") is None:
        session["user_type"] = "guest"
        session["first_name"] = "Guest"
        session.permanent = True

    if request.method == "GET":
        db = get_db_connection()
        cur = db.cursor(dictionary=True)

        cur.execute("""
            SELECT DISTINCT ORIGIN AS city FROM ROUTE
            UNION
            SELECT DISTINCT DESTINATION AS city FROM ROUTE
            ORDER BY city
        """)
        cities = [row["city"] for row in cur.fetchall()]

        cur.close()
        db.close()

        return render_template("flight_results.html", flights=None,
                               passengers=None, origin=None, destination=None, departure_date=None,
                               cities=cities,container_size="wide")


    dep_date = request.form.get("departure_date", "").strip()
    origin = request.form.get("origin", "").strip()
    destination = request.form.get("destination", "").strip()
    passengers_raw = request.form.get("passengers", "").strip()


    if not dep_date or not origin or not destination or not passengers_raw:
        flash("Please fill in all fields to search flights.", "error")
        return redirect(url_for("flight_search"))


    try:
        passengers = int(passengers_raw)
        if passengers <= 0:
            raise ValueError()
    except ValueError:
        flash("Passengers must be a positive number.", "error")
        return redirect(url_for("flight_search"))

    db = get_db_connection()
    cur = db.cursor(dictionary=True)


    cur.execute(
        "SELECT 1 FROM ROUTE WHERE ORIGIN=%s AND DESTINATION=%s LIMIT 1",
        (origin, destination)
    )
    route_exists = cur.fetchone() is not None

    if not route_exists:
        cur.close()
        db.close()
        flash("No flights exist for these routes. Try other destinations.", "error")
        return redirect(url_for("flight_search"))


    cur.execute(
        """
        SELECT
            f.FLIGHT_NUM,
            r.ORIGIN,
            r.DESTINATION,
            f.DEPARTURE_DATE,
            f.DEPARTURE_TIME,
            f.ARRIVAL_DATE,
            f.ARRIVAL_TIME,
            f.DURATION,
            f.ECONOMY_PRICE
        FROM FLIGHT f
        JOIN ROUTE r
          ON f.ROUTE_ID = r.ROUTE_ID AND f.DURATION = r.DURATION
        WHERE f.FLIGHT_STATUS = 'ACTIVE'
          AND r.ORIGIN = %s
          AND r.DESTINATION = %s
          AND f.DEPARTURE_DATE = %s
          AND TIMESTAMP(f.DEPARTURE_DATE, f.DEPARTURE_TIME) > NOW()
        ORDER BY f.DEPARTURE_TIME ASC
        """,
            (origin, destination, dep_date)
    )

    flights = cur.fetchall()


    cur.execute("""
        SELECT DISTINCT ORIGIN AS city FROM ROUTE
        UNION
        SELECT DISTINCT DESTINATION AS city FROM ROUTE
        ORDER BY city
    """)
    cities = [row["city"] for row in cur.fetchall()]

    cur.close()
    db.close()

    if not flights:
        flash("No active flights on this date. Try another date.", "error")
        return redirect(url_for("flight_search"))


    return render_template("flight_results.html",
                           flights=flights,
                           passengers=passengers,
                           origin=origin,
                           destination=destination,
                           departure_date=dep_date,
                           cities=cities,container_size="wide")


@app.route("/flight/<flight_num>/seats", methods=["GET", "POST"])
def seat_select(flight_num):
    """
    Shows seat map for a flight and lets the user pick seats.
    On POST: checks the seats are still free, calculates prices, and saves selection in session.
    """
    if session.get("user_type") not in ["guest", "registered"]:
        session["user_type"] = "guest"
        session["first_name"] = "Guest"
        session.permanent = True


    if request.method == "GET":
        passengers_raw = request.args.get("passengers", "").strip()
        try:
            passengers = int(passengers_raw)
            if passengers <= 0:
                raise ValueError()
        except ValueError:
            flash("Invalid passengers number.", "error")
            return redirect(url_for("flight_search"))

        db = get_db_connection()
        cur = db.cursor(dictionary=True)

        cur.execute("""
            SELECT
              f.FLIGHT_NUM, f.AIRCRAFT_ID, f.FLIGHT_STATUS,
              f.DEPARTURE_DATE, f.DEPARTURE_TIME,
              f.ARRIVAL_DATE, f.ARRIVAL_TIME,
              f.DURATION, f.ECONOMY_PRICE, f.BUSINESS_PRICE,
              a.SIZE AS AIRCRAFT_SIZE,
              a.MANUFACTURER AS MANUFACTURER,
              r.ORIGIN, r.DESTINATION
            FROM FLIGHT f
            JOIN AIRCRAFT a ON f.AIRCRAFT_ID = a.AIRCRAFT_ID
            JOIN ROUTE r ON f.ROUTE_ID = r.ROUTE_ID AND f.DURATION = r.DURATION
            WHERE f.FLIGHT_NUM = %s
        """, (flight_num,))
        flight = cur.fetchone()

        if not flight or flight["FLIGHT_STATUS"] != "ACTIVE":
            cur.close(); db.close()
            flash("This flight is not active.", "error")
            return redirect(url_for("flight_search"))

        aircraft_id = flight["AIRCRAFT_ID"]


        cur.execute("""
            SELECT ROW_NUM, COL_LETTER, CLASS
            FROM SEAT
            WHERE AIRCRAFT_ID=%s
            ORDER BY ROW_NUM, COL_LETTER
        """, (aircraft_id,))
        seats = cur.fetchall()

        if not seats:
            cur.execute("""
                SELECT CAPACITY_ECONOMY, CAPACITY_BUSINESS
                FROM AIRCRAFT
                WHERE AIRCRAFT_ID=%s
                LIMIT 1
            """, (aircraft_id,))
            a = cur.fetchone()

            if a:
                create_seats_for_aircraft(
                    cur,
                    aircraft_id,
                    int(a["CAPACITY_ECONOMY"] or 0),
                    int(a["CAPACITY_BUSINESS"] or 0)
                )
                db.commit()


                cur.execute("""
                    SELECT ROW_NUM, COL_LETTER, CLASS
                    FROM SEAT
                    WHERE AIRCRAFT_ID=%s
                    ORDER BY ROW_NUM, COL_LETTER
                """, (aircraft_id,))
                seats = cur.fetchall()

        rows_map = {}
        for s in seats:
            r = s["ROW_NUM"]
            c = s["COL_LETTER"]
            rows_map.setdefault(r, {})[c] = s["CLASS"]

        row_numbers = sorted(rows_map.keys())
        cols_left, cols_mid, cols_right = seat_layout(flight["MANUFACTURER"], flight["AIRCRAFT_SIZE"])


        cur.execute("""
            SELECT os.ROW_NUM, os.COL_LETTER
            FROM ORDER_SEAT os
            JOIN F_ORDER o ON os.O_ID = o.O_ID
            WHERE o.FLIGHT_NUM=%s AND o.O_STATUS='ACTIVE'
        """, (flight_num,))
        occupied = set((x["ROW_NUM"], x["COL_LETTER"]) for x in cur.fetchall())

        cur.close(); db.close()


        session["passengers"] = passengers
        session["selected_flight_num"] = flight_num
        session.modified = True

        return render_template(
            "seat_select.html",
            flight=flight,
            rows_map=rows_map,
            row_numbers=row_numbers,
            cols_left=cols_left,
            cols_mid=cols_mid,
            cols_right=cols_right,
            occupied=occupied,
            passengers=passengers
        )


    selected = request.form.getlist("seat")
    passengers = int(session.get("passengers", 0))

    if passengers <= 0:
        flash("Session expired. Please search again.", "error")
        return redirect(url_for("flight_search"))

    if len(selected) != passengers:
        flash(f"You must select exactly {passengers} seats.", "error")
        return redirect(url_for("seat_select", flight_num=flight_num, passengers=passengers))

    db = get_db_connection()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT AIRCRAFT_ID, ECONOMY_PRICE, BUSINESS_PRICE FROM FLIGHT WHERE FLIGHT_NUM=%s", (flight_num,))
    f = cur.fetchone()
    if not f:
        cur.close(); db.close()
        flash("Flight not found.", "error")
        return redirect(url_for("flight_search"))

    aircraft_id = f["AIRCRAFT_ID"]
    econ_price = float(f["ECONOMY_PRICE"] or 0)
    bus_price = float(f["BUSINESS_PRICE"] or 0)


    cur.execute("""
        SELECT os.ROW_NUM, os.COL_LETTER
        FROM ORDER_SEAT os
        JOIN F_ORDER o ON os.O_ID = o.O_ID
        WHERE o.FLIGHT_NUM=%s AND o.O_STATUS='ACTIVE'
    """, (flight_num,))
    occupied_now = set((x["ROW_NUM"], x["COL_LETTER"]) for x in cur.fetchall())

    seat_details = []
    total_price = 0.0

    for seat_code in selected:
        seat_code = seat_code.strip().upper()
        row_num = int(seat_code[:-1])
        col = seat_code[-1]

        if (row_num, col) in occupied_now:
            cur.close(); db.close()
            flash("One of the selected seats was just taken. Please choose again.", "error")
            return redirect(url_for("seat_select", flight_num=flight_num, passengers=passengers))

        cur.execute("""
            SELECT CLASS FROM SEAT
            WHERE AIRCRAFT_ID=%s AND ROW_NUM=%s AND COL_LETTER=%s
        """, (aircraft_id, row_num, col))
        srow = cur.fetchone()
        if not srow:
            cur.close(); db.close()
            flash("Invalid seat selection.", "error")
            return redirect(url_for("seat_select", flight_num=flight_num, passengers=passengers))

        seat_class = srow["CLASS"]
        price = bus_price if seat_class == "BUSINESS" else econ_price
        total_price += price

        seat_details.append({"code": seat_code, "row": row_num, "col": col, "class": seat_class, "price": price})

    cur.close(); db.close()


    session["selected_aircraft_id"] = aircraft_id
    session["selected_seats"] = [x["code"] for x in seat_details]
    session["selected_flight_num"] = flight_num
    session["passengers"] = passengers
    session.modified = True

    return redirect(url_for("checkout"))



@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    """
    Final step to create an order after choosing seats.
    Collects passenger details (guest or registered), creates the order + seats, then shows success page.
    """
    if session.get("user_type") not in ["guest", "registered"]:
        session["user_type"] = "guest"
        session["first_name"] = "Guest"

    flight_num = session.get("selected_flight_num")
    passengers = session.get("passengers")
    selected_codes = session.get("selected_seats") or []
    aircraft_id = session.get("selected_aircraft_id")
    total_price = session.get("selected_total_price")


    if not flight_num or not passengers or not selected_codes or not aircraft_id:
        flash("No flight/seat selection found. Please search again.", "error")
        return redirect(url_for("flight_search"))


    if total_price is None:
        db_tmp = get_db_connection()
        cur_tmp = db_tmp.cursor(dictionary=True)

        cur_tmp.execute(
            "SELECT ECONOMY_PRICE, BUSINESS_PRICE FROM FLIGHT WHERE FLIGHT_NUM=%s",
            (flight_num,)
        )
        f = cur_tmp.fetchone()
        if not f:
            cur_tmp.close(); db_tmp.close()
            flash("Flight not found.", "error")
            return redirect(url_for("flight_search"))

        econ = float(f["ECONOMY_PRICE"] or 0)
        bus = float(f["BUSINESS_PRICE"] or 0)

        total = 0.0
        for code in selected_codes:
            code = code.strip().upper()
            row_num = int(code[:-1])
            col = code[-1]

            cur_tmp.execute("""
                SELECT CLASS FROM SEAT
                WHERE AIRCRAFT_ID=%s AND ROW_NUM=%s AND COL_LETTER=%s
            """, (aircraft_id, row_num, col))
            s = cur_tmp.fetchone()
            seat_class = s["CLASS"] if s else "ECONOMY"

            total += (bus if seat_class == "BUSINESS" else econ)

        cur_tmp.close(); db_tmp.close()

        total_price = float(total)
        session["selected_total_price"] = total_price
        session.modified = True


    try:
        total_price = float(total_price)
    except Exception:
        flash("Price calculation failed. Please choose seats again.", "error")
        return redirect(url_for("seat_select", flight_num=flight_num, passengers=passengers))


    db = None
    cur = None
    try:

        db = get_db_connection()
        cur = db.cursor(dictionary=True)


        cur.execute(
            """
            SELECT
              f.FLIGHT_NUM, f.DEPARTURE_DATE, f.DEPARTURE_TIME,
              r.ORIGIN, r.DESTINATION
            FROM FLIGHT f
            JOIN ROUTE r ON f.ROUTE_ID = r.ROUTE_ID AND f.DURATION = r.DURATION
            WHERE f.FLIGHT_NUM=%s
            """,
            (flight_num,)
        )
        flight = cur.fetchone()
        if not flight:
            flash("Flight not found.", "error")
            return redirect(url_for("flight_search"))


        cur.execute("SELECT ECONOMY_PRICE, BUSINESS_PRICE FROM FLIGHT WHERE FLIGHT_NUM=%s", (flight_num,))
        pf = cur.fetchone()
        econ = float(pf["ECONOMY_PRICE"] or 0)
        bus = float(pf["BUSINESS_PRICE"] or 0)


        seat_details = []
        for code in selected_codes:
            code = code.strip().upper()
            row_num = int(code[:-1])
            col = code[-1]

            cur.execute("""
                SELECT CLASS FROM SEAT
                WHERE AIRCRAFT_ID=%s AND ROW_NUM=%s AND COL_LETTER=%s
            """, (aircraft_id, row_num, col))
            srow = cur.fetchone()
            seat_class = srow["CLASS"] if srow else "ECONOMY"

            price = bus if seat_class == "BUSINESS" else econ

            seat_details.append({
                "code": code,
                "row": row_num,
                "col": col,
                "class": seat_class,
                "price": float(price)
            })

        user_type = session.get("user_type")


        auto_email = None
        auto_passport = None
        auto_birth = None
        auto_first = None
        auto_last = None

        if user_type == "registered":
            email = session.get("email")
            cur.execute("""
                SELECT R_MAIL, PASSPORT_NUM, BIRTH_DATE, E_FIRST_NAME, E_LAST_NAME
                FROM `REGISTER`
                WHERE R_MAIL=%s
            """, (email,))
            u = cur.fetchone()
            if u:
                auto_email = u["R_MAIL"]
                auto_passport = u["PASSPORT_NUM"]
                auto_birth = u["BIRTH_DATE"].isoformat() if u["BIRTH_DATE"] else ""
                auto_first = u["E_FIRST_NAME"]
                auto_last = u["E_LAST_NAME"]


        if request.method == "GET":
            return render_template(
                "checkout.html",
                flight=flight,
                passengers=passengers,
                seat_details=seat_details,
                total_price=total_price,
                user_type=user_type,
                auto_email=auto_email,
                auto_passport=auto_passport,
                auto_birth=auto_birth,
                auto_first=auto_first,
                auto_last=auto_last
            )


        if user_type == "guest":
            email = request.form.get("email", "").strip().lower()
            first_name = request.form.get("first_name", "").strip()
            last_name = request.form.get("last_name", "").strip()
            phones_raw = request.form.get("phones", "")
            phones = parse_phones(phones_raw)

            if not email or not first_name or not last_name or len(phones) == 0:
                flash("All guest fields are required (including at least one phone number).", "error")
                return redirect(url_for("checkout"))


            if not is_valid_name(first_name) or not is_valid_name(last_name):
                flash("First and last names must contain letters only.", "error")
                return redirect(url_for("checkout"))

            if not validate_phone_list(phones):
                flash("Phone numbers must contain only digits and be 9–10 digits long.", "error")
                return redirect(url_for("checkout"))

            if any_phone_belongs_to_manager(phones):
                flash("One of the phone numbers belongs to a manager. Managers cannot purchase tickets as guests.",
                      "error")
                return redirect(url_for("checkout"))


            cur.execute("SELECT 1 FROM `REGISTER` WHERE R_MAIL=%s", (email,))
            if cur.fetchone():
                flash("This email belongs to a registered user. Please log in.", "error")
                return redirect(url_for("login"))


            cur.execute("SELECT E_FIRST_NAME, E_LAST_NAME FROM GUEST WHERE G_MAIL=%s", (email,))
            g = cur.fetchone()
            if not g:
                cur.execute(
                    "INSERT INTO GUEST (G_MAIL, E_FIRST_NAME, E_LAST_NAME) VALUES (%s,%s,%s)",
                    (email, first_name, last_name)
                )
            else:
                if g["E_FIRST_NAME"] != first_name or g["E_LAST_NAME"] != last_name:
                    flash("Guest details do not match the email.", "error")
                    return redirect(url_for("checkout"))


            for p in phones:
                cur.execute(
                    "INSERT IGNORE INTO GUEST_PHONE (G_MAIL, PHONE_NUM) VALUES (%s,%s)",
                    (email, p)
                )

            g_mail = email
            r_mail = None
            user_type_enum = "GUEST"

        else:
            r_mail = session.get("email")
            g_mail = None
            user_type_enum = "REGISTERD"


        order_id = next_order_id(cur)
        order_date = date.today()

        cur.execute(
            """
            INSERT INTO F_ORDER (O_ID, FLIGHT_NUM, G_MAIL, R_MAIL, O_STATUS, O_DATE, ORDER_PRICE, USER_TYPE, CANACELATION_DATE_TIME)
            VALUES (%s,%s,%s,%s,'ACTIVE',%s,%s,%s,NULL)
            """,
            (order_id, flight_num, g_mail, r_mail, order_date, total_price, user_type_enum)
        )


        for s in seat_details:
            cur.execute(
                """
                INSERT INTO ORDER_SEAT (O_ID, AIRCRAFT_ID, ROW_NUM, COL_LETTER)
                VALUES (%s,%s,%s,%s)
                """,
                (order_id, aircraft_id, s["row"], s["col"])
            )

        update_flight_full_status(cur, flight_num)
        db.commit()


        session.pop("selected_flight_num", None)
        session.pop("selected_aircraft_id", None)
        session.pop("selected_seats", None)
        session.pop("selected_total_price", None)
        session.pop("passengers", None)

        return render_template("order_success.html", order_id=order_id, flight=flight, total_price=total_price)

    except Exception as e:
        if db:
            db.rollback()
        flash(f"Checkout failed: {e}", "error")
        return redirect(url_for("flight_search"))

    finally:
        if cur:
            cur.close()
        if db:
            db.close()

@app.route("/my_orders", methods=["GET", "POST"])
def my_orders():
    """
    Shows orders page for guests and registered users.
    Guests search by Order ID + Email; registered users see their order list with filters.
    """
    auto_complete_flights()

    user_type = session.get("user_type")
    if user_type not in ["guest", "registered"]:

        session["user_type"] = "guest"
        user_type = "guest"

    db = get_db_connection()
    cur = db.cursor(dictionary=True)


    if user_type == "guest":
        order = None

        if request.method == "POST":
            order_id = request.form.get("order_id", "").strip()
            email = request.form.get("email", "").strip().lower()

            if not order_id or not email:
                flash("Please enter Order ID and Email.", "error")
            else:
                cur.execute("""
                    SELECT
                      o.O_ID, o.O_DATE, o.ORDER_PRICE, o.O_STATUS,
                      o.G_MAIL, g.E_FIRST_NAME, g.E_LAST_NAME,
                      f.FLIGHT_NUM, r.ORIGIN, r.DESTINATION,
                      f.DEPARTURE_DATE, f.DEPARTURE_TIME,
                      f.ARRIVAL_DATE, f.ARRIVAL_TIME
                    FROM F_ORDER o
                    JOIN FLIGHT f ON o.FLIGHT_NUM = f.FLIGHT_NUM
                    JOIN ROUTE r ON f.ROUTE_ID = r.ROUTE_ID AND f.DURATION = r.DURATION
                    JOIN GUEST g ON o.G_MAIL = g.G_MAIL
                    WHERE o.O_ID=%s AND o.G_MAIL=%s AND o.O_STATUS='ACTIVE'
                    LIMIT 1
                """, (order_id, email))
                order = cur.fetchone()

                if order:

                    session["guest_order_email"] = email
                    session.modified = True

                    cur.execute("""
                        SELECT
                          CONCAT(os.ROW_NUM, os.COL_LETTER) AS seat_code,
                          s.CLASS AS seat_class
                        FROM ORDER_SEAT os
                        JOIN SEAT s
                          ON s.AIRCRAFT_ID=os.AIRCRAFT_ID
                         AND s.ROW_NUM=os.ROW_NUM
                         AND s.COL_LETTER=os.COL_LETTER
                        WHERE os.O_ID=%s
                        ORDER BY os.ROW_NUM, os.COL_LETTER
                    """, (order_id,))
                    order["seats"] = cur.fetchall() or []
                else:
                    flash("Active order not found (check Order ID / Email).", "error")


        if order and "seats" not in order:
            order["seats"] = []

        cur.close();
        db.close()
        return render_template("my_orders_guest.html", order=order)


    status = request.args.get("status", "").strip()
    r_mail = session.get("email")


    q = """
        SELECT
          o.O_ID, o.O_DATE, o.ORDER_PRICE, o.O_STATUS,
          reg.E_FIRST_NAME, reg.E_LAST_NAME,
          f.FLIGHT_NUM, rt.ORIGIN, rt.DESTINATION,
          f.DEPARTURE_DATE, f.DEPARTURE_TIME,
          f.ARRIVAL_DATE, f.ARRIVAL_TIME
        FROM F_ORDER o
        JOIN `REGISTER` reg ON o.R_MAIL = reg.R_MAIL
        JOIN FLIGHT f ON o.FLIGHT_NUM = f.FLIGHT_NUM
        JOIN ROUTE rt ON f.ROUTE_ID = rt.ROUTE_ID AND f.DURATION = rt.DURATION
        WHERE o.R_MAIL=%s
    """
    params = [r_mail]

    if status:
        q += " AND o.O_STATUS=%s"
        params.append(status)

    q += " ORDER BY f.DEPARTURE_DATE ASC, f.DEPARTURE_TIME ASC"

    cur.execute(q, tuple(params))
    orders = cur.fetchall()


    for o in orders:
        cur.execute("""
            SELECT CONCAT(os.ROW_NUM, os.COL_LETTER) AS seat_code, s.CLASS AS seat_class
            FROM ORDER_SEAT os
            JOIN SEAT s
              ON s.AIRCRAFT_ID=os.AIRCRAFT_ID
             AND s.ROW_NUM=os.ROW_NUM
             AND s.COL_LETTER=os.COL_LETTER
            WHERE os.O_ID=%s
            ORDER BY os.ROW_NUM, os.COL_LETTER
        """, (o["O_ID"],))
        seats = cur.fetchall()
        o["seats"] = seats
        o["seat_count"] = len(seats)
        o["seat_summary"] = ", ".join([f"{s['seat_code']} ({s['seat_class']})" for s in seats])

    cur.close(); db.close()
    return render_template("my_orders_registered.html", orders=orders, selected_status=status, container_size="wide")



@app.route("/manager/flights", methods=["GET"])
def manager_flights():
    """
    Shows the manager flight board with filters (date/status/origin/destination).
    Pulls flights from the database and displays them in a table.
    """
    if session.get("user_type") != "manager":
        return redirect(url_for("manager_login"))
    auto_complete_flights()

    f_date = request.args.get("date", "").strip()
    f_status = request.args.get("status", "").strip()
    f_origin = request.args.get("origin", "").strip()
    f_dest = request.args.get("destination", "").strip()

    db = get_db_connection()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT DISTINCT ORIGIN AS city FROM ROUTE
        UNION
        SELECT DISTINCT DESTINATION AS city FROM ROUTE
        ORDER BY city
    """)
    cities = [r["city"] for r in cur.fetchall()]

    where = []
    params = []

    if f_date:
        where.append("f.DEPARTURE_DATE=%s")
        params.append(f_date)
    if f_status:
        where.append("f.FLIGHT_STATUS=%s")
        params.append(f_status)
    if f_origin:
        where.append("r.ORIGIN=%s")
        params.append(f_origin)
    if f_dest:
        where.append("r.DESTINATION=%s")
        params.append(f_dest)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    query = f"""
        SELECT
          f.FLIGHT_NUM,
          f.AIRCRAFT_ID,
          a.SIZE AS AIRCRAFT_SIZE,
          f.FLIGHT_STATUS,
          f.DEPARTURE_DATE, f.DEPARTURE_TIME,
          f.ARRIVAL_DATE, f.ARRIVAL_TIME,
          f.ECONOMY_PRICE,
          f.BUSINESS_PRICE,
          r.ORIGIN,
          r.DESTINATION
        FROM FLIGHT f
        JOIN AIRCRAFT a ON f.AIRCRAFT_ID = a.AIRCRAFT_ID
        JOIN ROUTE r ON f.ROUTE_ID = r.ROUTE_ID AND f.DURATION = r.DURATION
        {where_sql}
        ORDER BY f.DEPARTURE_DATE, f.DEPARTURE_TIME
    """

    cur.execute(query, tuple(params))
    flights = cur.fetchall()

    cur.close()
    db.close()

    return render_template(
        "manager_flights.html",
        flights=flights,
        cities=cities,
        f_date=f_date,
        f_status=f_status,
        f_origin=f_origin,
        f_dest=f_dest,
        container_size="wide"
    )


@app.route("/manager/flight/<flight_num>/cancel", methods=["GET", "POST"])
def manager_cancel_flight(flight_num):
    """
    Lets a manager cancel a flight (only if departure is at least 72 hours away).
    Also cancels all ACTIVE orders for that flight as SYSTEM_CANCELLED and sets price to 0.
    """
    if session.get("user_type") != "manager":
        return redirect(url_for("manager_login"))

    db = get_db_connection()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT FLIGHT_NUM, FLIGHT_STATUS, DEPARTURE_DATE, DEPARTURE_TIME
        FROM FLIGHT
        WHERE FLIGHT_NUM=%s
    """, (flight_num,))
    f = cur.fetchone()
    if not f:
        cur.close(); db.close()
        flash("Flight not found.", "error")
        return redirect(url_for("manager_flights"))

    dep_dt = dt_from_date_time(f["DEPARTURE_DATE"], f["DEPARTURE_TIME"])
    now = datetime.now()

    hours_left = (dep_dt - now).total_seconds() / 3600.0

    if request.method == "GET":
        return render_template("manager_cancel_flight.html",
                               flight=f,
                               hours_left=hours_left)


    if hours_left < 72:
        cur.close(); db.close()
        flash("Cannot cancel this flight: departure is in less than 72 hours.", "error")
        return redirect(url_for("manager_flights"))


    cur.execute("UPDATE FLIGHT SET FLIGHT_STATUS='CANCELLED' WHERE FLIGHT_NUM=%s", (flight_num,))


    cur.execute("""
        UPDATE F_ORDER
        SET O_STATUS='SYSTEM_CANCELLED',
            ORDER_PRICE=0,
            CANACELATION_DATE_TIME=NOW()
        WHERE FLIGHT_NUM=%s AND O_STATUS='ACTIVE'
    """, (flight_num,))

    db.commit()
    cur.close(); db.close()

    flash("Flight cancelled. All active orders were set to SYSTEM_CANCELLED with price 0.", "success")
    return redirect(url_for("manager_flights"))


@app.route("/manager/flights/new/step1", methods=["GET", "POST"])
def manager_new_flight_step1():
    """
    Step 1 of creating a new flight: choose route and departure time.
    Finds aircraft options that fit the time window and saves the flight draft in session.
    """
    if not require_manager():
        return redirect(url_for("manager_login"))

    db = get_db_connection()
    cur = db.cursor(dictionary=True)


    cur.execute("""
        SELECT DISTINCT ORIGIN AS city FROM ROUTE
        UNION
        SELECT DISTINCT DESTINATION AS city FROM ROUTE
        ORDER BY city
    """)
    cities = [x["city"] for x in cur.fetchall()]

    if request.method == "GET":
        cur.close(); db.close()
        return render_template("manager_new_flight_step1.html", cities=cities, aircrafts=None)

    dep_date = request.form.get("departure_date", "").strip()
    dep_time = request.form.get("departure_time", "").strip()
    origin = request.form.get("origin", "").strip()
    destination = request.form.get("destination", "").strip()

    if not dep_date or not dep_time or not origin or not destination:
        flash("Please fill all fields.", "error")
        cur.close(); db.close()
        return redirect(url_for("manager_new_flight_step1"))


    if len(dep_time) == 5:
        dep_time = dep_time + ":00"


    cur.execute("""
        SELECT ROUTE_ID, DURATION
        FROM ROUTE
        WHERE ORIGIN=%s AND DESTINATION=%s
        LIMIT 1
    """, (origin, destination))
    route = cur.fetchone()
    if not route:
        flash("Route does not exist in the system.", "error")
        cur.close(); db.close()
        return render_template("manager_new_flight_step1.html", cities=cities, aircrafts=None,
                               departure_date=dep_date, departure_time=dep_time[:5],
                               origin=origin, destination=destination)

    route_duration_td = mysql_time_to_timedelta(route["DURATION"])
    long_flight = route_duration_td > timedelta(hours=6)


    dep_dt = combine_date_time(dep_date, dep_time)
    arr_dt = dep_dt + route_duration_td


    if long_flight:
        cur.execute("SELECT * FROM AIRCRAFT WHERE SIZE='BIG' ORDER BY AIRCRAFT_ID")
    else:
        cur.execute("SELECT * FROM AIRCRAFT ORDER BY AIRCRAFT_ID")
    all_aircrafts = cur.fetchall()


    available = []
    for a in all_aircrafts:
        aircraft_id = a["AIRCRAFT_ID"]

        cur.execute("""
            SELECT
              f.DEPARTURE_DATE, f.DEPARTURE_TIME,
              f.ARRIVAL_DATE, f.ARRIVAL_TIME,
              r.ORIGIN, r.DESTINATION
            FROM FLIGHT f
            JOIN ROUTE r ON f.ROUTE_ID = r.ROUTE_ID AND f.DURATION = r.DURATION
            WHERE f.AIRCRAFT_ID=%s
              AND f.FLIGHT_STATUS <> 'CANCELLED'
        """, (aircraft_id,))
        flights = cur.fetchall()

        ok = four_day_availability_ok(
            flights,
            dep_dt, arr_dt,
            origin, destination
        )

        if ok:
            total_seats = int((a["CAPACITY_ECONOMY"] or 0) + (a["CAPACITY_BUSINESS"] or 0))
            a["TOTAL_SEATS"] = total_seats
            available.append(a)


    session["new_flight"] = {
        "origin": origin,
        "destination": destination,
        "route_id": route["ROUTE_ID"],
        "duration": str(route["DURATION"]),
        "departure_date": dep_date,
        "departure_time": dep_time,
        "arrival_date": arr_dt.date().isoformat(),
        "arrival_time": arr_dt.time().strftime("%H:%M:%S"),
        "is_long": long_flight
    }
    session.modified = True

    cur.close(); db.close()

    if not available:
        flash("No available aircraft for these details. Please try different inputs.", "error")
        return render_template("manager_new_flight_step1.html", cities=cities, aircrafts=[],
                               departure_date=dep_date, departure_time=dep_time[:5],
                               origin=origin, destination=destination)

    return render_template("manager_new_flight_step1.html", cities=cities, aircrafts=available,
                           departure_date=dep_date, departure_time=dep_time[:5],
                           origin=origin, destination=destination)


@app.route("/manager/flights/new/step2/aircraft", methods=["POST"])
def manager_new_flight_step2_aircraft():
    """
    Step 2 of creating a new flight: choose the aircraft.
    Saves the selected aircraft in the session flight draft.
    """
    if session.get("user_type") != "manager":
        return redirect(url_for("manager_login"))

    aircraft_id = request.form.get("aircraft_id")
    if not aircraft_id:
        flash("Please choose an aircraft.", "error")
        return redirect(url_for("manager_new_flight_step1"))


    nf = session.get("new_flight")
    if not nf:
        flash("Session expired. Please start again.", "error")
        return redirect(url_for("manager_new_flight_step1"))

    nf["aircraft_id"] = aircraft_id
    session["new_flight"] = nf
    session.modified = True

    flash(f"Aircraft selected: {aircraft_id}. Next step will be attendants.", "success")
    return redirect(url_for("manager_new_flight_step3_attendants"))


@app.route("/manager/flights/new/step3/attendants", methods=["GET", "POST"])
def manager_new_flight_step3_attendants():
    """
    Step 3 of creating a new flight: choose flight attendants.
    Shows only attendants that are available and pass the scheduling rules.
    """
    if not require_manager():
        return redirect(url_for("manager_login"))

    nf = get_new_flight_session()
    if not nf or not nf.get("aircraft_id"):
        flash("Session expired. Please start again.", "error")
        return redirect(url_for("manager_new_flight_step1"))

    is_long = bool(nf.get("is_long"))
    aircraft_id = nf["aircraft_id"]

    dep_dt = combine_date_time(nf["departure_date"], nf["departure_time"])
    arr_dt = combine_date_time(nf["arrival_date"], nf["arrival_time"])

    required_att = 6 if is_long else 3

    db = get_db_connection()
    cur = db.cursor(dictionary=True)

    if request.method == "POST":
        selected_ids = request.form.getlist("attendant_id")
        if len(selected_ids) != required_att:
            flash(f"You must select exactly {required_att} attendants.", "error")


            if is_long:
                cur.execute("SELECT * FROM FLIGHT_ATTENDANT WHERE IS_QUALIFIED=1 ORDER BY ID_A")
            else:
                cur.execute("SELECT * FROM FLIGHT_ATTENDANT ORDER BY ID_A")
            attendants = cur.fetchall()

            available = []
            for a in attendants:
                aid = a["ID_A"]
                cur.execute("""
                    SELECT
                      f.DEPARTURE_DATE, f.DEPARTURE_TIME,
                      f.ARRIVAL_DATE, f.ARRIVAL_TIME,
                      r.ORIGIN, r.DESTINATION
                    FROM ASSIGHNED_ATTENDANT aa
                    JOIN FLIGHT f ON aa.FLIGHT_NUM = f.FLIGHT_NUM
                    JOIN ROUTE r ON f.ROUTE_ID = r.ROUTE_ID AND f.DURATION = r.DURATION
                    WHERE aa.ID_A=%s
                      AND f.FLIGHT_STATUS <> 'CANCELLED'
                """, (aid,))
                flights = cur.fetchall()

                ok = four_day_availability_ok(flights, dep_dt, arr_dt, nf["origin"], nf["destination"])
                if ok and crew_week_rule_ok(cur, 'attendant', aid, dep_dt, nf['origin']):
                    available.append(a)

            cur.close();
            db.close()


            return render_template(
                "manager_new_flight_step3_attendants.html",
                nf=nf,
                attendants=available,
                required_count=required_att,
                selected_ids=selected_ids
            )

        nf["attendants"] = selected_ids
        session["new_flight"] = nf
        session.modified = True
        cur.close(); db.close()
        return redirect(url_for("manager_new_flight_step4_pilots"))


    if is_long:
        cur.execute("SELECT * FROM FLIGHT_ATTENDANT WHERE IS_QUALIFIED=1 ORDER BY ID_A")
    else:
        cur.execute("SELECT * FROM FLIGHT_ATTENDANT ORDER BY ID_A")
    attendants = cur.fetchall()

    available = []
    for a in attendants:
        aid = a["ID_A"]

        cur.execute("""
            SELECT
              f.DEPARTURE_DATE, f.DEPARTURE_TIME,
              f.ARRIVAL_DATE, f.ARRIVAL_TIME,
              r.ORIGIN, r.DESTINATION
            FROM ASSIGHNED_ATTENDANT aa
            JOIN FLIGHT f ON aa.FLIGHT_NUM = f.FLIGHT_NUM
            JOIN ROUTE r ON f.ROUTE_ID = r.ROUTE_ID AND f.DURATION = r.DURATION
            WHERE aa.ID_A=%s
              AND f.FLIGHT_STATUS <> 'CANCELLED'
        """, (aid,))
        flights = cur.fetchall()

        ok = four_day_availability_ok(
            flights,
            dep_dt, arr_dt,
            nf["origin"], nf["destination"]
        )

        if ok and crew_week_rule_ok(cur, 'attendant', aid, dep_dt, nf['origin']):
            available.append(a)

    cur.close(); db.close()

    if not available:
        flash("No available attendants for this flight window.", "error")
        return redirect(url_for("manager_new_flight_step1"))

    return render_template("manager_new_flight_step3_attendants.html",
                           nf=nf,
                           attendants=available,
                           required_count=required_att)

@app.route("/manager/flights/new/step4/pilots", methods=["GET", "POST"])
def manager_new_flight_step4_pilots():
    """
    Step 4 of creating a new flight: choose pilots.
    Filters pilots by availability and rules, then saves selected pilots in the session flight draft.
    """
    if not require_manager():
        return redirect(url_for("manager_login"))

    nf = get_new_flight_session()
    if not nf or not nf.get("aircraft_id") or not nf.get("attendants"):
        flash("Session expired. Please start again.", "error")
        return redirect(url_for("manager_new_flight_step1"))

    is_long = bool(nf.get("is_long"))
    dep_dt = combine_date_time(nf["departure_date"], nf["departure_time"])
    arr_dt = combine_date_time(nf["arrival_date"], nf["arrival_time"])

    required_p = 3 if is_long else 2

    db = get_db_connection()
    cur = db.cursor(dictionary=True)

  
    def get_available_pilots():
        if is_long:
            cur.execute("SELECT * FROM PILOT WHERE IS_QUALIFIED=1 ORDER BY ID_P")
        else:
            cur.execute("SELECT * FROM PILOT ORDER BY ID_P")
        pilots = cur.fetchall()

        available = []
        for p in pilots:
            pid = p["ID_P"]
            cur.execute("""
                SELECT
                  f.DEPARTURE_DATE, f.DEPARTURE_TIME,
                  f.ARRIVAL_DATE, f.ARRIVAL_TIME,
                  r.ORIGIN, r.DESTINATION
                FROM ASSIGNED_PILOT ap
                JOIN FLIGHT f ON ap.FLIGHT_NUM = f.FLIGHT_NUM
                JOIN ROUTE r ON f.ROUTE_ID = r.ROUTE_ID AND f.DURATION = r.DURATION
                WHERE ap.ID_P=%s
                  AND f.FLIGHT_STATUS <> 'CANCELLED'
            """, (pid,))
            flights = cur.fetchall()

            ok = four_day_availability_ok(
                flights, dep_dt, arr_dt,
                nf["origin"], nf["destination"]
            )

            if ok and crew_week_rule_ok(cur, "pilot", pid, dep_dt, nf["origin"]):
                available.append(p)

        return available


    if request.method == "POST":
        selected_ids = request.form.getlist("pilot_id")

        if len(selected_ids) != required_p:
            flash(f"You must select exactly {required_p} pilots.", "error")
            available = get_available_pilots()
            cur.close(); db.close()
            return render_template(
                "manager_new_flight_step4_pilots.html",
                nf=nf,
                pilots=available,
                required_count=required_p,
                selected_ids=selected_ids
            )

        nf["pilots"] = selected_ids
        session["new_flight"] = nf
        session.modified = True
        cur.close(); db.close()
        return redirect(url_for("manager_new_flight_step5_pricing"))


    available = get_available_pilots()
    cur.close(); db.close()

    if not available:
        flash("No available pilots for this flight window.", "error")
        return redirect(url_for("manager_new_flight_step1"))

    return render_template(
        "manager_new_flight_step4_pilots.html",
        nf=nf,
        pilots=available,
        required_count=required_p,
        selected_ids=[]
    )



@app.route("/manager/flights/new/step5/pricing", methods=["GET", "POST"])
def manager_new_flight_step5_pricing():
    """
    Step 5 of creating a new flight: set ticket prices.
    Validates prices and saves them into the session flight draft.
    """
    if not require_manager():
        return redirect(url_for("manager_login"))

    nf = get_new_flight_session()
    if not nf or not nf.get("aircraft_id") or not nf.get("attendants") or not nf.get("pilots"):
        flash("Session expired. Please start again.", "error")
        return redirect(url_for("manager_new_flight_step1"))

    is_long = bool(nf.get("is_long"))

    if request.method == "GET":
        return render_template("manager_new_flight_step5_pricing.html", nf=nf, is_long=is_long)

    econ_raw = request.form.get("economy_price", "").strip()
    bus_raw = request.form.get("business_price", "").strip()

    try:
        econ_price = float(econ_raw)
        if econ_price <= 0:
            raise ValueError()
    except:
        flash("Economy price must be a positive number.", "error")
        return redirect(url_for("manager_new_flight_step5_pricing"))

    if is_long:
        try:
            bus_price = float(bus_raw)
            if bus_price <= 0:
                raise ValueError()
        except:
            flash("Business price must be a positive number.", "error")
            return redirect(url_for("manager_new_flight_step5_pricing"))
    else:
        bus_price = 0.0

    nf["economy_price"] = econ_price
    nf["business_price"] = bus_price
    session["new_flight"] = nf
    session.modified = True

    return redirect(url_for("manager_new_flight_step6_summary"))


@app.route("/manager/flights/new/step6/summary", methods=["GET", "POST"])
def manager_new_flight_step6_summary():
    """
    Step 6 of creating a new flight: final summary + save.
    Inserts the flight and crew assignments into the database, then clears the session draft.
    """
    if not require_manager():
        return redirect(url_for("manager_login"))

    nf = get_new_flight_session()
    needed = ["aircraft_id", "attendants", "pilots", "economy_price", "business_price",
              "departure_date", "departure_time", "arrival_date", "arrival_time", "route_id", "duration"]
    if not nf or any(k not in nf for k in needed):
        flash("Session expired. Please start again.", "error")
        return redirect(url_for("manager_new_flight_step1"))

    if request.method == "GET":
        return render_template("manager_new_flight_step6_summary.html", nf=nf)

    db = get_db_connection()
    cur = db.cursor(dictionary=True)

    try:
        flight_num = next_flight_num(cur)

        cur.execute("""
            INSERT INTO FLIGHT
            (FLIGHT_NUM, AIRCRAFT_ID, DURATION, ROUTE_ID, FLIGHT_STATUS,
             DEPARTURE_DATE, DEPARTURE_TIME, ARRIVAL_DATE, ARRIVAL_TIME,
             ECONOMY_PRICE, BUSINESS_PRICE)
            VALUES
            (%s,%s,%s,%s,'ACTIVE',%s,%s,%s,%s,%s,%s)
        """, (
            flight_num,
            nf["aircraft_id"],
            nf["duration"],
            nf["route_id"],
            nf["departure_date"],
            nf["departure_time"],
            nf["arrival_date"],
            nf["arrival_time"],
            nf["economy_price"],
            nf["business_price"]
        ))


        for aid in nf["attendants"]:
            cur.execute("INSERT INTO ASSIGHNED_ATTENDANT (ID_A, FLIGHT_NUM) VALUES (%s,%s)", (aid, flight_num))


        for pid in nf["pilots"]:
            cur.execute("INSERT INTO ASSIGNED_PILOT (ID_P, FLIGHT_NUM) VALUES (%s,%s)", (pid, flight_num))

        db.commit()

        session.pop("new_flight", None)
        flash(f"Flight {flight_num} was created successfully.", "success")
        return redirect(url_for("manager_flights"))

    except Exception as e:
        db.rollback()
        flash(f"Failed to add flight: {e}", "error")
        return redirect(url_for("manager_new_flight_step1"))

    finally:
        cur.close()
        db.close()


@app.route("/manager/reports", methods=["GET"])
def manager_reports():
    """
    Shows the manager reports page (5 reports) with filters.
    Runs SQL queries to calculate things like occupancy, revenue, crew hours, cancellations, and utilization.
    """
    if session.get("user_type") != "manager":
        return redirect(url_for("manager_login"))


    def parse_date(s):

        if not s:
            return None
        try:
            return date.fromisoformat(s)
        except Exception:
            return None

    def parse_month(s):

        if not s:
            return None
        try:
            y, m = s.split("-")
            return int(y), int(m)
        except Exception:
            return None

    def month_start_end(ym_from, ym_to):

        if not ym_from and not ym_to:
            return None, None

        if ym_from:
            y, m = ym_from
            start = date(y, m, 1)
        else:
            start = date(1900, 1, 1)

        if ym_to:
            y, m = ym_to

            if m == 12:
                end = date(y, 12, 31)
            else:
                end = date(y, m + 1, 1) - timedelta(days=1)
        else:
            end = date(2100, 12, 31)

        return start, end


    active_report = request.args.get("active_report", "r1").strip() or "r1"
    if active_report not in ["r1", "r2", "r3", "r4", "r5"]:
        active_report = "r1"


    r1_avg = None
    r1_from = request.args.get("r1_from", "").strip()
    r1_to = request.args.get("r1_to", "").strip()

    r2_from = request.args.get("r2_from", "").strip()
    r2_to = request.args.get("r2_to", "").strip()
    r2_class = request.args.get("r2_class", "").strip().upper()
    r2_manufacturer = request.args.get("r2_manufacturer", "").strip()
    r2_size = request.args.get("r2_size", "").strip().upper()
    r2_sort = request.args.get("r2_sort", "DESC").strip().upper()
    r2_rows = []

    r3_role = request.args.get("r3_role", "").strip().upper()
    r3_emp = request.args.get("r3_emp", "").strip()
    r3_flight_type = request.args.get("r3_flight_type", "").strip().upper()
    r3_sort = request.args.get("r3_sort", "DESC").strip().upper()
    r3_rows = []

    r4_from = request.args.get("r4_from", "").strip()
    r4_to = request.args.get("r4_to", "").strip()
    r4_class = request.args.get("r4_class", "").strip().upper()
    r4_sort = request.args.get("r4_sort", "ASC").strip().upper()
    r4_rows = []

    r5_from = request.args.get("r5_from", "").strip()
    r5_to = request.args.get("r5_to", "").strip()
    r5_aircraft = request.args.get("r5_aircraft", "").strip()
    r5_manufacturer = request.args.get("r5_manufacturer", "").strip()
    r5_origin = request.args.get("r5_origin", "").strip()
    r5_destination = request.args.get("r5_destination", "").strip()
    r5_rows = []


    if r2_sort not in ["ASC", "DESC"]:
        r2_sort = "DESC"
    if r3_sort not in ["ASC", "DESC"]:
        r3_sort = "DESC"
    if r4_sort not in ["ASC", "DESC"]:
        r4_sort = "ASC"


    if r2_class not in ["", "ECONOMY", "BUSINESS"]:
        r2_class = ""
    if r2_size not in ["", "SMALL", "BIG"]:
        r2_size = ""
    if r3_role not in ["", "PILOT", "ATTENDANT"]:
        r3_role = ""
    if r3_flight_type not in ["", "SHORT", "LONG"]:
        r3_flight_type = ""
    if r4_class not in ["", "ECONOMY", "BUSINESS"]:
        r4_class = ""


    db = get_db_connection()
    cur = db.cursor(dictionary=True)

    try:

        d1 = parse_date(r1_from)
        d2 = parse_date(r1_to)

        where = ["f.FLIGHT_STATUS = 'COMPLETED'"]
        params = []

        if d1:
            where.append("f.DEPARTURE_DATE >= %s")
            params.append(d1.isoformat())
        if d2:
            where.append("f.DEPARTURE_DATE <= %s")
            params.append(d2.isoformat())

        q1 = f"""
            SELECT AVG(occupied_seats / total_capacity) AS avg_occupancy
            FROM (
                SELECT
                    f.FLIGHT_NUM,
                    COUNT(DISTINCT os.AIRCRAFT_ID, os.ROW_NUM, os.COL_LETTER) AS occupied_seats,
                    (a.CAPACITY_ECONOMY + a.CAPACITY_BUSINESS) AS total_capacity
                FROM FLIGHT f
                JOIN AIRCRAFT a ON a.AIRCRAFT_ID = f.AIRCRAFT_ID
                LEFT JOIN F_ORDER o
                    ON o.FLIGHT_NUM = f.FLIGHT_NUM
                   AND o.O_STATUS = 'COMPLETED'
                LEFT JOIN ORDER_SEAT os
                    ON os.O_ID = o.O_ID
                WHERE {" AND ".join(where)}
                GROUP BY f.FLIGHT_NUM, (a.CAPACITY_ECONOMY + a.CAPACITY_BUSINESS)
            ) AS Occupation_per_flight
        """
        cur.execute(q1, tuple(params))
        row = cur.fetchone()
        r1_avg = row["avg_occupancy"] if row and row["avg_occupancy"] is not None else None



        d1 = parse_date(r2_from)
        d2 = parse_date(r2_to)

        where = ["f.FLIGHT_STATUS <> 'CANCELLED'"]
        params = []

        if d1:
            where.append("f.DEPARTURE_DATE >= %s")
            params.append(d1.isoformat())
        if d2:
            where.append("f.DEPARTURE_DATE <= %s")
            params.append(d2.isoformat())

        if r2_class:
            where.append("s.CLASS = %s")
            params.append(r2_class)

        if r2_manufacturer:
            where.append("a.MANUFACTURER = %s")
            params.append(r2_manufacturer)

        if r2_size:
            where.append("a.SIZE = %s")
            params.append(r2_size)

        q2 = f"""
            SELECT a.SIZE, a.MANUFACTURER, s.CLASS,
                SUM(
                    CASE
                        WHEN o.O_STATUS IN ('ACTIVE','COMPLETED') THEN
                            CASE
                                WHEN s.CLASS = 'ECONOMY'  THEN f.ECONOMY_PRICE
                                WHEN s.CLASS = 'BUSINESS' THEN f.BUSINESS_PRICE
                            END

                        WHEN o.O_STATUS = 'CUSTOMER_CANCELLED'
                             AND o.CANACELATION_DATE_TIME IS NOT NULL
                             AND TIMESTAMPDIFF(
                                    HOUR,
                                    o.CANACELATION_DATE_TIME,
                                    TIMESTAMP(f.DEPARTURE_DATE, f.DEPARTURE_TIME)
                                 ) < 36
                        THEN
                            CASE
                                WHEN s.CLASS = 'ECONOMY'  THEN f.ECONOMY_PRICE
                                WHEN s.CLASS = 'BUSINESS' THEN f.BUSINESS_PRICE
                            END

                        WHEN o.O_STATUS = 'CUSTOMER_CANCELLED'
                             AND o.CANACELATION_DATE_TIME IS NOT NULL
                             AND TIMESTAMPDIFF(
                                    HOUR,
                                    o.CANACELATION_DATE_TIME,
                                    TIMESTAMP(f.DEPARTURE_DATE, f.DEPARTURE_TIME)
                                 ) >= 36
                        THEN
                            (0.05 * o.ORDER_PRICE) *
                            (1.0 / (
                                  SELECT COUNT(*)
                                  FROM ORDER_SEAT os2
                                  WHERE os2.O_ID = o.O_ID
                            ))

                        ELSE 0
                    END
                ) AS revenue
            FROM FLIGHT f
            JOIN AIRCRAFT a ON a.AIRCRAFT_ID = f.AIRCRAFT_ID
            JOIN F_ORDER o ON o.FLIGHT_NUM = f.FLIGHT_NUM
            JOIN ORDER_SEAT os ON os.O_ID = o.O_ID
            JOIN SEAT s
              ON s.AIRCRAFT_ID = os.AIRCRAFT_ID
             AND s.ROW_NUM = os.ROW_NUM
             AND s.COL_LETTER = os.COL_LETTER
            WHERE {" AND ".join(where)}
            GROUP BY a.SIZE, a.MANUFACTURER, s.CLASS
            ORDER BY revenue {r2_sort}, a.SIZE, a.MANUFACTURER, s.CLASS
        """
        cur.execute(q2, tuple(params))
        r2_rows = cur.fetchall()



        where_outer = ["1=1"]
        params_outer = []

        if r3_role:
            where_outer.append("employee_type = %s")
            params_outer.append(r3_role)

        if r3_emp:
            where_outer.append("employee_id = %s")
            params_outer.append(r3_emp)

        if r3_flight_type:
            where_outer.append("flight_type = %s")
            params_outer.append(r3_flight_type)

        q3 = f"""
            SELECT employee_type, employee_id, flight_type,
                   ROUND(SUM(TIME_TO_SEC(duration)) / 3600, 2) AS total_hours
            FROM (
                SELECT
                    'PILOT' AS employee_type,
                    ap.ID_P AS employee_id,
                    CASE WHEN f.DURATION > '06:00:00' THEN 'LONG' ELSE 'SHORT' END AS flight_type,
                    f.DURATION AS duration
                FROM ASSIGNED_PILOT ap
                JOIN FLIGHT f ON f.FLIGHT_NUM = ap.FLIGHT_NUM
                WHERE f.FLIGHT_STATUS = 'COMPLETED'

                UNION ALL

                SELECT
                    'ATTENDANT' AS employee_type,
                    aa.ID_A AS employee_id,
                    CASE WHEN f.DURATION > '06:00:00' THEN 'LONG' ELSE 'SHORT' END AS flight_type,
                    f.DURATION AS duration
                FROM ASSIGHNED_ATTENDANT aa
                JOIN FLIGHT f ON f.FLIGHT_NUM = aa.FLIGHT_NUM
                WHERE f.FLIGHT_STATUS = 'COMPLETED'
            ) AS employee_flight_hours
            WHERE {" AND ".join(where_outer)}
            GROUP BY employee_type, employee_id, flight_type
            ORDER BY total_hours {r3_sort}, employee_type, employee_id
        """
        cur.execute(q3, tuple(params_outer))
        r3_rows = cur.fetchall()



        ym1 = parse_month(r4_from)
        ym2 = parse_month(r4_to)
        start_date, end_date = month_start_end(ym1, ym2)


        base_where = ["1=1"]
        base_params = []

        if start_date:
            base_where.append("o.O_DATE >= %s")
            base_params.append(start_date.isoformat())
        if end_date:
            base_where.append("o.O_DATE <= %s")
            base_params.append(end_date.isoformat())




        if r4_class:
            base_where.append("s.CLASS = %s")
            base_params.append(r4_class)

        q4 = f"""
            SELECT
                yr AS year,
                mo AS month,
                ROUND(100.0 * cancelled_cnt / NULLIF(total_cnt,0), 2) AS cancel_rate_percent
            FROM (
                SELECT
                    YEAR(o.O_DATE) AS yr,
                    MONTH(o.O_DATE) AS mo,
                    COUNT(DISTINCT o.O_ID) AS total_cnt,
                    COUNT(DISTINCT CASE
                        WHEN o.O_STATUS='CUSTOMER_CANCELLED'
                         AND o.CANACELATION_DATE_TIME IS NOT NULL
                        THEN o.O_ID END
                    ) AS cancelled_cnt
                FROM F_ORDER o
                JOIN FLIGHT f ON f.FLIGHT_NUM = o.FLIGHT_NUM
                LEFT JOIN ORDER_SEAT os ON os.O_ID = o.O_ID
                LEFT JOIN SEAT s
                  ON s.AIRCRAFT_ID = os.AIRCRAFT_ID
                 AND s.ROW_NUM = os.ROW_NUM
                 AND s.COL_LETTER = os.COL_LETTER
                WHERE {" AND ".join(base_where)}
                GROUP BY YEAR(o.O_DATE), MONTH(o.O_DATE)
            ) t
            ORDER BY cancel_rate_percent {r4_sort}, year, month
        """
        cur.execute(q4, tuple(base_params))
        r4_rows = cur.fetchall()



        ym1 = parse_month(r5_from)
        ym2 = parse_month(r5_to)
        start_date, end_date = month_start_end(ym1, ym2)


        outer_where = ["1=1"]
        outer_params = []

        if r5_aircraft:
            outer_where.append("x.AIRCRAFT_ID = %s")
            outer_params.append(r5_aircraft)

        if r5_manufacturer:
            outer_where.append("x.MANUFACTURER = %s")
            outer_params.append(r5_manufacturer)

        if r5_origin:
            outer_where.append("(x.origin = %s)")
            outer_params.append(r5_origin)

        if r5_destination:
            outer_where.append("(x.destination = %s)")
            outer_params.append(r5_destination)

        if start_date:
            outer_where.append("STR_TO_DATE(CONCAT(x.year,'-',LPAD(x.month,2,'0'),'-01'), '%Y-%m-%d') >= %s")
            outer_params.append(start_date.isoformat())
        if end_date:
            outer_where.append("STR_TO_DATE(CONCAT(x.year,'-',LPAD(x.month,2,'0'),'-01'), '%Y-%m-%d') <= %s")
            outer_params.append(end_date.isoformat())

        q5 = f"""
            WITH
            years AS (
              SELECT DISTINCT YEAR(DEPARTURE_DATE) AS year
              FROM FLIGHT
            ),
            months AS (
              SELECT 1 AS month UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
              UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8
              UNION ALL SELECT 9 UNION ALL SELECT 10 UNION ALL SELECT 11 UNION ALL SELECT 12
            ),
            skeleton AS (
              SELECT a.AIRCRAFT_ID, a.MANUFACTURER, y.year, m.month
              FROM AIRCRAFT a
              CROSS JOIN years y
              CROSS JOIN months m
            ),
            monthly_flights AS (
              SELECT
                AIRCRAFT_ID,
                YEAR(DEPARTURE_DATE) AS year,
                MONTH(DEPARTURE_DATE) AS month,
                SUM(FLIGHT_STATUS = 'COMPLETED') AS completed_flights,
                SUM(FLIGHT_STATUS = 'CANCELLED') AS cancelled_flights
              FROM FLIGHT
              GROUP BY AIRCRAFT_ID, YEAR(DEPARTURE_DATE), MONTH(DEPARTURE_DATE)
            ),
            dominant_route AS (
              SELECT AIRCRAFT_ID, year, month, origin, destination
              FROM (
                SELECT
                  f.AIRCRAFT_ID,
                  YEAR(f.DEPARTURE_DATE) AS year,
                  MONTH(f.DEPARTURE_DATE) AS month,
                  r.ORIGIN AS origin,
                  r.DESTINATION AS destination,
                  COUNT(*) AS cnt,
                  ROW_NUMBER() OVER (
                    PARTITION BY f.AIRCRAFT_ID, YEAR(f.DEPARTURE_DATE), MONTH(f.DEPARTURE_DATE)
                    ORDER BY COUNT(*) DESC, r.ORIGIN, r.DESTINATION
                  ) AS rn
                FROM FLIGHT f
                JOIN ROUTE r
                  ON r.ROUTE_ID = f.ROUTE_ID AND r.DURATION = f.DURATION
                WHERE f.FLIGHT_STATUS = 'COMPLETED'
                GROUP BY f.AIRCRAFT_ID,
                         YEAR(f.DEPARTURE_DATE),
                         MONTH(f.DEPARTURE_DATE),
                         r.ORIGIN,
                         r.DESTINATION
              ) t
              WHERE rn = 1
            )
            SELECT *
            FROM (
              SELECT
                s.AIRCRAFT_ID,
                s.MANUFACTURER,
                s.year,
                s.month,

                CASE WHEN mf.completed_flights IS NULL THEN 0 ELSE mf.completed_flights END AS completed_flights,
                CASE WHEN mf.cancelled_flights IS NULL THEN 0 ELSE mf.cancelled_flights END AS cancelled_flights,

                ROUND(
                  LEAST(
                    (CASE WHEN mf.completed_flights IS NULL THEN 0 ELSE mf.completed_flights END) / 30.0,
                    1
                  ) * 100,
                  2
                ) AS utilization_percent,

                dr.origin,
                dr.destination
              FROM skeleton s
              LEFT JOIN monthly_flights mf
                ON mf.AIRCRAFT_ID = s.AIRCRAFT_ID
               AND mf.year = s.year
               AND mf.month = s.month
              LEFT JOIN dominant_route dr
                ON dr.AIRCRAFT_ID = s.AIRCRAFT_ID
               AND dr.year = s.year
               AND dr.month = s.month
            ) x
            WHERE {" AND ".join(outer_where)}
            ORDER BY x.AIRCRAFT_ID, x.year, x.month
        """
        cur.execute(q5, tuple(outer_params))
        r5_rows = cur.fetchall()

    finally:
        cur.close()
        db.close()

    return render_template(
        "manager_reports.html",
        container_size="wide",
        active_report=active_report,


        r1_avg=r1_avg,
        r1_from=r1_from,
        r1_to=r1_to,


        r2_from=r2_from,
        r2_to=r2_to,
        r2_class=r2_class if r2_class else "",
        r2_manufacturer=r2_manufacturer,
        r2_size=r2_size if r2_size else "",
        r2_sort=r2_sort,
        r2_rows=r2_rows,


        r3_role=r3_role if r3_role else "",
        r3_emp=r3_emp,
        r3_flight_type=r3_flight_type if r3_flight_type else "",
        r3_sort=r3_sort,
        r3_rows=r3_rows,


        r4_from=r4_from,
        r4_to=r4_to,
        r4_class=r4_class if r4_class else "",
        r4_sort=r4_sort,
        r4_rows=r4_rows,


        r5_from=r5_from,
        r5_to=r5_to,
        r5_aircraft=r5_aircraft,
        r5_manufacturer=r5_manufacturer,
        r5_origin=r5_origin,
        r5_destination=r5_destination,
        r5_rows=r5_rows
    )


@app.route("/manager/staff/new", methods=["GET", "POST"])
def manager_add_staff():
    """
    Adds a new pilot or flight attendant into the system.
    Validates fields and inserts the employee into the correct table.
    """
    if not require_manager():
        return redirect(url_for("manager_login"))

    if request.method == "GET":
        return render_template("manager_add_employee.html", container_size="narrow")

    role = request.form.get("role", "").strip()
    emp_id = request.form.get("emp_id", "").strip()
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    phone = request.form.get("phone", "").strip()
    city = request.form.get("city", "").strip()
    street = request.form.get("street", "").strip()
    house_num = request.form.get("house_num", "").strip()
    start_date = request.form.get("start_date", "").strip()
    qualified_raw = request.form.get("is_qualified", "").strip()


    if not all([role, emp_id, first_name, last_name, phone, city, street, house_num, start_date, qualified_raw]):
        flash("Missing required field. Please fill all fields.", "error")
        return redirect(url_for("manager_add_staff"))


    if role not in ["pilot", "attendant"]:
        flash("Invalid role.", "error")
        return redirect(url_for("manager_add_staff"))


    if not is_valid_hebrew_name(first_name) or not is_valid_hebrew_name(last_name):
        flash("First/Last name must be in Hebrew letters.", "error")
        return redirect(url_for("manager_add_staff"))

    try:
        house_num_int = int(house_num)
    except ValueError:
        flash("House number must be numeric.", "error")
        return redirect(url_for("manager_add_staff"))

    is_qualified = True if qualified_raw.lower() == "yes" else False

    db = get_db_connection()
    cur = db.cursor(dictionary=True)


    if role == "pilot":
        cur.execute("SELECT 1 FROM FLIGHT_ATTENDANT WHERE ID_A=%s", (emp_id,))
        if cur.fetchone():
            cur.close(); db.close()
            flash("This ID already exists as an attendant. One employee cannot have two roles.", "error")
            return redirect(url_for("manager_add_staff"))
    else:
        cur.execute("SELECT 1 FROM PILOT WHERE ID_P=%s", (emp_id,))
        if cur.fetchone():
            cur.close(); db.close()
            flash("This ID already exists as a pilot. One employee cannot have two roles.", "error")
            return redirect(url_for("manager_add_staff"))


    try:
        if role == "pilot":
            cur.execute("""
                INSERT INTO PILOT (ID_P, H_FIRST_NAME, H_LAST_NAME, PHONE_NUM, CITY, STREET, HOUSE_NUM, START_DATE, IS_QUALIFIED)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (emp_id, first_name, last_name, phone, city, street, house_num_int, start_date, is_qualified))
        else:
            cur.execute("""
                INSERT INTO FLIGHT_ATTENDANT (ID_A, H_FIRST_NAME, H_LAST_NAME, PHONE_NUM, CITY, STREET, HOUSE_NUM, START_DATE, IS_QUALIFIED)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (emp_id, first_name, last_name, phone, city, street, house_num_int, start_date, is_qualified))

        db.commit()
    except Exception as e:
        db.rollback()
        cur.close(); db.close()
        flash(f"Failed to add employee: {e}", "error")
        return redirect(url_for("manager_add_staff"))

    cur.close(); db.close()
    flash("Employee added successfully.", "success")
    return redirect(url_for("manager_flights"))


@app.route("/manager/aircraft/new", methods=["GET", "POST"])
def manager_add_aircraft():
    """
    Adds a new aircraft into the system.
    Validates details, inserts into AIRCRAFT, and automatically creates all seats for it.
    """
    if not require_manager():
        return redirect(url_for("manager_login"))

    if request.method == "GET":
        return render_template("manager_add_aircraft.html", container_size="narrow")

    aircraft_id = request.form.get("aircraft_id", "").strip()
    size = request.form.get("size", "").strip()
    manufacturer = request.form.get("manufacturer", "").strip()
    purchase_date = request.form.get("purchase_date", "").strip()
    cap_business = request.form.get("cap_business", "").strip()
    cap_economy = request.form.get("cap_economy", "").strip()

    if not all([aircraft_id, size, manufacturer, purchase_date, cap_economy]):
        flash("All fields are required.", "error")
        return redirect(url_for("manager_add_aircraft"))

    if size == "BIG" and (cap_business is None or cap_business.strip() == ""):
        flash("Business seats are required for BIG aircraft.", "error")
        return redirect(url_for("manager_add_aircraft"))

    if size not in ["BIG", "SMALL"]:
        flash("Invalid aircraft size.", "error")
        return redirect(url_for("manager_add_aircraft"))

    if manufacturer not in ["Boeing", "Airbus", "Dassault"]:
        flash("Invalid manufacturer.", "error")
        return redirect(url_for("manager_add_aircraft"))

    try:
        cap_business_int = int(cap_business)
        cap_economy_int = int(cap_economy)
        if cap_business_int < 0 or cap_economy_int < 0:
            raise ValueError()
    except ValueError:
        flash("Capacities must be non-negative integers.", "error")
        return redirect(url_for("manager_add_aircraft"))


    if size == "SMALL":
        cap_business_int = 0

    db = get_db_connection()
    cur = db.cursor(dictionary=True)

    try:
        cur.execute("""
          INSERT INTO AIRCRAFT (AIRCRAFT_ID, SIZE, MANUFACTURER, PURCHASE_DATE, CAPACITY_BUSINESS, CAPACITY_ECONOMY)
          VALUES (%s,%s,%s,%s,%s,%s)
        """, (aircraft_id, size, manufacturer, purchase_date, cap_business_int, cap_economy_int))

        create_seats_for_aircraft(cur, aircraft_id, cap_economy_int, cap_business_int)

        db.commit()

    except Exception as e:
        db.rollback()
        cur.close(); db.close()
        flash(f"Failed to add aircraft: {e}", "error")
        return redirect(url_for("manager_add_aircraft"))

    cur.close(); db.close()
    flash("Aircraft added successfully.", "success")
    return redirect(url_for("manager_flights"))

@app.route("/logout")
def logout():
    """
    Logs out any user by clearing the session.
    Then sends the user back to the flight search page.
    """
    session.clear()
    return redirect(url_for("flight_search"))

if __name__ == "__main__":
    app.run(debug=True)
