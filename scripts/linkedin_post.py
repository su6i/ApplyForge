"""
linkedin_post.py — Post a PDF document + text to LinkedIn

Usage:
    python scripts/linkedin_post.py --post linkedin/01_IT_job_market

The post folder must contain:
    carousel.pdf   — the document to upload
    post.txt       — title on line 1 (after "TITRE DU DOCUMENT : "), post text below "---"

Setup (one-time):
    1. Go to https://developer.linkedin.com/  → Create App
    2. Add product: "Share on LinkedIn" + "Sign In with LinkedIn using OpenID Connect"
    3. Copy Client ID and Client Secret into .env:
           LINKEDIN_CLIENT_ID=xxx
           LINKEDIN_CLIENT_SECRET=xxx
    4. Run:  python scripts/linkedin_post.py --auth
       → Opens browser, you approve, token saved to .linkedin_token.json
    5. Run:  python scripts/linkedin_post.py --post linkedin/02_data_science
"""

import argparse
import json
import os
import re
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────
REPO_ROOT    = Path(__file__).parent.parent
TOKEN_FILE   = REPO_ROOT / ".linkedin_token.json"
REDIRECT_URI = "http://localhost:8765/callback"
SCOPES       = "openid profile w_member_social"

load_dotenv(REPO_ROOT / ".env")
CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")

# ── OAuth helpers ─────────────────────────────────────────────────────────────

def auth_flow():
    """Open browser for OAuth2, capture code via local server, exchange for token."""
    if not CLIENT_ID or not CLIENT_SECRET:
        sys.exit("❌  Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env first.")

    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        + urlencode({
            "response_type": "code",
            "client_id":     CLIENT_ID,
            "redirect_uri":  REDIRECT_URI,
            "scope":         SCOPES,
        })
    )
    print(f"🌐  Opening browser for LinkedIn authorization…\n{auth_url}")
    webbrowser.open(auth_url)

    # Tiny one-shot HTTP server to catch the redirect
    code_holder = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = parse_qs(urlparse(self.path).query)
            code_holder["code"] = qs.get("code", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>Authorization complete. You can close this tab.</h2>")

        def log_message(self, *_):
            pass

    server = HTTPServer(("localhost", 8765), Handler)
    print("⏳  Waiting for authorization (approve in browser)…")
    server.handle_request()

    code = code_holder.get("code")
    if not code:
        sys.exit("❌  No authorization code received.")

    # Exchange code for access token
    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  REDIRECT_URI,
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    token_data = resp.json()

    # Fetch person URN
    me = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
        timeout=10,
    ).json()
    token_data["sub"] = me["sub"]   # person URN like "urn:li:person:XXXX"

    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    print(f"✅  Token saved to {TOKEN_FILE}")
    return token_data


def load_token() -> dict:
    if not TOKEN_FILE.exists():
        sys.exit("❌  No token found. Run:  python scripts/linkedin_post.py --auth")
    return json.loads(TOKEN_FILE.read_text())


# ── LinkedIn API helpers ──────────────────────────────────────────────────────

def api_headers(token: str) -> dict:
    return {
        "Authorization":    f"Bearer {token}",
        "LinkedIn-Version": "202604",
        "X-Restli-Protocol-Version": "2.0.0",
    }


def upload_document(pdf_path: Path, token: str, owner_urn: str) -> str:
    """Upload PDF and return the asset URN."""
    headers = api_headers(token)

    # Step 1 — initialize upload
    init = requests.post(
        "https://api.linkedin.com/rest/documents?action=initializeUpload",
        headers={**headers, "Content-Type": "application/json"},
        json={"initializeUploadRequest": {"owner": owner_urn}},
        timeout=15,
    )
    init.raise_for_status()
    data = init.json()["value"]
    upload_url  = data["uploadUrl"]
    document_urn = data["document"]

    # Step 2 — PUT the PDF bytes
    pdf_bytes = pdf_path.read_bytes()
    put_resp = requests.put(
        upload_url,
        data=pdf_bytes,
        headers={"Content-Type": "application/octet-stream"},
        timeout=60,
    )
    put_resp.raise_for_status()
    print(f"📤  Uploaded {pdf_path.name} ({len(pdf_bytes)//1024} KB)")
    return document_urn


def create_document_post(
    token: str,
    owner_urn: str,
    text: str,
    document_urn: str,
    doc_title: str,
) -> str:
    """Create the LinkedIn post and return the post URN."""
    headers = {**api_headers(token), "Content-Type": "application/json"}

    payload = {
        "author":       owner_urn,
        "commentary":   text,
        "visibility":   "PUBLIC",
        "distribution": {
            "feedDistribution":             "MAIN_FEED",
            "targetEntities":               [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {
            "media": {
                "title": doc_title,
                "id":    document_urn,
            }
        },
        "lifecycleState":           "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    resp = requests.post(
        "https://api.linkedin.com/rest/posts",
        headers=headers,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    post_id = resp.headers.get("x-restli-id", "unknown")
    return post_id


# ── Post-folder parser ────────────────────────────────────────────────────────

def parse_post_folder(folder: Path) -> tuple[str, str, Path]:
    """Return (doc_title, post_text, pdf_path) from a post folder."""
    post_txt = folder / "post.txt"
    pdf_path = folder / "carousel.pdf"

    if not post_txt.exists():
        sys.exit(f"❌  Missing {post_txt}")
    if not pdf_path.exists():
        sys.exit(f"❌  Missing {pdf_path}")

    raw = post_txt.read_text(encoding="utf-8")

    # Extract document title from line "TITRE DU DOCUMENT : ..."
    title_match = re.search(r"TITRE DU DOCUMENT\s*:\s*(.+)", raw)
    doc_title = title_match.group(1).strip() if title_match else folder.name

    # Post text = everything after the last "---..." separator line
    parts = re.split(r"^-{5,}.*$", raw, flags=re.MULTILINE)
    post_text = parts[-1].strip()

    return doc_title, post_text, pdf_path


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Post a PDF carousel to LinkedIn")
    parser.add_argument("--auth",  action="store_true", help="Run OAuth2 flow")
    parser.add_argument("--post",  metavar="FOLDER",    help="Post folder to publish")
    parser.add_argument("--dry-run", action="store_true", help="Parse & print without posting")
    args = parser.parse_args()

    if args.auth:
        auth_flow()
        return

    if not args.post:
        parser.print_help()
        return

    folder = REPO_ROOT / args.post
    if not folder.exists():
        sys.exit(f"❌  Folder not found: {folder}")

    doc_title, post_text, pdf_path = parse_post_folder(folder)

    print(f"📄  Title  : {doc_title}")
    print(f"📝  Text   : {post_text[:120].replace(chr(10),' ')}…")
    print(f"📎  PDF    : {pdf_path}")

    if args.dry_run:
        print("\n✅  Dry run complete — nothing posted.")
        return

    token_data = load_token()
    token      = token_data["access_token"]
    owner_urn  = f"urn:li:person:{token_data['sub']}"

    print(f"\n👤  Posting as {owner_urn}")

    document_urn = upload_document(pdf_path, token, owner_urn)
    time.sleep(2)   # let LinkedIn process the upload

    post_id = create_document_post(token, owner_urn, post_text, document_urn, doc_title)
    print(f"\n✅  Post published!  ID: {post_id}")
    print(f"🔗  https://www.linkedin.com/feed/update/{post_id}/")


if __name__ == "__main__":
    main()
