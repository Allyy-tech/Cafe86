"""
Internet connectivity check — the piece that makes "Offline Mode" a real,
observable thing rather than just a line in the documentation.

Important distinction this file exists to demonstrate:

  LOCAL network (Wi-Fi/LAN inside the cafe, between a POS tablet and the
  server this Flask app runs on) is a completely different link than the
  INTERNET (the shop's connection out to the wider web). A local power/ISP
  outage takes down the second without touching the first. Every core POS
  action in this app (ringing up a sale, taking payment, printing a
  receipt) only ever needs the local link, which is why the register can
  keep working straight through an internet outage.

This function checks ONLY the internet link, by attempting a short TCP
connection to a public, highly-available host. It never touches, and is
never touched by, the local Flask/SQLite operations that run the register —
those succeed or fail entirely independently of this check.
"""
import socket


def is_internet_available(host="8.8.8.8", port=53, timeout=1.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
