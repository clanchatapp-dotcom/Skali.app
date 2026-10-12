# Skali.app — Import Into This Workspace

Skali.app is an existing social media app that combines Facebook, Instagram, Telegram and TikTok-style features in one place.
This plan only brings the uploaded project ("Skali.app-Web-test-run (3).zip") into this workspace, exactly as it is, and checks that it starts in preview.

## Who it's for
- The owner of Skali.app, who wants the full existing codebase in this space with nothing lost, moved or rewritten.

## Core features and experience
- Every file and folder from the zip lands in /app in its original structure, with the same names and nesting.
- Nothing from the zip is deleted, renamed, moved or edited, including .env files, config, assets and hidden files.
- The starter template that was already in this space is kept whole in a separate backup folder, so zip files with the same names do not overwrite it.
- Existing credentials in the zip's .env files (Supabase, MongoDB, Firebase, Google Auth, LiveKit) are used as they are.
- Once imported, the app is started in preview to confirm the frontend and backend come up.

## User flow
1. The zip is downloaded and unpacked.
2. The starter template files are copied to a backup folder (e.g. /app/_starter_template_backup) before anything else happens.
3. The zip contents are placed into /app exactly as packaged.
4. A file-for-file check confirms that everything in the zip is now in /app.
5. A run check is done in preview. The user gets a report of what started, what didn't, and why.

## UI/UX feel
- No changes. The app keeps its own design, screens and behaviour.

## Implementation phases
- **Phase 1 (MVP, now):** Back up the starter template, import the zip as-is, check every file is there, and run a preview check with a status report.
- **Phase 2 (later, only on request):** Fix anything that stops the app running in preview, with the user's approval for each change.
- **Phase 3 (later, only on request):** New features, redesign or deployment from this space.

## Assumptions
- "Do not delete or move anything" covers everything in the zip. The only thing relocated is the starter template that was already here, and it is kept in full in a backup folder, not deleted.
- If the zip has a single top-level folder (e.g. "Skali.app-Web-test-run/"), its contents go directly into /app, so frontend/backend sit where the zip's structure puts them. Everything inside that folder stays exactly as it is.
- If the zip includes its own .git folder, node_modules or build output, they are imported unchanged.
- The preview run check does not change any code. If something blocks the app from starting here (for example a different port, the start command, or Render-specific URLs in .env), it goes in the report and nothing is fixed without approval.
- Render URLs and production settings in the .env files stay unchanged. Because of that, parts of the preview may still talk to the live Render services.
- Dependencies may be installed so the run check can happen. This only adds packages and doesn't change source files.
