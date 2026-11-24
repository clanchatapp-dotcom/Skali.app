#!/usr/bin/env bash
# Archive unsigned, stamp the push entitlement, cloud-sign for App Store, verify, then upload to TestFlight.
# Needs: APPLE_TEAM_ID, ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_PATH, BUILD_NUMBER (App Store Connect key must be Admin).
set -euo pipefail
cd "$(dirname "$0")/../App"
ARCHIVE="$RUNNER_TEMP/Skali.xcarchive"
EXPORT="$RUNNER_TEMP/export"
AUTH=(-allowProvisioningUpdates -authenticationKeyPath "$ASC_KEY_PATH" -authenticationKeyID "$ASC_KEY_ID" -authenticationKeyIssuerID "$ASC_ISSUER_ID")

xcodebuild -workspace App.xcworkspace -scheme App -configuration Release \
  -destination 'generic/platform=iOS' -archivePath "$ARCHIVE" \
  DEVELOPMENT_TEAM="$APPLE_TEAM_ID" CURRENT_PROJECT_VERSION="$BUILD_NUMBER" \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY="" \
  archive

# An unsigned archive carries no entitlements, so export would drop push. Ad-hoc sign the app with them first.
APP="$ARCHIVE/Products/Applications/App.app"
codesign --force --sign - --entitlements App/App.entitlements "$APP"

cat > "$RUNNER_TEMP/ExportOptions.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>method</key><string>app-store-connect</string>
  <key>destination</key><string>export</string>
  <key>teamID</key><string>${APPLE_TEAM_ID}</string>
  <key>signingStyle</key><string>automatic</string>
  <key>uploadSymbols</key><true/>
</dict></plist>
EOF

xcodebuild -exportArchive -archivePath "$ARCHIVE" -exportOptionsPlist "$RUNNER_TEMP/ExportOptions.plist" \
  -exportPath "$EXPORT" "${AUTH[@]}"

IPA=$(ls "$EXPORT"/*.ipa | head -1)
rm -rf "$RUNNER_TEMP/ipa" && mkdir -p "$RUNNER_TEMP/ipa" && unzip -q "$IPA" -d "$RUNNER_TEMP/ipa"
ENT=$(codesign -d --entitlements :- "$RUNNER_TEMP"/ipa/Payload/*.app 2>/dev/null || true)
echo "$ENT"
if ! grep -q "aps-environment" <<<"$ENT"; then
  echo "::error::Signed app is missing the push entitlement (aps-environment). Turn on Push Notifications for app.skali.mobile in Apple Developer > Identifiers."
  exit 1
fi
[ -f "$RUNNER_TEMP"/ipa/Payload/App.app/public/GoogleService-Info.plist ] && echo "Firebase config bundled" || echo "::warning::GoogleService-Info.plist missing - push will stay off"

mkdir -p "$HOME/private_keys" && cp "$ASC_KEY_PATH" "$HOME/private_keys/"
xcrun altool --upload-app -f "$IPA" -t ios --apiKey "$ASC_KEY_ID" --apiIssuer "$ASC_ISSUER_ID"
rm -rf "$HOME/private_keys"
echo "Uploaded build $BUILD_NUMBER to App Store Connect (TestFlight)."
