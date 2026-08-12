# -*- coding: utf-8 -*-
"""
download_adalibieke_ftp.py   (resilient version)
TPDC FTP downloader for the Adalibieke crop-specific N fertilization dataset.
RUN ON YOUR OWN COMPUTER.  Standard library only.

Handles the TPDC server's habits: it often resets the connection at the start of a file
(WinError 10054) and DNS can hiccup. This version reconnects with back-off through ANY
transient error, resumes partial files, and never crashes - just re-run to continue.
Best bandwidth 02:00-10:00 Beijing time (~14:00-22:00 US Eastern).
"""
import ftplib
import os
import time
# run from anywhere: anchor to THIS script folder (A_agricultural_leaching)
import os
try:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))   # this script LIVES IN "2. N_application_rate"
except NameError:
    pass   # cell-by-cell in Spyder: set the working dir to "2. N_application_rate" first

# ===================== settings =====================
HOSTS    = ["ftp2.tpdc.ac.cn", "ftp3.tpdc.ac.cn"]
PORT     = 6201
USERNAME = "download_XXXXXXXX"
PASSWORD = "XXXXXXXX"
REMOTE_DIR = "/"
LOCAL_DIR  = "."   # the script sits INSIDE "2. N_application_rate" -> download right here
PASSIVE   = True
TIMEOUT   = 120
RETRIES   = 10                 # download attempts per file
RECONNECT_TRIES = 20           # how many times to retry the LOGIN before giving up
SMALL_FIRST = True
ONLY_CONTAINS = []             # e.g. ["application"] to skip harvested area
SKIP_LARGER_THAN_GB = None     # e.g. 2.0 to skip the 2.8 GB harvested-area file
# ====================================================


def open_connection():
    """Return a live FTP object, or None if every host failed this pass."""
    for host in HOSTS:
        try:
            ftp = ftplib.FTP()
            ftp.connect(host, PORT, timeout=TIMEOUT)
            ftp.login(USERNAME, PASSWORD)
            ftp.set_pasv(PASSIVE)
            return ftp
        except Exception as e:
            print("  connect failed on " + host + ": " + str(e))
    return None


def ensure_connection(box):
    """Keep retrying (with back-off) until we hold a live connection. True/False."""
    for k in range(RECONNECT_TRIES):
        ftp = open_connection()
        if ftp is not None:
            box[0] = ftp
            return True
        wait = min(60, 5 * (k + 1))
        print("  reconnect attempt " + str(k + 1) + " failed; sleeping " + str(wait) + "s")
        time.sleep(wait)
    box[0] = None
    return False


def safe_close(box):
    try:
        if box[0] is not None:
            box[0].close()
    except Exception:
        pass
    box[0] = None


def list_files(box):
    """Flat recursive listing as (path, size). Reconnects once if it fails."""
    for _ in range(2):
        try:
            acc = []
            stack = [REMOTE_DIR]
            while stack:
                d = stack.pop()
                box[0].cwd(d)
                for name in box[0].nlst():
                    if name in (".", ".."):
                        continue
                    cur = box[0].pwd()
                    isdir = False
                    try:
                        box[0].cwd(name); box[0].cwd(cur); isdir = True
                    except Exception:
                        isdir = False
                    full = d.rstrip("/") + "/" + name
                    if isdir:
                        stack.append(full)
                    else:
                        try:
                            sz = box[0].size(name)
                        except Exception:
                            sz = 0
                        acc.append((full, sz if sz else 0))
            return acc
        except Exception as e:
            print("  listing error: " + str(e) + " -- reconnecting")
            safe_close(box); ensure_connection(box)
    return []


def download_one(box, remote_path, local_path):
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
    remote_dir = os.path.dirname(remote_path) or "/"
    name = os.path.basename(remote_path)
    for attempt in range(1, RETRIES + 1):
        if box[0] is None and not ensure_connection(box):
            print("  cannot reach server; resume " + name + " next run")
            return False
        # probe size (any failure -> reconnect and retry)
        try:
            box[0].cwd(remote_dir)
            rsize = box[0].size(name)
        except Exception as e:
            print("    probe error: " + str(e) + " -- reconnecting")
            safe_close(box); ensure_connection(box); continue
        have = os.path.getsize(local_path) if os.path.exists(local_path) else 0
        if rsize and have == rsize:
            print("  skip (complete): " + local_path)
            return True
        mode = "ab" if (have > 0 and rsize and have < rsize) else "wb"
        rest = have if mode == "ab" else None
        act = "resume" if rest else "start"
        try:
            print("  " + name + ": " + str(have) + "/" + str(rsize) + " bytes, " + act + " (attempt " + str(attempt) + ")")
            fh = open(local_path, mode)
            box[0].retrbinary("RETR " + name, fh.write, 1024 * 1024, rest)
            fh.close()
            print("  saved -> " + local_path)
            return True
        except Exception as e:
            try:
                fh.close()
            except Exception:
                pass
            print("    error: " + str(e) + " -- reconnecting and retrying")
            safe_close(box)
            time.sleep(5)
            ensure_connection(box)
    print("  GAVE UP on " + name + " after " + str(RETRIES) + " attempts (resume next run)")
    return False


# ----------------------------------------------------------------- run
box = [None]
if not ensure_connection(box):
    raise SystemExit("Could not reach the FTP server at all. Try again later (02:00-10:00 Beijing).")
print("connected. listing files ...")
files = list_files(box)
if ONLY_CONTAINS:
    files = [(p, s) for (p, s) in files if any(k.lower() in p.lower() for k in ONLY_CONTAINS)]
if SKIP_LARGER_THAN_GB is not None:
    cap = SKIP_LARGER_THAN_GB * 1e9
    files = [(p, s) for (p, s) in files if s <= cap]
if SMALL_FIRST:
    files.sort(key=lambda x: x[1])
print("\n" + str(len(files)) + " file(s) to fetch:")
for p, s in files:
    print("  " + format(s / 1e6, "10.1f") + " MB   " + p)
print()
ok = 0
for p, s in files:
    local = os.path.join(LOCAL_DIR, p.lstrip("/"))
    try:
        if download_one(box, p, local):
            ok += 1
    except Exception as e:
        print("  unexpected error on " + p + ": " + str(e) + " -- continuing")
print("\nDONE this run: " + str(ok) + "/" + str(len(files)) + " complete. Re-run to finish the rest. Folder: " + os.path.abspath(LOCAL_DIR))
safe_close(box)
