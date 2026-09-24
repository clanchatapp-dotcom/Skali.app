package app.skali.mobile;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.os.Build;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * CallAudio — routes call audio through the Android voice-communication stream
 * instead of the media stream.
 *
 * The LiveKit web SDK renders remote audio inside the WebView, which by default
 * uses STREAM_MUSIC. That means the hardware volume rocker adjusts "Media"
 * while a call is in progress, and calls play through the loud speaker even
 * when the user expected earpiece routing.
 *
 * On startCall() we:
 *   - Remember the previous audio mode + speakerphone state
 *   - Request transient voice-communication audio focus
 *   - Switch the system into MODE_IN_COMMUNICATION so the volume rocker
 *     controls the in-call stream and routing follows telephony rules
 *
 * On endCall() we abandon focus and restore the previous mode / speakerphone
 * state so the rest of the app (media playback, notifications) is unaffected.
 *
 * setSpeakerOn(boolean) toggles the loud speaker while the call is active.
 */
@CapacitorPlugin(name = "CallAudio")
public class CallAudioPlugin extends Plugin {

    private static final String TAG = "CallAudio";

    private AudioManager audioManager;
    private AudioFocusRequest focusRequest;

    private int previousMode = AudioManager.MODE_NORMAL;
    private boolean previousSpeakerOn = false;
    private boolean active = false;

    private AudioManager am() {
        if (audioManager == null && getContext() != null) {
            audioManager = (AudioManager) getContext()
                    .getSystemService(Context.AUDIO_SERVICE);
        }
        return audioManager;
    }

    @PluginMethod
    public void startCall(final PluginCall call) {
        try {
            final AudioManager manager = am();
            if (manager == null) {
                call.reject("AudioManager unavailable");
                return;
            }

            if (!active) {
                previousMode = manager.getMode();
                previousSpeakerOn = manager.isSpeakerphoneOn();
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                AudioAttributes attrs = new AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build();

                focusRequest = new AudioFocusRequest
                        .Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
                        .setAudioAttributes(attrs)
                        .setAcceptsDelayedFocusGain(false)
                        .setWillPauseWhenDucked(false)
                        .setOnAudioFocusChangeListener(focusChange -> {
                            /* We don't need to react to transient focus loss;
                             * LiveKit's own audio session handles ducking. */
                        })
                        .build();

                manager.requestAudioFocus(focusRequest);
            } else {
                //noinspection deprecation
                manager.requestAudioFocus(
                        null,
                        AudioManager.STREAM_VOICE_CALL,
                        AudioManager.AUDIOFOCUS_GAIN_TRANSIENT);
            }

            manager.setMode(AudioManager.MODE_IN_COMMUNICATION);
            active = true;
            call.resolve();
        } catch (Exception e) {
            call.reject("startCall failed: " + e.getMessage(), e);
        }
    }

    @PluginMethod
    public void endCall(final PluginCall call) {
        try {
            final AudioManager manager = am();
            if (manager == null) {
                call.resolve();
                return;
            }

            try {
                manager.setSpeakerphoneOn(previousSpeakerOn);
            } catch (Exception ignored) { /* not fatal */ }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                if (focusRequest != null) {
                    manager.abandonAudioFocusRequest(focusRequest);
                    focusRequest = null;
                }
            } else {
                //noinspection deprecation
                manager.abandonAudioFocus(null);
            }

            int restore = (previousMode == AudioManager.MODE_INVALID)
                    ? AudioManager.MODE_NORMAL
                    : previousMode;
            manager.setMode(restore);

            active = false;
            call.resolve();
        } catch (Exception e) {
            call.reject("endCall failed: " + e.getMessage(), e);
        }
    }

    @PluginMethod
    public void setSpeakerOn(final PluginCall call) {
        try {
            Boolean on = call.getBoolean("on", Boolean.TRUE);
            final AudioManager manager = am();
            if (manager == null) {
                call.reject("AudioManager unavailable");
                return;
            }
            manager.setSpeakerphoneOn(on != null && on);
            call.resolve();
        } catch (Exception e) {
            call.reject("setSpeakerOn failed: " + e.getMessage(), e);
        }
    }
}
