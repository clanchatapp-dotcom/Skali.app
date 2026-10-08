package app.skali.mobile;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.media.AudioAttributes;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Build;
import android.util.Log;

import androidx.core.app.NotificationCompat;

import com.google.firebase.messaging.RemoteMessage;

import java.util.Map;

/**
 * Custom Firebase messaging service.
 *
 * We extend Capacitor's own MessagingService so that ordinary push
 * notifications (DMs, replies, generic pings) still flow into the JS
 * Push Notifications API exactly the way they do today. We only take
 * over when the payload's `type` is `incoming_call` — those we render
 * ourselves as a full-screen, phone-style incoming-call notification
 * that also fires even when the app is force-killed.
 *
 * The payload we expect from the backend (data-only FCM message):
 *
 *   {
 *     "type": "incoming_call",
 *     "room": "<livekit-room>",
 *     "from_handle": "<caller-handle>",
 *     "from_name":   "<caller-display-name>",
 *     "from_avatar": "<https-url>",
 *     "media":       "audio" | "video",
 *     "call_id":     "<uuid-per-ring>"     // optional; used as notif id
 *   }
 */
public class CallMessagingService
        extends com.capacitorjs.plugins.pushnotifications.MessagingService {

    private static final String TAG = "CallMessagingService";
    public  static final String CHANNEL_ID_CALLS = "incoming_calls_v1";

    @Override
    public void onMessageReceived(RemoteMessage remoteMessage) {
        Map<String, String> data = remoteMessage.getData();
        String type = data != null ? data.get("type") : null;

        if ("incoming_call".equals(type)) {
            try {
                showIncomingCall(data);
            } catch (Throwable t) {
                Log.e(TAG, "showIncomingCall failed", t);
            }
            return; // never fall through to Capacitor for call rings
        }

        // Everything else keeps its existing behaviour.
        super.onMessageReceived(remoteMessage);
    }

    // -----------------------------------------------------------------
    // Full-screen incoming-call notification
    // -----------------------------------------------------------------

    private void showIncomingCall(Map<String, String> data) {
        Context ctx = getApplicationContext();

        String room    = orEmpty(data.get("room"));
        String handle  = orEmpty(data.get("from_handle"));
        String name    = orEmpty(data.get("from_name"));
        String avatar  = orEmpty(data.get("from_avatar"));
        String media   = orEmpty(data.get("media"));
        String callId  = orEmpty(data.get("call_id"));
        if (name.isEmpty())   name   = handle.isEmpty() ? "Incoming call" : "@" + handle;
        if (media.isEmpty())  media  = "video";
        if (callId.isEmpty()) callId = room.isEmpty() ? String.valueOf(System.currentTimeMillis()) : room;

        // Stable notification id derived from the call id so accept /
        // decline / cancel can all target the same notification.
        int notifId = callId.hashCode();

        ensureCallChannel(ctx);

        // 1) Full-screen intent -> our lock-screen-capable activity.
        Intent fullScreen = new Intent(ctx, IncomingCallActivity.class);
        fullScreen.setFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK
              | Intent.FLAG_ACTIVITY_CLEAR_TOP
              | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        fullScreen.putExtra("room",        room);
        fullScreen.putExtra("from_handle", handle);
        fullScreen.putExtra("from_name",   name);
        fullScreen.putExtra("from_avatar", avatar);
        fullScreen.putExtra("media",       media);
        fullScreen.putExtra("call_id",     callId);
        fullScreen.putExtra("notif_id",    notifId);

        PendingIntent fullScreenPI = PendingIntent.getActivity(
                ctx, notifId, fullScreen, piFlags());

        // 2) Accept -> IncomingCallActivity acts as the accept-and-forward host,
        //    since it can wake / unlock the device and then hand off to the app.
        Intent acceptIntent = new Intent(fullScreen);
        acceptIntent.setAction(IncomingCallActivity.ACTION_ACCEPT);
        PendingIntent acceptPI = PendingIntent.getActivity(
                ctx, notifId + 1, acceptIntent, piFlags());

        // 3) Decline -> receiver hits the backend + cancels the notif.
        Intent declineIntent = new Intent(ctx, CallActionReceiver.class);
        declineIntent.setAction(CallActionReceiver.ACTION_DECLINE);
        declineIntent.putExtra("room",        room);
        declineIntent.putExtra("from_handle", handle);
        declineIntent.putExtra("call_id",     callId);
        declineIntent.putExtra("notif_id",    notifId);
        PendingIntent declinePI = PendingIntent.getBroadcast(
                ctx, notifId + 2, declineIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        // A Person object is what makes the CallStyle template render properly.
        androidx.core.app.Person caller = new androidx.core.app.Person.Builder()
                .setName(name)
                .setImportant(true)
                .build();

        NotificationCompat.Builder b = new NotificationCompat.Builder(ctx, CHANNEL_ID_CALLS)
                .setSmallIcon(android.R.drawable.sym_call_incoming)
                .setContentTitle(name)
                .setContentText("video".equals(media) ? "Incoming video call" : "Incoming call")
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setCategory(NotificationCompat.CATEGORY_CALL)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setOngoing(true)
                .setAutoCancel(false)
                .setFullScreenIntent(fullScreenPI, true)
                .setContentIntent(fullScreenPI);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            // Android 12+ has the dedicated CallStyle template.
            b.setStyle(NotificationCompat.CallStyle.forIncomingCall(
                    caller, declinePI, acceptPI));
        } else {
            b.addAction(new NotificationCompat.Action.Builder(
                    android.R.drawable.sym_action_call, "Answer",  acceptPI).build());
            b.addAction(new NotificationCompat.Action.Builder(
                    android.R.drawable.ic_menu_close_clear_cancel, "Decline", declinePI).build());
        }

        NotificationManager nm = (NotificationManager)
                ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm != null) nm.notify(notifId, b.build());
    }

    private void ensureCallChannel(Context ctx) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = (NotificationManager)
                ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null || nm.getNotificationChannel(CHANNEL_ID_CALLS) != null) return;

        NotificationChannel ch = new NotificationChannel(
                CHANNEL_ID_CALLS, "Incoming calls",
                NotificationManager.IMPORTANCE_HIGH);
        ch.setDescription("Ringing for incoming Skali calls");
        ch.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
        ch.enableVibration(true);
        ch.setVibrationPattern(new long[]{ 0, 1000, 800, 1000, 800, 1000 });
        ch.enableLights(true);
        ch.setBypassDnd(true);

        Uri ring = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE);
        AudioAttributes attrs = new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build();
        ch.setSound(ring, attrs);

        nm.createNotificationChannel(ch);
    }

    private static int piFlags() {
        return PendingIntent.FLAG_UPDATE_CURRENT
             | PendingIntent.FLAG_IMMUTABLE;
    }

    private static String orEmpty(String s) { return s == null ? "" : s; }
}
