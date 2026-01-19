from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime, timedelta, date
from db import get_db_connection
import re

def parse_phones(raw_text):
    """
    Turns the phones input text into a clean list of phone numbers.
    Splits by commas/new lines, trims spaces, and removes duplicates.
    """
    phones = []
    if not raw_text:
        return phones

    raw_text = raw_text.replace(",", "\n")
    for line in raw_text.splitlines():
        p = line.strip()
        if p and p not in phones:
            phones.append(p)
    return phones


def mysql_time_to_timedelta(t):
    """
    Converts a MySQL time value into a Python timedelta.
    Works with timedelta, time-like objects, or strings like 'HH:MM:SS'.
    """
    if t is None:
        return timedelta(0)

    if isinstance(t, timedelta):
        return t


    if hasattr(t, "hour") and hasattr(t, "minute") and hasattr(t, "second"):
        return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)


    s = str(t)
    hh, mm, ss = [int(x) for x in s.split(":")]
    return timedelta(hours=hh, minutes=mm, seconds=ss)

def combine_date_time(d, t):
    """
    Takes a date and a time and returns one full datetime.
    Supports strings and also converts timedelta time to a real time.
    """

    if isinstance(d, str):
        d = date.fromisoformat(d)


    if isinstance(t, timedelta):
        total_seconds = int(t.total_seconds()) % (24 * 3600)
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        t = datetime.strptime(f"{h:02}:{m:02}:{s:02}", "%H:%M:%S").time()

    elif isinstance(t, str):
        if len(t) == 5:
            t = datetime.strptime(t, "%H:%M").time()
        else:
            t = datetime.strptime(t, "%H:%M:%S").time()

    return datetime.combine(d, t)


def overlaps(a_start, a_end, b_start, b_end):
    """
    Checks if two time ranges overlap each other.
    Returns True if they touch in time, otherwise False.
    """
    return a_start < b_end and a_end > b_start


def get_new_flight_session():
    """
    Gets the 'new_flight' data saved in the session.
    Returns None if nothing was saved yet.
    """
    nf = session.get("new_flight")
    if not nf:
        return None
    return nf


def require_manager():
    """
    Checks if the current user in session is a manager.
    Returns True for manager, otherwise False.
    """
    return session.get("user_type") == "manager"


def next_flight_num(cur):
    """
    Creates the next flight number like F600, F601, etc.
    Looks at existing flight numbers in the database and adds 1.
    """
    cur.execute("SELECT FLIGHT_NUM FROM FLIGHT WHERE FLIGHT_NUM LIKE 'F%'")
    rows = cur.fetchall()

    mx = 599
    for r in rows:
        fn = r["FLIGHT_NUM"] if isinstance(r, dict) else r[0]
        m = re.match(r"F(\d+)", str(fn))
        if m:
            mx = max(mx, int(m.group(1)))
    return f"F{mx+1}"



def any_phone_belongs_to_manager(phone_list):
    """
    Checks if any phone in the list belongs to a manager in the database.
    Used to block managers from doing actions as regular users/guests.
    """
    if not phone_list:
        return False

    db = get_db_connection()
    cur = db.cursor()

    for phone in phone_list:
        cur.execute("SELECT 1 FROM MANAGER WHERE PHONE_NUM=%s", (phone,))
        if cur.fetchone():
            cur.close()
            db.close()
            return True

    cur.close()
    db.close()
    return False


def is_valid_name(name):
    """
    Checks if a name contains only English letters.
    Returns True if it is letters only, otherwise False.
    """
    return name.isalpha()



def is_valid_phone(phone):
    """
    Checks if a phone is only digits and has 9 to 10 numbers.
    Returns True if valid, otherwise False.
    """
    return phone.isdigit() and 9 <= len(phone) <= 10


def validate_phone_list(phone_list):
    """
    Validates a list of phone numbers.
    Returns True only if the list is not empty and all phones are valid.
    """
    if len(phone_list) == 0:
        return False
    for phone in phone_list:
        if not is_valid_phone(phone):
            return False
    return True


def is_valid_passport(passport):
    """
    Checks if a passport number is letters/numbers only and length 6–9.
    Returns True if valid, otherwise False.
    """

    return passport.isalnum() and 6 <= len(passport) <= 9


def _to_time(t):
    """
    Converts different time formats into a datetime.time object.
    Supports timedelta, 'HH:MM:SS' strings, or already-a-time values.
    """
    if isinstance(t, timedelta):
        return (datetime.min + t).time()

    if isinstance(t, str):
        return datetime.strptime(t, "%H:%M:%S").time()

    return t


def compute_cancellation_fee(dep_date, dep_time, order_price):
    """
    Calculates cancellation fee based on how close the flight is.
    More than 36 hours: 5% fee. Less/equal 36 hours: full price fee.
    """
    dep_time = _to_time(dep_time)
    dep_dt = datetime.combine(dep_date, dep_time)

    now = datetime.now()
    diff = dep_dt - now

    order_price = float(order_price or 0)


    if diff > timedelta(hours=36):
        fee = round(order_price * 0.05, 2)
        new_price = fee
    else:
        fee = round(order_price, 2)
        new_price = order_price

    return fee, new_price



def dt_from_date_time(d, t):
    """
    Builds a datetime from a date and a time value.
    Uses _to_time() to make sure the time is in the right format.
    """
    return datetime.combine(d, _to_time(t))


def aircraft_available(cur, aircraft_id, cand_start, cand_end):
    """
    Checks if an aircraft is free between two datetimes.
    Returns True only if there is no other non-cancelled flight in that window.
    """
    cur.execute("""
      SELECT 1
      FROM FLIGHT
      WHERE AIRCRAFT_ID=%s
        AND FLIGHT_STATUS <> 'CANCELLED'
        AND TIMESTAMP(DEPARTURE_DATE, DEPARTURE_TIME) < %s
        AND TIMESTAMP(ARRIVAL_DATE, ARRIVAL_TIME) > %s
      LIMIT 1
    """, (aircraft_id, cand_end, cand_start))
    return cur.fetchone() is None


def next_order_id(cur):
    """
    Creates the next order ID like O500, O501, etc.
    Looks at existing orders in the database and adds 1.
    """
    cur.execute("SELECT O_ID FROM F_ORDER WHERE O_ID LIKE 'O%'")
    rows = cur.fetchall()

    mx = 499
    for r in rows:
        oid = r["O_ID"] if isinstance(r, dict) else r[0]
        m = re.match(r"O(\d+)", str(oid))
        if m:
            mx = max(mx, int(m.group(1)))
    return f"O{mx+1}"


def is_valid_hebrew_name(name: str) -> bool:
    """
    Checks if a name is written in Hebrew letters (with spaces/'/- allowed).
    Returns True if it matches Hebrew-only rules, otherwise False.
    """
    return bool(re.fullmatch(r"[א-ת\s'\-]+", name or ""))


def crew_week_rule_ok(cur, role: str, emp_id: str, cand_start: datetime, cand_origin: str) -> bool:
    """
    Checks the “7-day crew rule”.
    If the employee flew in the last 7 days, their last destination must match the new flight origin.
    """
    seven_days_ago = cand_start - timedelta(days=7)

    if role == "pilot":
        join_table = "ASSIGNED_PILOT"
        id_col = "ID_P"
    else:
        join_table = "ASSIGHNED_ATTENDANT"
        id_col = "ID_A"

    cur.execute(f"""
        SELECT
          r.DESTINATION,
          TIMESTAMP(f.ARRIVAL_DATE, f.ARRIVAL_TIME) AS arr_dt
        FROM {join_table} j
        JOIN FLIGHT f ON j.FLIGHT_NUM = f.FLIGHT_NUM
        JOIN ROUTE r ON f.ROUTE_ID = r.ROUTE_ID AND f.DURATION = r.DURATION
        WHERE j.{id_col}=%s
          AND f.FLIGHT_STATUS <> 'CANCELLED'
          AND TIMESTAMP(f.ARRIVAL_DATE, f.ARRIVAL_TIME) <= %s
          AND TIMESTAMP(f.ARRIVAL_DATE, f.ARRIVAL_TIME) >= %s
        ORDER BY arr_dt DESC
        LIMIT 1
    """, (emp_id, cand_start, seven_days_ago))

    last = cur.fetchone()
    if not last:
        return True

    return (last["DESTINATION"] == cand_origin)


def seat_layout(manufacturer: str, size: str):
    """
    Returns the seat columns layout (left/middle/right) by aircraft type.
    Different manufacturers and sizes have different seat letters per row.
    """
    manufacturer = (manufacturer or "").strip()
    size = (size or "").strip().upper()

    if manufacturer == "Boeing":
        if size == "BIG":
            return (["A","B","C"], ["D","E","F","G"], ["H","I","J"])  # 10
        else:
            return (["A","B","C"], [], ["D","E","F"])                # 6

    if manufacturer == "Airbus":
        if size == "BIG":
            return (["A","B","C"], ["D","E","F"], ["G","H","I"])     # 9
        else:
            return (["A","B","C"], [], ["D","E","F"])                # 6

    if manufacturer == "Dassault":
        if size == "BIG":
            return (["A","B","C"], [], ["D","E","F"])                # 6
        else:
            return (["A","B"], [], ["C","D"])                        # 4


    return (["A","B","C"], [], ["D","E","F"])


def create_seats_for_aircraft(cur, aircraft_id, cap_econ, cap_bus):
    """
    Creates seat rows/columns in the SEAT table for an aircraft.
    Uses the aircraft layout and fills business seats first, then economy.
    """
    cur.execute("""
        SELECT MANUFACTURER, SIZE
        FROM AIRCRAFT
        WHERE AIRCRAFT_ID=%s
        LIMIT 1
    """, (aircraft_id,))
    a = cur.fetchone()

    manufacturer = a["MANUFACTURER"] if a and isinstance(a, dict) else (a[0] if a else "")
    size = a["SIZE"] if a and isinstance(a, dict) else (a[1] if a else "SMALL")

    cols_left, cols_mid, cols_right = seat_layout(manufacturer, size)
    cols = cols_left + cols_mid + cols_right
    seats_per_row = len(cols)

    seats = []
    total_bus = int(cap_bus or 0)
    total_econ = int(cap_econ or 0)

    row = 1


    for i in range(total_bus):
        col = cols[i % seats_per_row]
        seats.append((aircraft_id, row, col, "BUSINESS"))
        if (i % seats_per_row) == (seats_per_row - 1):
            row += 1


    for i in range(total_econ):
        col = cols[(total_bus + i) % seats_per_row]
        seats.append((aircraft_id, row, col, "ECONOMY"))
        if ((total_bus + i) % seats_per_row) == (seats_per_row - 1):
            row += 1

    for s in seats:
        cur.execute("""
            INSERT IGNORE INTO SEAT (AIRCRAFT_ID, ROW_NUM, COL_LETTER, CLASS)
            VALUES (%s,%s,%s,%s)
        """, s)

def update_flight_full_status(cur, flight_num: str):
    """
    Updates flight status to FULL when all seats are taken, otherwise ACTIVE.
    Does nothing for CANCELLED or COMPLETED flights.
    """
    cur.execute("""
        SELECT f.FLIGHT_STATUS,
               (a.CAPACITY_ECONOMY + a.CAPACITY_BUSINESS) AS total_seats
        FROM FLIGHT f
        JOIN AIRCRAFT a ON a.AIRCRAFT_ID = f.AIRCRAFT_ID
        WHERE f.FLIGHT_NUM = %s
        LIMIT 1
    """, (flight_num,))
    row = cur.fetchone()

    if not row:
        return

    current_status = row["FLIGHT_STATUS"]
    total_seats = int(row["total_seats"] or 0)


    if current_status in ["CANCELLED", "COMPLETED"]:
        return


    cur.execute("""
        SELECT COUNT(*) AS taken
        FROM ORDER_SEAT os
        JOIN F_ORDER o ON o.O_ID = os.O_ID
        WHERE o.FLIGHT_NUM = %s
          AND o.O_STATUS = 'ACTIVE'
    """, (flight_num,))
    taken = int(cur.fetchone()["taken"] or 0)


    if total_seats > 0 and taken >= total_seats:
        new_status = "FULL"
    else:
        new_status = "ACTIVE"

    if new_status != current_status:
        cur.execute("""
            UPDATE FLIGHT
            SET FLIGHT_STATUS=%s
            WHERE FLIGHT_NUM=%s
        """, (new_status, flight_num))


def auto_complete_flights():
    """
    Automatically marks flights as COMPLETED when arrival time already passed.
    Also marks their ACTIVE orders as COMPLETED.
    """
    db = get_db_connection()
    cur = db.cursor(dictionary=True)
    try:

        cur.execute("""
            UPDATE FLIGHT
            SET FLIGHT_STATUS = 'COMPLETED'
            WHERE FLIGHT_STATUS IN ('ACTIVE','FULL')
              AND TIMESTAMP(ARRIVAL_DATE, ARRIVAL_TIME) <= NOW()
        """)


        cur.execute("""
            UPDATE F_ORDER o
            JOIN FLIGHT f ON f.FLIGHT_NUM = o.FLIGHT_NUM
            SET o.O_STATUS = 'COMPLETED'
            WHERE o.O_STATUS = 'ACTIVE'
              AND f.FLIGHT_STATUS = 'COMPLETED'
        """)

        db.commit()
    finally:
        cur.close()
        db.close()

FOUR_DAYS = timedelta(days=4)

def four_day_availability_ok(existing_flights, cand_dep_dt, cand_arr_dt, cand_origin, cand_dest):
    """
    4-day chaining rule (nearest flights only):
    - No overlap allowed with ANY existing flight.
    - Find the nearest flight BEFORE the candidate (by arrival time) within 4 days:
        its destination must equal cand_origin.
    - Find the nearest flight AFTER the candidate (by departure time) within 4 days:
        its origin must equal cand_dest.
    This fixes chain cases like A->B, B->A, A->C (the nearest-before is B->A).
    """

    for f in existing_flights:
        f_dep = combine_date_time(f["DEPARTURE_DATE"], f["DEPARTURE_TIME"])
        f_arr = combine_date_time(f["ARRIVAL_DATE"], f["ARRIVAL_TIME"])
        if overlaps(cand_dep_dt, cand_arr_dt, f_dep, f_arr):
            return False

    nearest_before = None
    nearest_before_arr = None

    nearest_after = None
    nearest_after_dep = None

    for f in existing_flights:
        f_dep = combine_date_time(f["DEPARTURE_DATE"], f["DEPARTURE_TIME"])
        f_arr = combine_date_time(f["ARRIVAL_DATE"], f["ARRIVAL_TIME"])

        if f_arr <= cand_dep_dt:
            if (cand_dep_dt - f_arr) <= FOUR_DAYS:
                if nearest_before_arr is None or f_arr > nearest_before_arr:
                    nearest_before = f
                    nearest_before_arr = f_arr

        elif f_dep >= cand_arr_dt:
            if (f_dep - cand_arr_dt) <= FOUR_DAYS:
                if nearest_after_dep is None or f_dep < nearest_after_dep:
                    nearest_after = f
                    nearest_after_dep = f_dep

    if nearest_before is not None:
        if nearest_before["DESTINATION"] != cand_origin:
            return False

    if nearest_after is not None:

        if nearest_after["ORIGIN"] != cand_dest:
            return False

    return True

