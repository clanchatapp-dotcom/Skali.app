package app.skali.mobile;

import android.content.ContentResolver;
import android.content.Context;
import android.os.Build;
import android.os.Bundle;
import android.util.AttributeSet;
import android.util.Base64;
import android.util.Log;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;

import androidx.core.view.inputmethod.EditorInfoCompat;
import androidx.core.view.inputmethod.InputConnectionCompat;
import androidx.core.view.inputmethod.InputContentInfoCompat;

import com.getcapacitor.CapacitorWebView;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;

/**
 * StickerWebView — a CapacitorWebView that accepts rich content (stickers / GIFs / images)
 * sent by the Android system keyboard via the CommitContent API.
 *
 * Android only delivers keyboard stickers to input fields that declare supported MIME types
 * and wrap their InputConnection with InputConnectionCompat. A plain WebView doesn't, so we
 * override onCreateInputConnection here. When the keyboard commits a sticker we read its bytes,
 * turn them into a data: URL and dispatch a DOM CustomEvent ('skaliKeyboardSticker') that the web
 * app listens for and sends into the current DM.
 *
 * Swapped in for the default CapacitorWebView via app/res/layout/bridge_layout_main.xml.
 */
public class StickerWebView extends CapacitorWebView {

    private static final String[] MIME_TYPES = new String[]{
            "image/png", "image/gif", "image/webp", "image/jpeg"
    };

    public StickerWebView(Context context, AttributeSet attrs) {
        super(context, attrs);
    }

    @Override
    public InputConnection onCreateInputConnection(EditorInfo outAttrs) {
        InputConnection ic = super.onCreateInputConnection(outAttrs);
        // Advertise that this field can receive image content from the IME.
        EditorInfoCompat.setContentMimeTypes(outAttrs, MIME_TYPES);
        if (ic == null) {
            return null;
        }

        InputConnectionCompat.OnCommitContentListener callback =
                (InputContentInfoCompat info, int flags, Bundle opts) -> {
                    boolean granted = false;
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N_MR1
                            && (flags & InputConnectionCompat.INPUT_CONTENT_GRANT_READ_URI_PERMISSION) != 0) {
                        try {
                            info.requestPermission();
                            granted = true;
                        } catch (Exception e) {
                            Log.w("StickerWebView", "requestPermission failed", e);
                            return false;
                        }
                    }
                    try {
                        ContentResolver cr = getContext().getContentResolver();
                        String mime = "image/png";
                        try {
                            if (info.getDescription() != null && info.getDescription().getMimeTypeCount() > 0) {
                                mime = info.getDescription().getMimeType(0);
                            }
                        } catch (Exception ignored) {}

                        byte[] bytes;
                        try (InputStream is = cr.openInputStream(info.getContentUri())) {
                            bytes = readAll(is);
                        }
                        if (bytes == null || bytes.length == 0) {
                            return false;
                        }
                        final String dataUrl = "data:" + mime + ";base64,"
                                + Base64.encodeToString(bytes, Base64.NO_WRAP);
                        // Deliver to the web layer on the UI thread.
                        post(() -> evaluateJavascript(
                                "window.dispatchEvent(new CustomEvent('skaliKeyboardSticker',{detail:'"
                                        + dataUrl + "'}));", null));
                        return true;
                    } catch (Exception e) {
                        Log.e("StickerWebView", "commitContent failed", e);
                        return false;
                    } finally {
                        if (granted) {
                            try { info.releasePermission(); } catch (Exception ignored) {}
                        }
                    }
                };

        return InputConnectionCompat.createWrapper(ic, outAttrs, callback);
    }

    private static byte[] readAll(InputStream is) throws Exception {
        if (is == null) return null;
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = is.read(buf)) != -1) {
            out.write(buf, 0, n);
        }
        return out.toByteArray();
    }
}
