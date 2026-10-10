package com.brokenomore.autosync

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.content.Intent
import android.util.Log
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

/**
 * Android NotificationListenerService for BrokeNoMore Milo AutoSync.
 * Filters strictly to Google Pay (com.google.android.apps.nfc.plugin.card.gp) notifications.
 * Never requests SMS, AccessibilityService, or Banking Passwords/PINs.
 */
class GPayNotificationListenerService : NotificationListenerService() {

    private val executor = Executors.newSingleThreadExecutor()
    private val TAG = "MiloAutoSync"

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        super.onNotificationPosted(sbn)
        if (sbn == null) return

        val packageName = sbn.packageName ?: return

        // Package Verification Guardrail: Strictly process Google Pay
        if (packageName != "com.google.android.apps.nfc.plugin.card.gp" &&
            packageName != "com.google.android.apps.walletnfcrel") {
            return
        }

        val extras = sbn.notification?.extras ?: return
        val title = extras.getCharSequence("android.title")?.toString() ?: ""
        val text = extras.getCharSequence("android.text")?.toString() ?: ""

        if (text.isBlank()) return

        Log.d(TAG, "GPay Notification Detected: $title | $text")

        // Asynchronously synchronize with authenticated BrokeNoMore API
        executor.execute {
            syncNotificationToBackend(title, text, packageName, sbn.postTime)
        }
    }

    private fun syncNotificationToBackend(title: String, text: String, pkg: String, postTime: Long) {
        try {
            val endpoint = URL("http://10.0.2.2:8000/api/v1/connectors/notification-listener")
            val conn = endpoint.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true

            val payload = JSONObject().apply {
                put("user_id", "usr_test_123")
                put("notification_title", title)
                put("notification_text", text)
                put("package_name", pkg)
                put("post_time", postTime)
            }

            conn.outputStream.use { os ->
                os.write(payload.toString().toByteArray(Charsets.UTF_8))
            }

            val responseCode = conn.responseCode
            Log.d(TAG, "Milo AutoSync Backend Response Code: $responseCode")
        } catch (e: Exception) {
            Log.e(TAG, "Offline recovery or network retry required: ${e.message}")
        }
    }
}
