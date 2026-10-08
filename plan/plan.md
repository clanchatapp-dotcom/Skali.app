# Skali.app Beta Test 2: Code Import + Creator Analytics

The existing Skali.app code from `Skali.app-Beta-test-2.zip` is brought into this workspace exactly as it is and started. An **Analytics** button then goes into the Creator Studio on the profile ("Me") screen, next to Add to Story and Live.
No existing code is deleted or moved. All work is edits and additions.

## Who it's for
- **Creators:** they get one place to see their earnings, subscribers, shop, finances, and how healthy their Inner Circle is.
- **Non-creator users:** their Creator Studio shows only "Add to Story".

## Core features and experience

### Import (unchanged from the approved plan)
- Every file in the zip is imported with its original folder layout. No code is refactored, renamed, or restyled.
- The app is started and checked to confirm it loads. It needs no API keys or secrets.
- If the app's setup clashes with this environment, work stops and the owner is asked before anything is changed.

### Creator Studio button rules
- **Creator accounts** see: Add to Story, Live, and the new **Analytics** button, all in the same row.
- **Non-creator accounts** see only Add to Story. Live and Analytics are hidden. They are not deleted.
- The Analytics button matches the look of the existing buttons (dark rounded style, with a chart icon).

### Analytics screen
Analytics opens as its own full screen with a back arrow and five tabs.

1. **Overview:** monthly revenue, new subscribers, tips, pending payouts, and growth compared with last month (shown as up or down percentages).
2. **Subscribers:** active memberships, churn (members who cancelled or didn't renew), upcoming renewal dates, and active discounts or promos.
3. **Shop:** orders, digital downloads, Printful fulfilment status for each order, and inventory status (in stock, low, or out).
4. **Finance:** payout history, the Skali fee breakdown (gross, fee, and net), tax documents, and an **Export** button that downloads the data as **CSV** or **PDF**.
5. **Creator Health:** returning subscribers, renewal rate, average watch time, subscriber retention, and messages from Inner Circle members.
   - Creator Health is **on by default**.
   - A clear switch hides it for mental health reasons. Each creator's choice is remembered.
   - When it's turned off, the tab shows only a short message and the switch to turn it back on. No numbers are shown.

### Data
- Real data is used wherever the app already tracks it (for example subscriptions, tips, and orders).
- Any number the app doesn't track yet shows sample data with a visible **"Sample"** tag, so it's never confused with real figures.

## User flow
1. A creator opens **Me** and taps **Analytics** in Creator Studio.
2. The Overview tab opens first. The creator swipes or taps between tabs.
3. In Finance, the creator taps Export and picks CSV or PDF, and the file downloads.
4. In Creator Health, the creator can switch the section off. It stays off on later visits until switched back on.
5. The back arrow returns to the profile.

## UI/UX feel
The screen matches the app's current dark theme, purple accents, and rounded cards, so it feels native to Skali. The layout is mobile-first and uses large readable numbers, small trend arrows, and simple charts. Creator Health uses a calm tone with no alarming red warnings.

## Implementation phases
- **Phase 1 (MVP, built now):** Import the zip as-is and get it running. Add the Analytics button with the creator-only rules, plus the full Analytics screen with all five tabs. Use real data where it exists and tagged sample data elsewhere. Include the Creator Health switch and the CSV/PDF export.
- **Phase 2:** Replace sample numbers with real tracking, such as watch time, churn, Printful order sync, and inventory.
- **Phase 3:** Add date-range filters, deeper charts, and optional alerts, such as a renewal-drop alert.

## Assumptions
- The zip holds the complete, current Skali.app source. Where it overlaps the starter template, the zip's files win, and starter files are not deleted.
- The app already tells creator accounts apart from regular accounts. If it doesn't, the owner is asked how to decide before this rule is built.
- Hiding Live for non-creators is new behaviour, made at the owner's request. The "Creator Studio" label stays for everyone.
- The "Skali fee" (renamed from "ClanChat fee") is the platform's cut of creator earnings. A placeholder rate tagged as sample is used for now, and the exact fees will be tuned later.
- Printful is not connected live in Phase 1. Fulfilment status uses existing order data if the app has it, and tagged sample data if not.
- Tax documents are listed as downloadable summaries built from the app's own data. Official tax forms are not generated.
- The Creator Health switch is saved to the creator's account, so it carries across devices.
- If the app's analytics data or setup clashes with how the screen is built, work stops and the owner is asked first. This matches the earlier choice.
