# Free YouTube uploader for Seeking the Christ

Uploads full audiobook MP4s directly through Google's **YouTube Data API v3**. There is no vidIQ dependency, no paid TTS, and no upload service subscription. The repo builds and tests the uploader on every change; **it never uploads on push**. Uploads require a separate, manually initiated workflow and an explicitly checked "publish" switch.

This uploader targets **@seekingthechrist114** (channel ID `UC_MLwosrdFohed-oRiohxLw`) and refuses to publish if OAuth authorizes a different channel.

## One-time authorization (do this yourself; do not share secrets in chat)

1. Visit [Google Cloud Console](https://console.cloud.google.com/). Create/select your own project; enable **YouTube Data API v3**.
2. In **Google Auth Platform** configure the OAuth audience and branding, then add an **OAuth client ID → Desktop app** and download its JSON file. Add your Google account as a test user if the app is in Testing mode.
3. On your **own computer**, clone this repository, then run:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r youtube_upload/requirements.txt
   python youtube_upload/setup_oauth.py ~/Downloads/YOUR_CLIENT_SECRET_FILE.json
   ```

   This opens Google consent in your browser. Select the YouTube account/channel for **@seekingthechrist114**. The helper prints exactly three values for GitHub **Secrets**. **Do not commit or share the values or JSON.**

4. Add all three under [GitHub repository Actions secrets](https://github.com/endelofaustin/didathing/settings/secrets/actions) → **New repository secret**:
   - `YOUTUBE_CLIENT_ID`
   - `YOUTUBE_CLIENT_SECRET`
   - `YOUTUBE_REFRESH_TOKEN`

   This GitHub connector cannot create secrets, and a ChatGPT conversation is not a safe place to paste credentials. The OAuth flow is only done once unless the token is revoked/expired.

   **Note:** External OAuth apps in "Testing" may receive refresh tokens that expire after **7 days**. Google offers other production/personal app configurations; review the [Google OAuth documentation](https://developers.google.com/identity/protocols/oauth2). Choose the appropriate compliant configuration rather than storing an expiring token indefinitely.

## Phone-only setup (Android / Chrome, no Python)

You can authorize our uploader completely from your phone with [Google's OAuth Playground](https://developers.google.com/oauthplayground/). This uses a **Web application** OAuth client rather than the **Desktop app** client described above. **Do not run `setup_oauth.py` for this method.** Both methods produce the same GitHub secret values used by `uploader.py`.

1. In [Google Cloud Console](https://console.cloud.google.com/), open your uploader project and enable [YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com). Configure [Google Auth Platform](https://console.cloud.google.com/auth/overview) for your own account. Personal mode, if available, avoids the External Testing 7-day token expiry.
2. Under **Clients**, create an OAuth client of type **Web application**. Name it `Seeking the Christ Phone Uploader`. Set the **Authorized redirect URI** to exactly `https://developers.google.com/oauthplayground`. Copy its Client ID and Client Secret **privately**.
3. Open [OAuth Playground](https://developers.google.com/oauthplayground/) in Chrome. Gear icon → OAuth flow **Server-side**, access type **Offline**, force prompt **Consent Screen**, select **Use your own OAuth credentials**, and enter your new **Web application** Client ID and Secret.
4. Under Step 1, enter these two scopes separated by a space and tap **Authorize APIs**:
   `https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly`
5. Choose the Google account managing **@seekingthechrist114** and grant consent. Under Step 2, tap **Exchange authorization code for tokens**. Copy the **Refresh token** privately.
6. Open [GitHub Actions Secrets](https://github.com/endelofaustin/didathing/settings/secrets/actions) in Chrome (use **Desktop site** if buttons are missing). Create `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, and `YOUTUBE_REFRESH_TOKEN` using the values you just generated. You never need to send them in chat.
7. Once the token is safely saved, you can remove the Playground redirect URI from your Google OAuth client. Google's guide recommends doing this to reduce exposure.

**Important:** In Google's **External / Testing** mode, authorization including the YouTube scopes generally expires after seven days. For long-lived automation, prefer **Personal** mode where eligible, or another compliant long-lived OAuth configuration.

## Prepare the video for the GitHub workflow

The uploader expects a GitHub Actions **artifact containing exactly one MP4 (or MOV)** and, optionally, one JPG/PNG thumbnail. An MP3-only audiobook artifact is *not* a video and cannot be uploaded directly to YouTube. Your FFmpeg video-assembly job should export a self-contained MP4, then add:

```yaml
- name: Package video for YouTube
  uses: actions/upload-artifact@v4
  with:
    name: youtube-ready-video
    path: |
      output/audiobook.mp4
      output/thumbnail.jpg
    retention-days: 30
```

Find that job's numeric **run ID** in its GitHub Actions URL (`/actions/runs/123456789`).

For the Luther project, the independent 4,588-character Gospel-centered description is already in `youtube_upload/metadata/luther_1522.json`. Duplicate that JSON for the next audiobook and change only its specific title, introduction, and credits while retaining the approved Gospel, disclaimer, and personal-contact section. The script enforces YouTube's 5,000-character description and 100-character title limits.

## Validate or publish

Open **[YouTube API Uploader (no vidIQ)](https://github.com/endelofaustin/didathing/actions/workflows/youtube-api-uploader.yml)** and choose **Run workflow** on `main`.

- `artifact_run_id`: GitHub run ID of your video-assembly job (not the MP3-only narration job)
- `artifact_name`: usually `youtube-ready-video`
- `metadata_file`: e.g. `youtube_upload/metadata/luther_1522.json`
- `visibility`: `private`, `unlisted`, or `public` — choose explicitly
- `publish`: **unchecked** to validate the metadata and video without uploading, or **checked** to upload to YouTube

The workflow will download the artifact using GitHub's built-in read token, verify the expected channel, then upload through a resumable YouTube API session. If one image is included, the workflow will also attempt the custom thumbnail. It saves the returned YouTube URL and a non-sensitive receipt in the GitHub run's summary/artifacts.

**Do not blindly rerun an upload job that fails after the upload starts.** YouTube may have successfully created the video even if the job later fails. Check the video's URL, workflow receipt, and YouTube Studio before attempting again to prevent duplicates.

For local testing:
```bash
python -m unittest discover -s youtube_upload -p 'test_*.py' -v
python youtube_upload/uploader.py --metadata youtube_upload/metadata/luther_1522.json --validate-only
python youtube_upload/uploader.py --metadata youtube_upload/metadata/luther_1522.json --video ./audiobook.mp4 --visibility private
```

Only `--publish` transmits an upload; the local default prints a dry-run preview. For a local actual publish, set the same three OAuth environment variables and add `--publish` and `--expected-channel-id UC_MLwosrdFohed-oRiohxLw`.

## Limits and security

The YouTube Data API's video-upload quota is separate from vidIQ's limits, but YouTube still applies channel-level daily limits, copyright restrictions, account verification, and policy checks. As of November 2, 2026, Google says uploads from unverified YouTube API projects are no longer automatically private-only.

Never commit client-secret JSON, refresh tokens, or access tokens. The workflow has read-only GitHub permissions. It uploads only via manual workflow dispatch when `publish` is explicitly true, never via a code push. All Gospel and historical text is maintained as ordinary, reviewable metadata; the uploader itself does not generate or change theological content.

Official references: [YouTube upload guide](https://developers.google.com/youtube/data/guides/uploading_a_video), [YouTube API reference](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert), [GitHub artifact download](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts).

## Manage EXISTING videos and playlists without vidIQ

This repository also includes a dedicated [YouTube Channel Manager workflow](https://github.com/endelofaustin/didathing/actions/workflows/youtube-channel-manager.yml). It edits existing uploads **without reuploading MP4s** and does not require vidIQ or vidIQ credits.

Supported operations:
- Update approved titles without changing the description, tags, or video privacy.
- Append a separately approved Gospel/contact text file **exactly** to an existing video description. Existing history, theological warnings, source credits, and all other description text remain intact. A repeated run detects the already-appended text and does not duplicate it.
- Set an approved JPG/PNG thumbnail when that asset has been added to the repository.
- Create public playlists and add owned videos without duplicating playlist entries.

This manager does **not** change the channel name or profile avatar, and currently leaves the channel-wide About text and banner to YouTube Studio. YouTube's API explicitly forbids changing the main channel title via `channels.update`. Channel-wide branding can be added later with a separate review of how the API preserves existing settings.

### One-time Google OAuth authorization for management

**Important:** The old uploader token originally requested only `youtube.upload` and `youtube.readonly`. Editing existing video metadata and playlists requires the additional scope **`youtube.force-ssl`**. The updated `setup_oauth.py` requests all three scopes. Rerun it on your own computer and replace the three GitHub repository secrets with the returned values; never paste your tokens in chat or put them in a public repo. If you have not set up the original uploader OAuth yet, do the one-time setup described above.

### The six prepared updates

The checked-in `youtube_upload/manifests/example_refresh.json` references your six existing public videos. Their titles match the choices approved for your channel, and each `youtube_upload/addenda/append_VIDEOID.txt` contains verbatim excerpts from your already approved Gospel statement, historical disclaimer, and personal-contact text. The full statement fits the Luther Galatians video; the other descriptions use selected approved sections so they fit within the 5,000-character limit. **No history or disclaimer is discarded, and the tool will refuse an oversized description rather than shorten anything.**

To preview **without modifying YouTube**, go to the workflow, select `main`, choose **Run workflow**, leave `apply_changes` unchecked, and use this plan:

```
youtube_upload/manifests/example_refresh.json
```

The preview requires working OAuth secrets so it can retrieve the **current** text from YouTube and report what will change. The offline command below validates paths and JSON with no credentials:

```bash
python youtube_upload/manage.py \
  --plan youtube_upload/manifests/example_refresh.json --check-plan
```

When you have reviewed the exact titles, addenda and any thumbnail images, run the workflow again with `apply_changes` checked, or locally use `--apply`. Each run checks that the authorized Google account controls `UC_MLwosrdFohed-oRiohxLw` and that every video belongs to it. **There is no schedule and no automatic publication**. A code push only runs tests.

Custom thumbnails are deliberately not in the initial text-only GitHub patch. For a given video, upload its approved image under `youtube_upload/assets/` and add, for example, `"thumbnailFile": "youtube_upload/assets/Thumbnail_hrTiAYYibaU.jpg"` to that video's plan object. A preview validates the file; applying writes it. Do not claim thumbnails were updated until that operation completes.

### Managing playlists

Create a separate plan or add a `playlists` array to an approved plan. This example creates a playlist and adds two already owned videos:

```json
{
  "expectedChannelId": "UC_MLwosrdFohed-oRiohxLw",
  "videos": [],
  "playlists": [{
    "title": "Reformation Audiobooks",
    "description": "Historic Christian works read in English.",
    "videoIds": ["hrTiAYYibaU", "iyHn-KBT_NQ"]
  }]
}
```

The script checks existing playlists and their contents before inserting. To avoid unintentional duplicates, use unique playlist titles. The workflow does not delete or privatize any video.

### Technical and privacy safeguards

The management API uses `videos.list` followed by `videos.update(part="snippet")`. It preserves the video's current title (unless changed), full description (except the literal approved addition), category ID, tags, and default language. **It never sends the `status` part**, so existing privacy and made-for-kids settings remain untouched. YouTube's API replaces the mutable fields in the parts you update, which is why read/merge/write is essential. The process is not a substitute for Google verification and remains subject to YouTube's API quotas and policies.

The workflow writes a non-sensitive receipt. If Google refuses a write or a run fails after some updates, review YouTube Studio and the receipt before retrying.
