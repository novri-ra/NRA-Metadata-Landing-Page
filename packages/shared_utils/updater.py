import urllib.request
import json
import threading

APP_VERSION = "1.0.0"

def check_github_release(repo="novri-ra/NRA-Metadata", callback=None):
    """Non-blocking version check via github API"""
    def _check():
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/releases/latest",
                headers={"User-Agent": "NRA-Metadata-App"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                tag = data.get("tag_name", "").lstrip("v")
                url = data.get("html_url", "")
                if tag and tag != APP_VERSION and callback:
                    callback({"version": tag, "url": url})
        except Exception:
            pass # Silent fail for bg checker
            
    threading.Thread(target=_check, daemon=True).start()
