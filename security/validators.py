"""
Server-side input validation.

Everything here is re-checked on the server even though the HTML forms also
enforce similar rules with maxlength/pattern/required attributes — client-side
validation is only a convenience, since a user (or an attacker) can bypass
the browser entirely and send a request directly. The server is the only
trust boundary that matters.
"""
import re

_WEAK_PINS = {
    "0000", "1111", "2222", "3333", "4444",
    "5555", "6666", "7777", "8888", "9999",
    "1234", "4321",
}


def is_valid_username(username):
    return bool(username) and bool(re.fullmatch(r"[a-zA-Z0-9_]{3,20}", username))


def is_valid_email(email):
    # Deliberately not a full RFC 5322 validator (nothing short of actually
    # sending mail truly proves an address). This just catches obvious
    # typos: something@something.something, no whitespace, reasonable
    # length. Any provider is accepted — Gmail is used to SEND the OTP,
    # the person receiving it can be on any domain.
    if not email or len(email) > 254:
        return False
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def is_valid_password(password):
    if not password or len(password) < 8:
        return False
    has_letter = re.search(r"[A-Za-z]", password) is not None
    has_number = re.search(r"[0-9]", password) is not None
    return has_letter and has_number


def is_valid_pin(pin):
    if not pin or not re.fullmatch(r"\d{4}", pin):
        return False
    return pin not in _WEAK_PINS


def is_positive_int(value, max_value=999):
    try:
        v = int(value)
    except (TypeError, ValueError):
        return False
    return 1 <= v <= max_value


def is_valid_price(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    return 0 < v <= 100000


def is_valid_quantity(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    return v >= 0
