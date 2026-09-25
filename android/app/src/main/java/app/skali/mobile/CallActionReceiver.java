package app.skali.mobile;

import android.app.NotificationManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.util.Log;

import androidx.annotation.NonNull;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Handles the Decline action from the incoming-call notification while
 * the app is out. Cancels the notification and fires POST /api/call/decline
 * on a background thread so the caller stops waiting.
 *
 * The auth token and API base URL are stashed in SharedPreferences by the
 * JS layer at login time -- see the "Web-side wiring" section in the README.
 */
public class CallActionReceiver extends BroadcastReceiver {

    public static final String ACTION_DECLINE = "app.skali.mobile.CALL_DECLINE";

    private static final String TAG = "CallActionReceiver";

    // Keep in sync with pushNotifications.ts.
    private static final String PREFS_NAME     = "skali_call_prefs";
    private static final String KEY_API_BASE   = "api_base_url";
    private static final String KEY_AUTH_TOKEN = "auth_token";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null) return;
        String action = intent.getAction();
        if (!ACTION_DECLINE.equals(action)) return;

        String room   = intent.getStringExtra("room");
        String peer   = intent.getStringExtra("from_handle");
        int notifId   = intent.getIntExtra("notif_id", 0);

        // Kill the notification immediately -- the user has decided.
        NotificationManager nm = (NotificationManager)
                context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm != null && notifId != 0) nm.cancel(notifId);

        SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        final String apiBase = prefs.getString(KEY_API_BASE, null);
        final String token   = prefs.getString(KEY_AUTH_TOKEN, null);

        if (apiBase == null || token == null || room == null || peer == null) {
            Log.w(TAG, "Missing decline params, skipping backend call");
            return;
        }

        final String payload = "{\"peer\":" + jsonString(peer)
                             + ",\"room\":" + jsonString(room)
                             + "}";

        new Thread(() -> postDecline(apiBase, token, payload)).start();
    }

    private static void postDecline(@NonNull String apiBase, @NonNull String token, @NonNull String payload) {
        HttpURLConnection conn = null;
        try {
            String base = apiBase.endsWith("/") ? apiBase.substring(0, apiBase.length() - 1) : apiBase;
            URL url = new URL(base + "/api/call/decline");
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(5000);
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("Authorization", "Bearer " + token);
            try (OutputStream os = conn.getOutputStream()) {
                os.write(payload.getBytes(StandardCharsets.UTF_8));
            }
            int code = conn.getResponseCode();
            Log.i(TAG, "decline POST -> " + code);
        } catch (Exception e) {
            Log.w(TAG, "decline POST failed: " + e.getMessage());
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private static String jsonString(String s) {
        if (s == null) return "null";
        StringBuilder sb = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\': sb.append("\\\\"); break;
                case '"':  sb.append("\\\"");  break;
                case '\n': sb.append("\\n");  break;
                case '\r': sb.append("\\r");  break;
                case '\t': sb.append("\\t");  break;
                default:
                    if (c < 0x20) sb.append(String.format("\\u%04x", (int) c));
                    else sb.append(c);
            }
        }
        return sb.append("\"").toString();
    }
}
