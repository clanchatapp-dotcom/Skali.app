package app.skali.mobile;

import android.app.Activity;
import android.app.KeyguardManager;
import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.widget.ImageView;
import android.widget.TextView;

/**
 * Full-screen incoming-call screen shown by the full-screen notification
 * intent. This is what makes the phone light up and ring even when the
 * app is force-killed or the phone is locked.
 *
 * Fix 1: Extends Activity (not AppCompatActivity) so the plain
 *         AppTheme.NoActionBarLaunch theme has no style-mismatch crash.
 *
 * Fix 2: Hands off to MainActivity via intent extras only -- no skali://
 *         deep link URI, no deep-link intent-filter needed in the manifest.
 *
 * Two entry points:
 *   1. The full-screen banner pops up (lock screen / notification shade) ->
 *      Activity launched with default action; user taps Accept/Decline here.
 *   2. The user taps the "Answer" notification action button ->
 *      Activity launched with ACTION_ACCEPT and we forward straight to
 *      MainActivity via extras.
 */
public class IncomingCallActivity extends Activity {

    public static final String ACTION_ACCEPT = "app.skali.mobile.CALL_ACCEPT";

    // Extra keys written to the MainActivity intent (read by pushNotifications.ts
    // via Capacitor's getLaunchUrl / appUrlOpen -- we synthesise a skali:// URL
    // from these on the JS side, so the deep-link plumbing in JS stays intact
    // while the Android side never uses a URI intent).
    public static final String EXTRA_ROOM    = "room";
    public static final String EXTRA_HANDLE  = "from_handle";
    public static final String EXTRA_MEDIA   = "media";
    public static final String EXTRA_CALL_ID = "call_id";
    public static final String EXTRA_NOTIF   = "notif_id";

    // -----------------------------------------------------------------------
    // Lifecycle
    // -----------------------------------------------------------------------

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Show over lock screen / wake the screen -- same as the built-in
        // phone dialler does.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true);
            setTurnScreenOn(true);
            KeyguardManager km = (KeyguardManager) getSystemService(KEYGUARD_SERVICE);
            if (km != null) km.requestDismissKeyguard(this, null);
        } else {
            getWindow().addFlags(
                    WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
                  | WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
                  | WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD
                  | WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        }

        setContentView(R.layout.activity_incoming_call);
        renderCaller(getIntent());
        handleAction(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        renderCaller(intent);
        handleAction(intent);
    }

    // -----------------------------------------------------------------------
    // UI
    // -----------------------------------------------------------------------

    private void renderCaller(Intent intent) {
        if (intent == null) return;

        String name   = intent.getStringExtra("from_name");
        String handle = intent.getStringExtra(EXTRA_HANDLE);
        String media  = intent.getStringExtra(EXTRA_MEDIA);

        TextView nameView   = findViewById(R.id.caller_name);
        TextView handleView = findViewById(R.id.caller_handle);
        TextView statusView = findViewById(R.id.call_status);
        ImageView avatar    = findViewById(R.id.caller_avatar);

        if (nameView   != null) nameView.setText(name == null || name.isEmpty() ? "Incoming call" : name);
        if (handleView != null) handleView.setText(handle != null && !handle.isEmpty() ? "#" + handle : "");
        if (statusView != null) statusView.setText("video".equalsIgnoreCase(media)
                ? "Incoming video call…" : "Incoming call…");
        if (avatar != null) avatar.setVisibility(View.VISIBLE);

        View accept  = findViewById(R.id.btn_accept);
        View decline = findViewById(R.id.btn_decline);
        if (accept  != null) accept.setOnClickListener(v  -> acceptCall());
        if (decline != null) decline.setOnClickListener(v -> declineCall());
    }

    private void handleAction(Intent intent) {
        if (intent != null && ACTION_ACCEPT.equals(intent.getAction())) {
            acceptCall();
        }
    }

    // -----------------------------------------------------------------------
    // Actions
    // -----------------------------------------------------------------------

    private void acceptCall() {
        Intent src    = getIntent();
        String room   = src.getStringExtra(EXTRA_ROOM);
        String handle = src.getStringExtra(EXTRA_HANDLE);
        String media  = src.getStringExtra(EXTRA_MEDIA);
        String callId = src.getStringExtra(EXTRA_CALL_ID);
        int notifId   = src.getIntExtra(EXTRA_NOTIF, 0);

        cancelNotification(notifId);

        // Pass call details to MainActivity as plain extras.
        // The JS bridge (pushNotifications.ts) reads
        // window.__SKALI_CALL_ACCEPT__ on startup and dispatches
        // the skali:incoming-call-accept event -- no URI deep link needed.
        Intent open = new Intent(this, MainActivity.class);
        open.setFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK
              | Intent.FLAG_ACTIVITY_CLEAR_TOP
              | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        open.putExtra("skali_call_action", "accept");
        open.putExtra(EXTRA_ROOM,    room   == null ? "" : room);
        open.putExtra(EXTRA_HANDLE,  handle == null ? "" : handle);
        open.putExtra(EXTRA_MEDIA,   media  == null ? "video" : media);
        open.putExtra(EXTRA_CALL_ID, callId == null ? "" : callId);
        startActivity(open);
        finish();
    }

    private void declineCall() {
        Intent src    = getIntent();
        int notifId   = src.getIntExtra(EXTRA_NOTIF, 0);

        Intent decline = new Intent(this, CallActionReceiver.class);
        decline.setAction(CallActionReceiver.ACTION_DECLINE);
        decline.putExtra(EXTRA_ROOM,    src.getStringExtra(EXTRA_ROOM));
        decline.putExtra(EXTRA_HANDLE,  src.getStringExtra(EXTRA_HANDLE));
        decline.putExtra(EXTRA_CALL_ID, src.getStringExtra(EXTRA_CALL_ID));
        decline.putExtra(EXTRA_NOTIF,   notifId);
        sendBroadcast(decline);

        cancelNotification(notifId);
        finish();
    }

    private void cancelNotification(int notifId) {
        NotificationManager nm = (NotificationManager)
                getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm != null && notifId != 0) nm.cancel(notifId);
    }
}
