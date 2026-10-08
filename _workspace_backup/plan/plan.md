# Skali.app — Import + UI Rearrangement

Bring the existing, already-working Skali.app (Skali.app-Test-run.zip) into this workspace untouched, then get a copy running in the live preview.
In that copy, rearrange the Feed, Messages, Me and bottom bar, separate Live Stories from Content Streaming, and add tap-on-avatar actions.

## Who it's for
The Skali.app owner and their users. The app is already live on Render (frontend + backend, Google auth via Supabase/Firebase, MongoDB Atlas) and everything works. These changes only move and tidy things in the UI.

## Core features and experience

### Import (no changes to the original)
- The zip goes into a new folder, `/app/skali-app`, exactly as it came. This copy is never edited and stays as the reference original.
- Nothing already in `/app` is deleted, moved or overwritten. If a workspace file has to be replaced, it gets backed up first.
- A copy of the code runs in the preview. Only connection settings (keys, addresses) are adjusted there so it can start.

### Feed
- **Remove the "Create a post" box:** the whole box goes, including the Public/Followers/Inner Circle choice, the text box, the tags field, the photo and mic buttons, and the Post button. Posts are made only from the centre **+** button, and that flow keeps all of these options.
- **Pinned top section:** the "My Feed" header, the General / Following / Interests tabs and the stories bar sit at the top and stay in place while the posts scroll underneath.
- The stories bar keeps its current items ("Your story" with its + badge, other users' stories, and the "Watch…" live circle).

### Messages
- **Activity moves into Messages:** a pill button at the top of the Messages page (next to the title) opens Activity, showing the same content as the current Activity tab.
- The pill shows a dot or count when there's unread activity, if the app already tracks this.

### Find
- **Clean search page:** everything under the search bar is removed, including the FOLLOWING chips, the PEOPLE hint and the INTERESTS chips. Only the existing tabs and the search bar remain.
- Searching still works exactly as before: **#** finds people and **@** finds interests. The placeholder text in the search bar explains this.
- **New "Streamers" tab:** added next to the existing Find tabs.
  - **Live now** at the top: creators who are content streaming right now. Tapping one opens the stream to watch.
  - **All creators** below, so viewers can browse streamers who aren't live.
  - A search box to find a streamer by name or handle.

### Settings → Preferences
- **New "Interests" tab:** shows the interests you follow (e.g. @music, @art).
  - Tap to unfollow any interest.
  - Add new ones from the full interests list (gaming, music, art, photography, sport, tech, food, fashion, travel, comedy, sculpting, etc.).
  - Changes here update the same follows the Feed's "Interests" tab uses.

### Bottom bar
- The Activity tab is removed. The bar becomes **Feed · Find · + · Messages · Me**, evenly spaced with the + still in the centre.

### Me (profile)
- **"SKALI PRESENTS" is removed.**
- **Smaller name:** the big display name (e.g. #THISISMAJOR…) gets much smaller so it fits on one line without "…", with the coloured underline sitting fully under it. Very long names shrink to fit, and only get cut off as a last resort.

### Live Stories vs Content Streaming (two separate features)
- **Live Stories:** open to everyone. Started from "Your story" in the stories bar or from the centre **+** button. It appears as a live story ring in the stories bar.
- **Content Streaming:** creators only. Started from the Creator Studio button, which gets renamed from "LIVE" to **"Content Streaming"**. Non-creators never see it.
- The two get their own names, entry points and labels in the UI, so they're never mixed up again.

### Tap a profile picture
- In the Feed (on post authors) and in Messages/DMs (chat list and inside a chat), tapping someone's profile picture opens a small menu with **View profile** and **View story**.
- **View story** only appears when that person has an active story. Otherwise the only option is **View profile**.

## User flow
1. Open the app and land on the Feed. The header, tabs and stories stay pinned while posts scroll.
2. Tap **+** to create a post (with audience, tags, photo or voice) or start a Live Story.
3. Tap any avatar in the Feed or DMs and choose View profile or View story.
4. Messages: the Activity pill at the top opens notifications.
5. Me: a clean profile header with a smaller name. Creators see "Content Streaming" in Creator Studio.
6. Find: search with # or @, or open **Streamers** to see who's live and search for a streamer to watch.
7. Settings → Preferences → **Interests**: manage the interests you follow.

## UI/UX feel
Unchanged look and style. Same dark theme, colours, fonts and buttons. These are layout and placement changes only, with no restyling.

## Implementation phases
- **Phase 1 (MVP, built now):** Import into `/app/skali-app`, run the copy in the preview with your keys, and make all of the changes above in the preview copy.
- **Phase 2:** Further UI rearrangements you ask for after reviewing the preview.
- **Phase 3:** Hand back the updated code (download / GitHub / redeploy to Render, whichever you choose) so the live app gets the changes.

## Assumptions
- `/app/skali-app` stays the untouched original. All edits happen in the preview copy only.
- If the zip doesn't include the keys (Supabase, Firebase, MongoDB Atlas, etc.), you'll provide them, or the values you use on Render.
- Google sign-in may need the preview web address added as an allowed domain in Firebase and Supabase. If so, you'll get exact steps.
- If Live Stories and Content Streaming currently run on the same underlying live system, they keep using it. The separation covers naming, who's allowed, where each is started and where each shows up.
- The "Watch…" circle in the stories bar shows Content Streams. Live Stories show as normal story rings marked "LIVE".
- If the + button doesn't already offer "Live Story", it gets added alongside "Create post".
- The Render deployment is not touched until phase 3.
- "Streamers" lists only creators (the same people who can use Content Streaming). Live streamers show a LIVE badge.
- The full interests list in Settings is the same list Find currently shows, including any custom ones like @Sculpting.
- Removing the chips from Find doesn't remove any follows. They stay manageable in Settings → Preferences → Interests.
