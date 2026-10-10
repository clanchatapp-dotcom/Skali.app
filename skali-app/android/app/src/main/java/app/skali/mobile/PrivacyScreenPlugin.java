package app.skali.mobile;

import android.view.WindowManager;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * PrivacyScreen — toggles Android FLAG_SECURE on the app window.
 * When enabled, the OS blocks screenshots and screen recording, and shows a
 * blank frame in the app switcher / recents. Used per-thread in DMs and while
 * viewing one-time (disappearing) media.
 *
 * FLAG_SECURE is enforced by the Android OS itself — it cannot be bypassed by
 * normal screenshot tools. (Web and iOS have no equivalent; the UI shows an
 * honest banner there instead.)
 */
@CapacitorPlugin(name = "PrivacyScreen")
public class PrivacyScreenPlugin extends Plugin {

    @PluginMethod
    public void enable(PluginCall call) {
        if (getActivity() != null) {
            getActivity().runOnUiThread(() ->
                getActivity().getWindow().setFlags(
                    WindowManager.LayoutParams.FLAG_SECURE,
                    WindowManager.LayoutParams.FLAG_SECURE));
        }
        call.resolve();
    }

    @PluginMethod
    public void disable(PluginCall call) {
        if (getActivity() != null) {
            getActivity().runOnUiThread(() ->
                getActivity().getWindow().clearFlags(
                    WindowManager.LayoutParams.FLAG_SECURE));
        }
        call.resolve();
    }
}
