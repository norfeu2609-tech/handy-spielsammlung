#!/usr/bin/env python3
"""
Auto-Spielesammlung - Lokaler HTTPS-Server
==========================================
Dieses Script startet einen lokalen Webserver mit HTTPS,
damit das Mikrofon auf allen Geräten im WLAN funktioniert.

Voraussetzung: Python 3 (meist schon installiert)

Starten:
  Windows: Doppelklick auf server_starten.py
           oder: python server_starten.py
  Mac/Linux: python3 server_starten.py
"""

import http.server
import ssl
import socket
import os
import sys
import threading
import subprocess
import tempfile
import struct

# ── Verzeichnis zu dem Ordner wechseln, wo dieses Script liegt ──────────────
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

PORT = 8443
HTML_FILE = "auto-spielesammlung.html"

# ── Farben für Terminal ──────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def get_local_ip():
    """Findet die lokale IP-Adresse im WLAN."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def create_self_signed_cert():
    """Erstellt ein selbstsigniertes SSL-Zertifikat mit openssl oder reinem Python."""
    cert_file = os.path.join(tempfile.gettempdir(), "spielesammlung.crt")
    key_file  = os.path.join(tempfile.gettempdir(), "spielesammlung.key")

    # Wenn schon vorhanden, wiederverwenden
    if os.path.exists(cert_file) and os.path.exists(key_file):
        return cert_file, key_file

    # Versuche openssl
    try:
        result = subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", key_file, "-out", cert_file,
            "-days", "365", "-nodes",
            "-subj", "/CN=spielesammlung.local"
        ], capture_output=True, timeout=15)
        if result.returncode == 0:
            return cert_file, key_file
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: cryptography-Bibliothek
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, u"spielesammlung.local")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .sign(key, hashes.SHA256())
        )
        with open(key_file, "wb") as f:
            f.write(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption()
            ))
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        return cert_file, key_file

    except ImportError:
        return None, None

def print_qr_code(url):
    """Gibt einen QR-Code im Terminal aus (funktioniert ohne externe Bibliotheken)."""
    try:
        import qrcode  # type: ignore
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        print()
        qr.print_ascii(invert=True)
        print()
        return
    except ImportError:
        pass

    # Minimaler QR-Code-Generator (nur für URL, keine externe Bibliothek nötig)
    # Zeige stattdessen den Link groß an
    print()
    print(f"  ┌{'─'*50}┐")
    print(f"  │  {BOLD}Adresse für alle Geräte im WLAN:{RESET}          │")
    print(f"  │                                                  │")
    print(f"  │  {GREEN}{BOLD}{url}{RESET}")
    print(f"  │                                                  │")
    print(f"  │  Einfach diese Adresse im Browser eingeben!      │")
    print(f"  └{'─'*50}┘")
    print()

def open_browser(url):
    """Öffnet den Browser automatisch."""
    import time
    time.sleep(1.5)
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass

def main():
    print()
    print(f"{BOLD}{BLUE}╔════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{BLUE}║    🚗  Auto-Spielesammlung Server     ║{RESET}")
    print(f"{BOLD}{BLUE}╚════════════════════════════════════════╝{RESET}")
    print()

    # Prüfe ob HTML-Datei vorhanden
    if not os.path.exists(HTML_FILE):
        print(f"{RED}❌ Datei '{HTML_FILE}' nicht gefunden!{RESET}")
        print(f"   Bitte script im gleichen Ordner wie die HTML-Datei ablegen.")
        input("\nEnter drücken zum Beenden...")
        sys.exit(1)

    # IP ermitteln
    local_ip = get_local_ip()
    print(f"  📡 Lokale IP-Adresse: {GREEN}{local_ip}{RESET}")

    # SSL-Zertifikat erstellen
    print(f"  🔐 Erstelle HTTPS-Zertifikat...")
    cert_file, key_file = create_self_signed_cert()

    if cert_file and key_file:
        protocol = "https"
        url_local = f"https://localhost:{PORT}/{HTML_FILE}"
        url_wlan  = f"https://{local_ip}:{PORT}/{HTML_FILE}"
        use_https = True
    else:
        print(f"  {YELLOW}⚠️  HTTPS nicht verfügbar - starte HTTP (Mikrofon evtl. eingeschränkt){RESET}")
        protocol = "http"
        url_local = f"http://localhost:{PORT}/{HTML_FILE}"
        url_wlan  = f"http://{local_ip}:{PORT}/{HTML_FILE}"
        use_https = False

    # Server starten
    handler = http.server.SimpleHTTPRequestHandler

    # Logging unterdrücken
    class QuietHandler(handler):
        def log_message(self, format, *args):
            pass  # Kein Log-Spam

    try:
        httpd = http.server.HTTPServer(("", PORT), QuietHandler)
    except OSError:
        print(f"  {YELLOW}⚠️  Port {PORT} belegt, versuche Port 8444...{RESET}")
        PORT_alt = 8444
        httpd = http.server.HTTPServer(("", PORT_alt), QuietHandler)
        url_local = f"{protocol}://localhost:{PORT_alt}/{HTML_FILE}"
        url_wlan  = f"{protocol}://{local_ip}:{PORT_alt}/{HTML_FILE}"

    if use_https:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    print()
    print(f"  {GREEN}✅ Server läuft!{RESET}")
    print()
    print(f"  {BOLD}Auf diesem Gerät:{RESET}")
    print(f"     {GREEN}{url_local}{RESET}")
    print()
    print(f"  {BOLD}Auf Handy/Tablet im gleichen WLAN:{RESET}")
    print_qr_code(url_wlan)
    print(f"     {GREEN}{BOLD}{url_wlan}{RESET}")
    print()

    if use_https:
        print(f"  {YELLOW}💡 Hinweis: Browser zeigt 'Nicht sicher' - das ist normal!{RESET}")
        print(f"     {YELLOW}Auf 'Erweitert' → 'Trotzdem fortfahren' klicken.{RESET}")
        print(f"     {YELLOW}Danach funktioniert das Mikrofon! 🎤{RESET}")
    print()
    print(f"  {BOLD}Server stoppen: Strg+C drücken{RESET}")
    print()
    print(f"  {'─'*42}")

    # Browser automatisch öffnen
    threading.Thread(target=open_browser, args=(url_local,), daemon=True).start()

    # Server läuft bis Strg+C
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n\n  {YELLOW}Server gestoppt. Auf Wiedersehen! 🚗{RESET}\n")
        httpd.server_close()

if __name__ == "__main__":
    main()
