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
