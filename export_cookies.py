#!/usr/bin/env python3
"""
Export YouTube cookies from your browser to cookies.txt (Netscape format).
No browser extension needed. Run this on your computer (not the server).

Usage:
  pip install browser_cookie3
  python export_cookies.py [chrome|firefox|edge|opera|brave]

Chrome/Edge/Opera/Brave: Tarayıcıyı TAMAMEN KAPATIN, sonra çalıştırın.
Firefox: Genelde tarayıcı açıkken de çalışır.
"""
import sys

def _get_cookies(browser: str, domain: str):
    import browser_cookie3
    if browser == "chrome":
        return browser_cookie3.chrome(domain_name=domain)
    elif browser == "firefox":
        return browser_cookie3.firefox(domain_name=domain)
    elif browser == "edge":
        return browser_cookie3.edge(domain_name=domain)
    elif browser == "opera":
        return browser_cookie3.opera(domain_name=domain)
    elif browser == "brave":
        return browser_cookie3.brave(domain_name=domain)
    raise ValueError(f"Unknown browser: {browser}")

def main():
    try:
        import browser_cookie3
    except ImportError:
        print("Kurulum: pip install browser_cookie3")
        sys.exit(1)

    browser = "chrome"
    if len(sys.argv) > 1:
        browser = sys.argv[1].lower()

    if browser not in ("chrome", "firefox", "edge", "opera", "brave"):
        print("Kullanım: python export_cookies.py [chrome|firefox|edge|opera|brave]")
        sys.exit(1)

    seen = set()  # (domain, name) -> avoid duplicates
    all_cookies = []

    for domain in (".youtube.com", ".google.com"):
        try:
            cj = _get_cookies(browser, domain)
            for c in cj:
                key = (c.domain, c.name)
                if key not in seen:
                    seen.add(key)
                    all_cookies.append(c)
        except Exception as e:
            if "youtube" in domain:
                print(f"Uyarı: {domain} cookies alınamadı: {e}")

    if not all_cookies:
        print("No YouTube cookie found. Log in to youtube.com in the browser first.")
        print("If using Chrome, close the browser completely and try again.")
        sys.exit(1)

    # LF newlines (Linux server compatibility; yt-dlp can fail on CRLF)
    with open("cookies.txt", "w", newline="\n") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in all_cookies:
            domain = "." + c.domain if not c.domain.startswith(".") else c.domain
            f.write(f"{domain}\tTRUE\t{c.path or '/'}\tFALSE\t{c.expires or 0}\t{c.name}\t{c.value}\n")

    print("cookies.txt created.")
    print("Upload to server: scp cookies.txt root@SERVER_IP:/opt/nouscript/")
    print("Veya Hostinger Dosya Yöneticisi ile /opt/nouscript/ klasörüne yükleyin.")

if __name__ == "__main__":
    main()
