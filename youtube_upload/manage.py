#!/usr/bin/env python3
"""Safely maintain existing YouTube videos and playlists; default is preview-only.

Unlike the uploader this never creates videos, changes privacy, or deletes content.
Use --check-plan to validate without Google, or --apply after reviewing the plan.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
from pathlib import Path

CHANNEL_ID = "UC_MLwosrdFohed-oRiohxLw"
ROOT = Path(__file__).resolve().parent.parent
MAX_DESCRIPTION = 5000
MAX_TITLE = 100
VIDEO_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def safe_file(relative: str, allowed_extensions: tuple[str, ...]) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("Asset paths must be nonempty and relative to the repository.")
    p = (ROOT / relative).resolve()
    if p != ROOT and ROOT not in p.parents:
        raise ValueError("Asset path escapes the repository: " + relative)
    if p.suffix.lower() not in allowed_extensions or not p.is_file():
        raise ValueError("Missing or invalid file: " + relative)
    return p


def validate_title(title: str) -> str:
    if not isinstance(title, str) or not title.strip() or len(title) > MAX_TITLE:
        raise ValueError("A YouTube title must be 1-100 characters.")
    if "<" in title or ">" in title:
        raise ValueError("YouTube titles must not contain angle brackets.")
    return title


def load_plan(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        plan = json.load(f)
    if not isinstance(plan, dict) or plan.get("expectedChannelId") != CHANNEL_ID:
        raise ValueError("Plan must explicitly target the approved YouTube channel.")
    videos = plan.get("videos", [])
    if not isinstance(videos, list):
        raise ValueError("videos must be an array.")
    seen = set()
    for item in videos:
        if not isinstance(item, dict) or not VIDEO_ID_RE.fullmatch(str(item.get("videoId", ""))):
            raise ValueError("Each video needs a valid videoId.")
        if item["videoId"] in seen:
            raise ValueError("Duplicate videoId in plan.")
        seen.add(item["videoId"])
        if "title" in item:
            validate_title(item["title"])
        if "appendFile" in item:
            safe_file(item["appendFile"], (".txt",))
        if "thumbnailFile" in item:
            thumb = safe_file(item["thumbnailFile"], (".jpg", ".jpeg", ".png"))
            if thumb.stat().st_size > 10 * 1024 * 1024:
                raise ValueError("Thumbnail larger than 10 MiB.")
        if not any(k in item for k in ("title", "appendFile", "thumbnailFile")):
            raise ValueError("Each video must request at least one change.")
    playlists = plan.get("playlists", [])
    if not isinstance(playlists, list):
        raise ValueError("playlists must be an array.")
    for pl in playlists:
        if not isinstance(pl, dict) or not isinstance(pl.get("title"), str) or not pl["title"].strip():
            raise ValueError("Every playlist needs a title.")
        if not isinstance(pl.get("videoIds", []), list):
            raise ValueError("playlist videoIds must be an array.")
        if any(not VIDEO_ID_RE.fullmatch(str(v)) for v in pl.get("videoIds", [])):
            raise ValueError("Invalid video ID in playlist.")
        if not isinstance(pl.get("description", ""), str) or len(pl.get("description", "")) > 5000:
            raise ValueError("Invalid playlist description.")
    if not videos and not playlists:
        raise ValueError("Plan contains no changes.")
    return plan


def merge_description(original: str, addition: str) -> str:
    """Append approved text literally; never truncate or delete original material."""
    if not isinstance(original, str):
        raise ValueError("Existing description was not returned.")
    addition = addition.strip()
    if not addition or addition in original:
        return original
    final = original.rstrip() + ("\n\n" if original.strip() else "") + addition
    if len(final) > MAX_DESCRIPTION:
        raise ValueError(
            "Description would be {} characters (limit {}). No update was sent."
            .format(len(final), MAX_DESCRIPTION)
        )
    return final


def make_video_patch(item: dict, resource: dict) -> dict | None:
    current = resource.get("snippet")
    if not isinstance(current, dict) or current.get("channelId") != CHANNEL_ID:
        raise ValueError("Video is not owned by the expected channel.")
    old_title = current.get("title")
    old_desc = current.get("description")
    new_title = validate_title(item.get("title", old_title))
    new_desc = old_desc
    if "appendFile" in item:
        addition = safe_file(item["appendFile"], (".txt",)).read_text(encoding="utf-8")
        new_desc = merge_description(old_desc, addition)
    if new_title == old_title and new_desc == old_desc:
        return None
    if len(new_desc) > MAX_DESCRIPTION:
        raise ValueError("Description too long.")
    if not current.get("categoryId"):
        raise ValueError("YouTube did not return a categoryId; refusing update.")
    # videos.update replaces properties in the snippet part. Preserve editable
    # metadata, and never include the status part or modify privacy/audience.
    snippet = {k: current[k] for k in
               ("title", "description", "categoryId", "tags", "defaultLanguage")
               if k in current}
    snippet.update(title=new_title, description=new_desc)
    return {"id": item["videoId"], "snippet": snippet}


def credentials():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    keys = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        raise RuntimeError("Missing GitHub Actions OAuth secrets: " + ", ".join(missing))
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    if not creds.has_scopes([SCOPES[0]]):
        raise RuntimeError("OAuth must include youtube.force-ssl; rerun setup_oauth.py.")
    return creds


def list_owned_video(youtube, video_id: str) -> dict:
    result = youtube.videos().list(part="snippet,status", id=video_id).execute()
    items = result.get("items") or []
    if len(items) != 1 or items[0].get("snippet", {}).get("channelId") != CHANNEL_ID:
        raise RuntimeError("Video not found on the authorized channel: " + video_id)
    return items[0]


def playlist_by_title(youtube, title: str) -> dict | None:
    token = None
    while True:
        res = youtube.playlists().list(
            part="snippet", mine=True, maxResults=50, pageToken=token
        ).execute()
        matches = [p for p in res.get("items", []) if p.get("snippet", {}).get("title") == title]
        if len(matches) > 1:
            raise ValueError("Duplicate playlist titles; refusing ambiguous match: " + title)
        if matches:
            return matches[0]
        token = res.get("nextPageToken")
        if not token:
            return None


def playlist_video_ids(youtube, playlist_id: str) -> set[str]:
    found, token = set(), None
    while True:
        res = youtube.playlistItems().list(
            part="snippet", playlistId=playlist_id, maxResults=50, pageToken=token
        ).execute()
        for item in res.get("items", []):
            vid = item.get("snippet", {}).get("resourceId", {}).get("videoId")
            if vid:
                found.add(vid)
        token = res.get("nextPageToken")
        if not token:
            return found


def apply_plan(youtube, plan: dict, apply: bool) -> dict:
    from googleapiclient.http import MediaFileUpload
    from uploader import verify_channel

    verify_channel(youtube, CHANNEL_ID)
    report = {"channelId": CHANNEL_ID, "applied": apply, "videos": [], "playlists": []}
    # Prepare and validate all requested video changes before writing any.
    prepared = []
    for item in plan.get("videos", []):
        original = list_owned_video(youtube, item["videoId"])
        patch = make_video_patch(item, original)
        prepared.append((item, patch))
        report["videos"].append({
            "videoId": item["videoId"],
            "changeTitle": bool(patch and patch["snippet"]["title"] != original["snippet"]["title"]),
            "changeDescription": bool(patch and patch["snippet"]["description"] != original["snippet"]["description"]),
            "thumbnailRequested": "thumbnailFile" in item,
            "privacyUnchanged": original.get("status", {}).get("privacyStatus"),
        })
    for item, patch in prepared:
        if not apply:
            continue
        if patch:
            youtube.videos().update(part="snippet", body=patch).execute()
        if "thumbnailFile" in item:
            path = safe_file(item["thumbnailFile"], (".jpg", ".jpeg", ".png"))
            youtube.thumbnails().set(
                videoId=item["videoId"],
                media_body=MediaFileUpload(str(path), mimetype=mimetypes.guess_type(path.name)[0])
            ).execute()
    for pl in plan.get("playlists", []):
        title = pl["title"]
        existing = playlist_by_title(youtube, title)
        playlist_id = existing["id"] if existing else None
        existing_ids = playlist_video_ids(youtube, playlist_id) if playlist_id else set()
        pending = [v for v in dict.fromkeys(pl.get("videoIds", [])) if v not in existing_ids]
        for vid in pending:
            list_owned_video(youtube, vid)
        report["playlists"].append({
            "title": title, "existing": bool(existing), "videosToAdd": pending
        })
        if not apply:
            continue
        if not playlist_id:
            new_pl = youtube.playlists().insert(
                part="snippet,status",
                body={"snippet": {"title": title, "description": pl.get("description", "")},
                      "status": {"privacyStatus": "public"}}
            ).execute()
            playlist_id = new_pl["id"]
        for vid in pending:
            youtube.playlistItems().insert(
                part="snippet",
                body={"snippet": {"playlistId": playlist_id,
                                  "resourceId": {"kind": "youtube#video", "videoId": vid}}}
            ).execute()
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", required=True, help="Approved JSON plan")
    ap.add_argument("--check-plan", action="store_true", help="Local-only file checks; no API")
    ap.add_argument("--apply", action="store_true", help="Explicitly write reviewed changes")
    ap.add_argument("--result-file", default="youtube-manage-result.json")
    args = ap.parse_args()
    plan = load_plan(args.plan)
    if args.check_plan:
        print("VALID PLAN:", len(plan.get("videos", [])), "videos,",
              len(plan.get("playlists", [])), "playlists; no network requests.")
        return
    from googleapiclient.discovery import build
    youtube = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    report = apply_plan(youtube, plan, args.apply)
    Path(args.result_file).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not args.apply:
        print("PREVIEW ONLY. No YouTube content was changed.")


if __name__ == "__main__":
    main()
