#!/usr/bin/env python3
"""One-time local browser authorization; run on your own computer, never in GitHub Actions."""
import argparse
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("client_json", help="Downloaded Desktop OAuth Client JSON from Google Cloud")
    args = ap.parse_args()
    if not Path(args.client_json).is_file():
        ap.error("Download the Desktop OAuth client JSON from Google Cloud first.")
    flow = InstalledAppFlow.from_client_secrets_file(args.client_json, scopes=SCOPES)
    print("Google will ask which YouTube channel to authorize.")
    print("Choose the channel for @seekingthechrist114.")
    credentials = flow.run_local_server(
        port=0, open_browser=True, authorization_prompt_message="Open this URL: {url}",
        access_type="offline", prompt="consent"
    )
    if not credentials.refresh_token:
        raise SystemExit("Google returned no refresh token. Revoke access and retry with offline consent.")
    print("\nSUCCESS. Add the following as GitHub repository secrets. Do not commit or paste them into chat.")
    print("\nYOUTUBE_CLIENT_ID:\n" + credentials.client_id)
    print("\nYOUTUBE_CLIENT_SECRET:\n" + credentials.client_secret)
    print("\nYOUTUBE_REFRESH_TOKEN:\n" + credentials.refresh_token)
    print("\nGitHub secrets page:")
    print("https://github.com/endelofaustin/didathing/settings/secrets/actions")
    print("Keep the OAuth client JSON and printed values private.")

if __name__ == "__main__":
    main()
