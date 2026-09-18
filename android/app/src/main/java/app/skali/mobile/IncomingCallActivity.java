package app.skali.mobile;

import android.app.KeyguardManager;
import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.widget.ImageView;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

/**
 * Full-screen incoming-call screen shown by the full-screen notification
 * intent. This is what makes the phone light up and ring even when the
 * app is force-killed or the phone is locked.
 *
 * Two entry points:
 *   1. The user unlocks the phone and taps the notification / the full-screen
 *      pops up on lock -> this Activity is launched with the default action.
 *   2. The user taps "Answer" on the notification -> this Activity is
 *      launched with ACTION_ACCEPT and forwards straight into MainActivity
 *      with the room info as intent extras.
 */
public class IncomingCallActivity extends AppCompatActivity {

    public static final String ACTION_ACCEPT = "app.skali.mobile.CALL_ACCEPT";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Show over lock screen and turn the screen on -- exactly like the
        // real phone app.
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

    private void renderCaller(Intent intent) {
        if (intent == null) return;

        String name   = intent.getStringExtra("from_name");
        String handle = intent.getStringExtra("from_handle");
        String media  = intent.getStringExtra("media");

        TextView nameView   = findViewById(R.id.caller_name);
        TextView handleView = findViewById(R.id.caller_handle);
        TextView statusView = findViewById(R.id.call_status);
        ImageView avatar    = findViewById(R.id.caller_avatar);

        if (nameView   != null) nameView.setText(name == null || name.isEmpty() ? "Incoming call" : name);
        if (handleView != null) handleView.setText(handle != null && !handle.isEmpty() ? "@" + handle : "");
        if (statusView != null) statusView.setText("video".equalsIgnoreCase(media)
                ? "Incoming video call…" : "Incoming call…");
        if (avatar != null) avatar.setVisibility(View.VISIBLE); // placeholder art

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

    // -----------------------------------------------------------------
    // Actions
    // -----------------------------------------------------------------

    private void acceptCall() {
        Intent i = getIntent();
        String room   = i.getStringExtra("room");
        String handle = i.getStringExtra("from_handle");
        String media  = i.getStringExtra("media");
        String callId = i.getStringExtra("call_id");
        int notifId   = i.getIntExtra("notif_id", 0);

        cancelNotification(notifId);

        // Hand the call off to the JS layer through a custom deep link.
        // MainActivity parses this on cold and warm starts.
        Uri deepLink = new Uri.Builder()
                .scheme("skali")
                .authority("call")
                .appendQueryParameter("action", "accept")
                .appendQueryParameter("room",   room   == null ? "" : room)
                .appendQueryParameter("peer",   handle == null ? "" : handle)
                .appendQueryParameter("media",  media  == null ? "" : media)
                .appendQueryParameter("call_id", callId == null ? "" : callId)
                .build();

        Intent open = new Intent(this, MainActivity.class);
        open.setAction(Intent.ACTION_VIEW);
        open.setData(deepLink);
        open.setFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK
              | Intent.FLAG_ACTIVITY_CLEAR_TOP
              | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        startActivity(open);
        finish();
    }

    private void declineCall() {
        Intent i = getIntent();
        int notifId = i.getIntExtra("notif_id", 0);

        Intent decline = new Intent(this, CallActionReceiver.class);
        decline.setAction(CallActionReceiver.ACTION_DECLINE);
        decline.putExtra("room",        i.getStringExtra("room"));
        decline.putExtra("from_handle", i.getStringExtra("from_handle"));
        decline.putExtra("call_id",     i.getStringExtra("call_id"));
        decline.putExtra("notif_id",    notifId);
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
