#!/usr/bin/env python3
"""A conservative, reusable YouTube uploader. No upload occurs without --publish."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
RETRIABLE_HTTP_CODES = {429, 500, 502, 503, 504}


def load_metadata(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Metadata must be a JSON object.")
    title = data.get("title")
    desc = data.get("description")
    if not isinstance(title, str) or not title.strip() or len(title) > 100:
        raise ValueError("Title must contain 1 to 100 characters.")
    if any(c in title for c in "<>"):
        raise ValueError("YouTube titles cannot contain angle brackets.")
    if not isinstance(desc, str) or len(desc) > 5000:
        raise ValueError("Description must be text of at most 5,000 characters.")
    if not isinstance(data.get("madeForKids"), bool):
        raise ValueError("Set madeForKids explicitly to true or false.")
    if "containsSyntheticMedia" in data and not isinstance(data["containsSyntheticMedia"], bool):
        raise ValueError("containsSyntheticMedia must be a boolean.")
    category = data.get("categoryId", "27")
    if not str(category).isdigit() or int(category) < 1:
        raise ValueError("categoryId must be a positive YouTube category ID.")
    tags = data.get("tags", [])
    if (not isinstance(tags, list) or len(tags) > 30
            or any(not isinstance(t, str) or not t.strip() or "<" in t or ">" in t for t in tags)
            or len(",".join(tags)) > 500):
        raise ValueError("Invalid tags (maximum 30 and 500 characters total).")
    return {
        "title": title.strip(),
        "description": desc,
        "tags": tags,
        "categoryId": str(category),
        "madeForKids": data["madeForKids"],
        "containsSyntheticMedia": data.get("containsSyntheticMedia", False),
    }


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def build_credentials():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    keys = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
    missing = [key for key in keys if not os.getenv(key)]
    if missing:
        raise RuntimeError(
            "GitHub repository secrets missing: " + ", ".join(missing)
            + ". Follow youtube_upload/README.md. Never put tokens in Git or chat."
        )
    credentials = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    credentials.refresh(Request())
    return credentials


def verify_channel(youtube, expected_channel_id: str) -> None:
    if not expected_channel_id:
        raise ValueError("expected channel ID is required before upload.")
    result = youtube.channels().list(part="id,snippet", mine=True).execute()
    channels = result.get("items") or []
    if len(channels) != 1:
        raise RuntimeError(
            "OAuth did not identify exactly one channel. Reauthorize using "
            "the Google/YouTube channel you want to publish to."
        )
    found = channels[0]["id"]
    if found != expected_channel_id:
        raise RuntimeError(
            "Wrong YouTube channel selected. Expected " + expected_channel_id
            + ", authorized " + found + ". Upload cancelled."
        )
    print("Authorized channel verified: " + found, flush=True)


def make_body(meta: dict, visibility: str) -> dict:
    if visibility not in ("private", "unlisted", "public"):
        raise ValueError("Visibility must be private, unlisted, or public.")
    return {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": meta["categoryId"],
        },
        "status": {
            "privacyStatus": visibility,
            "selfDeclaredMadeForKids": meta["madeForKids"],
            "containsSyntheticMedia": meta["containsSyntheticMedia"],
        },
    }


def upload_video(youtube, media_path: Path, body: dict) -> str:
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    media = MediaFileUpload(
        str(media_path),
        mimetype="video/quicktime" if media_path.suffix.lower() == ".mov" else "video/mp4",
        resumable=True,
        chunksize=8 * 1024 * 1024,
    )
    request = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media, notifySubscribers=True
    )
    result = None
    retries = 0
    while result is None:
        try:
            progress, result = request.next_chunk()
            if progress:
                print("Uploaded {:.1%}".format(progress.progress()), flush=True)
            retries = 0
        except (HttpError, OSError) as exc:
            code = getattr(getattr(exc, "resp", None), "status", None)
            retryable = isinstance(exc, OSError) or code in RETRIABLE_HTTP_CODES
            if not retryable or retries >= 8:
                raise
            retries += 1
            delay = min(64, 2 ** retries + random.random())
            print("Retryable upload interruption; retrying in {:.1f}s".format(delay), flush=True)
            time.sleep(delay)
    video_id = result.get("id")
    if not video_id:
        raise RuntimeError("YouTube did not return a video ID. Check Studio before retrying.")
    return video_id


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--metadata", required=True, help="JSON title, description, tags and audience")
    ap.add_argument("--video", help="MP4/MOV file produced by your audiobook pipeline")
    ap.add_argument("--thumbnail", help="Optional JPG/PNG thumbnail; may be refused by YouTube")
    ap.add_argument("--visibility", choices=["public", "unlisted", "private"], default="private")
    ap.add_argument("--expected-channel-id", default="UC_MLwosrdFohed-oRiohxLw")
    ap.add_argument("--result-file", default="upload-result.json")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--publish", action="store_true", help="Only option that uploads to YouTube")
    mode.add_argument("--validate-only", action="store_true", help="Validate JSON without a video")
    args = ap.parse_args()

    meta = load_metadata(args.metadata)
    body = make_body(meta, args.visibility)
    if args.validate_only:
        print("VALID metadata: title={}, description={}/5000 chars".format(
            meta["title"], len(meta["description"])))
        return

    if not args.video:
        ap.error("--video is required for dry-run or publish.")
    video_path = Path(args.video)
    if not video_path.is_file() or video_path.suffix.lower() not in (".mp4", ".mov"):
        ap.error("--video must refer to an existing MP4 or MOV file.")
    if video_path.stat().st_size < 1024:
        ap.error("Video is unexpectedly small.")
    thumb_path = Path(args.thumbnail) if args.thumbnail else None
    if thumb_path and (not thumb_path.is_file()
                       or thumb_path.suffix.lower() not in (".jpg", ".jpeg", ".png")):
        ap.error("--thumbnail must refer to an existing JPG or PNG file.")
    if thumb_path and thumb_path.stat().st_size > 2_000_000:
        ap.error("YouTube thumbnail must be at most 2 MB.")
    print("Channel:", args.expected_channel_id)
    print("Title:", meta["title"])
    print("Description length:", len(meta["description"]), "/ 5000")
    print("Video:", video_path, "({} bytes)".format(video_path.stat().st_size))
    print("Visibility:", args.visibility)
    print("Thumbnail:", thumb_path or "(none)")
    if not args.publish:
        print("DRY RUN: no network authorization and no YouTube upload.")
        return

    if not args.expected_channel_id:
        ap.error("--expected-channel-id is required for --publish.")
    from googleapiclient.discovery import build
    youtube = build("youtube", "v3", credentials=build_credentials(), cache_discovery=False)
    verify_channel(youtube, args.expected_channel_id)
    video_id = upload_video(youtube, video_path, body)

    # Persist a receipt before attempting thumbnail assignment. Do not retry a
    # completed upload just because YouTube rejects a custom thumbnail.
    receipt = {
        "videoId": video_id,
        "url": "https://www.youtube.com/watch?v=" + video_id,
        "channelId": args.expected_channel_id,
        "title": meta["title"],
        "visibilityRequested": args.visibility,
        "descriptionCharacters": len(meta["description"]),
        "videoSha256": file_sha256(video_path),
        "uploadedAt": datetime.now(timezone.utc).isoformat(),
        "thumbnailStatus": "not_requested",
    }
    result_path = Path(args.result_file)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print("VIDEO UPLOADED:", receipt["url"], flush=True)

    if thumb_path:
        from googleapiclient.http import MediaFileUpload
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(
                    str(thumb_path), mimetype=mimetypes.guess_type(thumb_path.name)[0]
                ),
            ).execute()
            receipt["thumbnailStatus"] = "success"
        except Exception as exc:
            receipt["thumbnailStatus"] = "failed"
            receipt["thumbnailError"] = str(exc)[:300]
            print("WARNING: Video is uploaded; custom thumbnail failed.", file=sys.stderr)
        result_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("## YouTube upload\n\n" + receipt["url"] + "\n\n")
            f.write("Visibility requested: **" + args.visibility + "**\n\n")
            f.write("Thumbnail: " + receipt["thumbnailStatus"] + "\n")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)
