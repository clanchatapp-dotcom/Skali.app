package app.skali.mobile;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;

import com.getcapacitor.BridgeActivity;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginHandle;

import org.json.JSONObject;

import ee.forgr.capacitor.social.login.GoogleProvider;
import ee.forgr.capacitor.social.login.SocialLoginPlugin;
import ee.forgr.capacitor.social.login.ModifiedMainActivityForSocialLoginPlugin;

public class MainActivity extends BridgeActivity
        implements ModifiedMainActivityForSocialLoginPlugin {

    @Override
    public void onCreate(Bundle savedInstanceState) {

        /*
         * Register app-local Capacitor plugins BEFORE the bridge is created.
         *
         * IMPORTANT:
         * We deliberately do NOT replace Capacitor's WebChromeClient here.
         *
         * Capacitor already handles Android WebView camera/microphone
         * permission requests through BridgeWebChromeClient.
         */
        registerPlugin(PrivacyScreenPlugin.class);
        registerPlugin(CallAudioPlugin.class);

        super.onCreate(savedInstanceState);

        // Inject call-accept extras into the WebView so that
        // bootstrapCallHandoff() in pushNotifications.ts can read them
        // on a cold start (when IncomingCallActivity launched us).
        // Must run after super.onCreate() so getBridge().getWebView() exists.
        injectCallExtras(getIntent());
    }

    /**
     * Called when IncomingCallActivity re-launches us via
     * FLAG_ACTIVITY_SINGLE_TOP while we are already running (warm start).
     */
    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        injectCallExtras(intent);
    }

    /**
     * If the intent carries a skali_call_action extra (written by
     * IncomingCallActivity.acceptCall), serialise all the call extras as a
     * JSON object and inject it as window.__SKALI_CALL_EXTRAS__ in the
     * WebView.  The JS side reads this synchronously at bootstrap, before
     * any React component mounts.
     */
    private void injectCallExtras(Intent intent) {
        if (intent == null) return;
        if (!"accept".equals(intent.getStringExtra("skali_call_action"))) return;

        try {
            JSONObject obj = new JSONObject();
            obj.put("skali_call_action", "accept");
            obj.put("room",        safeStr(intent, "room"));
            obj.put("from_handle", safeStr(intent, "from_handle"));
            obj.put("media",       safeStr(intent, "media"));
            obj.put("call_id",     safeStr(intent, "call_id"));

            String js = "window.__SKALI_CALL_EXTRAS__ = " + obj.toString() + ";";

            // evaluateJavascript runs on the UI thread; the WebView is already
            // created by the time onCreate/onNewIntent reaches this point.
            getBridge().getWebView().post(() ->
                getBridge().getWebView().evaluateJavascript(js, null)
            );
        } catch (Exception e) {
            Log.w("MainActivity", "injectCallExtras failed: " + e.getMessage());
        }
    }

    private String safeStr(Intent intent, String key) {
        String v = intent.getStringExtra(key);
        return v != null ? v : "";
    }

    // -----------------------------------------------------------------------

    @Override
    public void onActivityResult(
            int requestCode,
            int resultCode,
            Intent data
    ) {
        super.onActivityResult(requestCode, resultCode, data);

        /*
         * Google login handling.
         */
        if (requestCode >= GoogleProvider.REQUEST_AUTHORIZE_GOOGLE_MIN
                && requestCode < GoogleProvider.REQUEST_AUTHORIZE_GOOGLE_MAX) {

            PluginHandle pluginHandle =
                    getBridge().getPlugin("SocialLogin");

            if (pluginHandle == null) {
                Log.i(
                        "Google Activity Result",
                        "SocialLogin plugin handle is null"
                );
                return;
            }

            Plugin plugin = pluginHandle.getInstance();

            if (!(plugin instanceof SocialLoginPlugin)) {
                Log.i(
                        "Google Activity Result",
                        "plugin instance is not SocialLoginPlugin"
                );
                return;
            }

            ((SocialLoginPlugin) plugin)
                    .handleGoogleLoginIntent(requestCode, data);
        }
    }

    /*
     * Required marker method for the capgo social-login v7 plugin.
     * Not called directly by application code.
     */
    @Override
    public void IHaveModifiedTheMainActivityForTheUseWithSocialLoginPlugin() {
    }
}
