# Skali.app — Beta test run · Import tree map

Extracted non-destructively (no deletes/moves/renames). Full pristine copy at:
  /app/_skali_import/extracted/Skali.app-Beta-test-run/

## Top-level (excluding node_modules, .git, build/dist)
  .emergent
  .gitconfig
  .github
  .gitignore
  .yarnrc
  DEPLOY.md
  LEGAL.md
  README.md
  SETUP.md
  _workspace_backup
  android
  backend
  backend_smoke_test.py
  backend_test.py
  backend_test_account_tier_coadmin_dm.py
  backend_test_admin_recognition.py
  backend_test_board_reactions_replies_cz.py
  backend_test_board_tier_fix.py
  backend_test_boards.py
  backend_test_call_signaling.py
  backend_test_delete_activity.py
  backend_test_dm_activity_diagnosis.py
  backend_test_dm_enc_regression.py
  backend_test_dm_media_allow_save.py
  backend_test_fcm_push.py
  backend_test_giphy_verification.py
  backend_test_groups_additions.py
  backend_test_handle_change.py
  backend_test_handle_history_tier_limits.py
  backend_test_inner_voice_call.py
  backend_test_media_upload.py
  backend_test_media_upload_fix.py
  backend_test_nicknames_stickers.py
  backend_test_phase5.py
  backend_test_post_wall_edit_inner_perms.py
  backend_test_safety_spine.py
  backend_test_silent_investigation.py
  backend_test_staff_roles.py
  backend_test_upheld_reports.py
  backend_test_upload_diagnosis.py
  backend_test_upload_extended.py
  backend_test_view_once.py
  backend_test_wall.py
  capacitor.config.ts
  check_bucket_config.py
  debug_board_access.py
  deployer-agent-docs
  email_auth_test.py
  eslint.config.js
  frontend
  index.html
  memory
  package.json
  phase1_social_test.py
  phase6_test.py
  plan
  postcss.config.js
  public
  regression_test.py
  render.yaml
  scripts
  skali-app
  smoke_test.py
  src
  tailwind.config.js
  test_admin_management.py
  test_change_password.py
  test_reports
  test_result.md
  tests
  tsconfig.json
  vite.config.ts

## Authoritative (DEPLOYED) source — what Render builds
Backend  (render.yaml rootDir: backend)  -> ./backend/
Frontend (static Vite SPA, yarn build)    -> repo ROOT: ./index.html + ./src/ + ./vite.config.ts
Android  (Capacitor wrapper of the SAME vite build) -> ./android/

## Duplicate / stale copies (NOT built by Render — left untouched):
  ./frontend/        (older divergent Emergent-workspace copy)
  ./skali-app/       (nested full duplicate)
  ./_workspace_backup/ (default Emergent template)

## Located components for the task
  Live Story create (mobile)      : ./src/components/LiveModal.tsx  (setup phase, used via Layout.tsx:635  <LiveModal mode="host" kind="story">)
  Content streaming create (web)  : ./src/components/LiveModal.tsx  (same component; Live.tsx:262 <LiveModal> defaults kind="stream">)
  Category source list            : ./src/lib/liveCategories.ts  +  backend LIVE_CATEGORIES (server.py ~5773)
  Backend create-stream endpoint  : ./backend/server.py  POST /api/live/start  (live_start, ~5930) · model LiveStart (~5784)

## ./src tree
  src/App.tsx
  src/components/AccountBadge.tsx
  src/components/ActivityPill.tsx
  src/components/AdultBadge.tsx
  src/components/AuditPanel.tsx
  src/components/AvatarMenu.tsx
  src/components/CallModal.tsx
  src/components/DobPicker.tsx
  src/components/FindStreamers.tsx
  src/components/IncomingCallScreen.tsx
  src/components/InterestsManager.tsx
  src/components/Layout.tsx
  src/components/LiveAlertBanner.tsx
  src/components/LiveModal.tsx
  src/components/LiveNowBanner.tsx
  src/components/MediaLightbox.tsx
  src/components/OnboardingTour.tsx
  src/components/PostCard.tsx
  src/components/ReplaysSection.tsx
  src/components/RoleBadge.tsx
  src/components/Stories.tsx
  src/components/StreamersPanel.tsx
  src/components/stream/CopyField.tsx
  src/components/stream/ObsStudioPanel.tsx
  src/components/stream/StreamBoundary.tsx
  src/components/stream/StreamChat.tsx
  src/components/stream/StreamMods.tsx
  src/components/stream/StreamVods.tsx
  src/index.css
  src/lib/api.ts
  src/lib/auth.tsx
  src/lib/callAudio.ts
  src/lib/firebase.ts
  src/lib/interests.ts
  src/lib/liveCategories.ts
  src/lib/nativeGoogle.ts
  src/lib/privacyScreen.ts
  src/lib/pushNotifications.ts
  src/lib/statusBar.ts
  src/lib/supabase.ts
  src/lib/theme.ts
  src/lib/ui.tsx
  src/lib/useAndroidBackButton.ts
  src/lib/watchTime.ts
  src/main.tsx
  src/pages/Activity.tsx
  src/pages/Admin.tsx
  src/pages/AuthCallback.tsx
  src/pages/Choices.tsx
  src/pages/Connections.tsx
  src/pages/ConversationInfo.tsx
  src/pages/CreatorAnalytics.tsx
  src/pages/CreatorHub.tsx
  src/pages/Feed.tsx
  src/pages/Groups.tsx
  src/pages/Interest.tsx
  src/pages/Legal.tsx
  src/pages/Links.tsx
  src/pages/Live.tsx
  src/pages/Login.tsx
  src/pages/Messages.tsx
  src/pages/Plans.tsx
  src/pages/Profile.tsx
  src/pages/Reels.tsx
  src/pages/Search.tsx
  src/pages/Settings.tsx
  src/pages/StreamWatch.tsx
  src/pages/Verify.tsx
  src/pages/settings.tsx
  src/pages/skali_Profile.tsx
  src/vite-env.d.ts

## ./backend tree
  backend/creator_analytics.py
  backend/live_alerts.py
  backend/pytest.ini
  backend/requirements.txt
  backend/server.py
  backend/streaming.py
  backend/tests/conftest.py
  backend/tests/test_audit_separation.py
  backend/tests/test_avatar_and_vod.py
  backend/tests/test_block1_hardening.py
  backend/tests/test_block2_block3.py
  backend/tests/test_block4_creator_hub.py
  backend/tests/test_block5_discovery.py
  backend/tests/test_claim_and_profile_stats.py
  backend/tests/test_creator_analytics.py
  backend/tests/test_golive_promos_milestones_watch.py
  backend/tests/test_live_alerts_replays.py
  backend/tests/test_live_notifications.py
  backend/tests/test_live_streaming_tiered.py
  backend/tests/test_livekit_smoke.py
  backend/tests/test_obs_streaming.py
  backend/tests/test_support_and_live_banner.py
