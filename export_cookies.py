#!/usr/bin/env python3
"""
Export YouTube cookies from your browser to cookies.txt (Netscape format).
No browser extension needed. Run this on your computer (not the server).

Usage:
  pip install browser_cookie3
  python export_cookies.py

Chrome/Firefox must be CLOSED when running (or use --browser firefox if Chrome is open).
"""
import sys

def main():
    try:
        import browser_cookie3
    except ImportError:
        print("Install: pip install browser_cookie3")
        sys.exit(1)

    browser = "chrome"
    if len(sys.argv) > 1:
        browser = sys.argv[1].lower()

    try:
        if browser == "chrome":
            cj = browser_cookie3.chrome(domain_name=".youtube.com")
        elif browser == "firefox":
            cj = browser_cookie3.firefox(domain_name=".youtube.com")
        elif browser == "edge":
            cj = browser_cookie3.edge(domain_name=".youtube.com")
        elif browser == "opera":
            cj = browser_cookie3.opera(domain_name=".youtube.com")
        elif browser == "brave":
            cj = browser_cookie3.brave(domain_name=".youtube.com")
        else:
            print("Usage: python export_cookies.py [chrome|firefox|edge|opera|brave]")
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        print("\nTip: Close your browser completely, then run this script again.")
        sys.exit(1)

    cookies = list(cj)
    if not cookies:
        print("No YouTube cookies found. Log in to youtube.com in your browser first.")
        sys.exit(1)

    with open("cookies.txt", "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in cookies:
            domain = "." + c.domain if not c.domain.startswith(".") else c.domain
            f.write(f"{domain}\tTRUE\t/\tFALSE\t{c.expires or 0}\t{c.name}\t{c.value}\n")

    print("Saved to cookies.txt")
    print("Upload this file to your server: /opt/nouscript/cookies.txt")

if __name__ == "__main__":
    main()
