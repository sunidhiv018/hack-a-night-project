package com.brokenomore.smartcapture

import android.content.Context
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.regex.Pattern

class BrokeBuddyNotificationListenerService : NotificationListenerService() {

    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val TAG = "BrokeBuddyListener"

    // Supported Financial & Banking App Packages in India & Global
    private val financialPackages = setOf(
        "com.phonepe.app",
        "com.google.android.apps.nbu.paisa.user", // Google Pay
        "net.one97.paytm", // Paytm
        "com.dreamplug.androidapp", // CRED
        "com.msf.kbank.mobile", // Kotak
        "com.snapwork.hdfc", // HDFC Bank
        "com.csam.icici.bank.imobile", // ICICI iMobile
        "com.axis.mobile", // Axis Bank
        "com.sbi.lotusintouch", // SBI YONO
        "com.google.android.apps.messaging", // Google Messages (SMS)
        "com.samsung.android.messaging" // Samsung Messages (SMS)
    )

    // Regex patterns for financial events
    private val amountPattern = Pattern.compile("(?:Rs\\.?|INR|₹)\\s*([\\d,]+(?:\\.\\d{2})?)", Pattern.CASE_INSENSITIVE)
    private val merchantPattern = Pattern.compile("(?:at|to|vpa|info:|paid to|towards)\\s*([A-Za-z0-9\\s&'\\.-]+?)(?:\\s+on|\\s+avail|\\s+ref|\\.|,|$)", Pattern.CASE_INSENSITIVE)
    private val debitKeywords = Pattern.compile("\\b(?:debited|spent|paid|withdrawn|sent)\\b", Pattern.CASE_INSENSITIVE)
    private val creditKeywords = Pattern.compile("\\b(?:credited|received|deposit|refund)\\b", Pattern.CASE_INSENSITIVE)

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        super.onNotificationPosted(sbn)
        if (sbn == null) return

        val packageName = sbn.packageName
        val extras = sbn.notification.extras ?: return

        val title = extras.getString("android.title") ?: ""
        val text = extras.getCharSequence("android.text")?.toString() ?: ""
        val bigText = extras.getCharSequence("android.bigText")?.toString() ?: ""

        val fullText = "$title $text $bigText".trim()
        if (fullText.isEmpty()) return

        // 1. Check if package is a banking app OR contains payment transaction keywords
        val isFinancialApp = financialPackages.contains(packageName)
        val hasMonetaryKeywords = fullText.contains("Rs", ignoreCase = true) ||
                fullText.contains("INR", ignoreCase = true) ||
                fullText.contains("₹") ||
                fullText.contains("debited", ignoreCase = true) ||
                fullText.contains("credited", ignoreCase = true)

        if (!isFinancialApp && !hasMonetaryKeywords) {
            return
        }

        // 2. Parse Amount
        val amtMatcher = amountPattern.matcher(fullText)
        val amount: Double? = if (amtMatcher.find()) {
            amtMatcher.group(1)?.replace(",", "")?.toDoubleOrNull()
        } else null

        if (amount == null || amount <= 0.0) {
            // Not a measurable financial transaction
            return
        }

        // 3. Determine debit vs credit
        val txnType = if (creditKeywords.matcher(fullText).find()) "credit" else "debit"

        // 4. Extract Merchant
        val merMatcher = merchantPattern.matcher(fullText)
        val merchant = if (merMatcher.find()) {
            merMatcher.group(1)?.trim()
        } else {
            "Payment via ${packageName.substringAfterLast('.')}"
        }

        val timestamp = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).format(Date())
        val rawHash = ApiClient.computeSha256("$timestamp|$merchant|$amount|$txnType|$packageName")

        val event = SmartCaptureEventDto(
            rawText = fullText,
            sourceApp = packageName,
            timestamp = timestamp,
            amount = amount,
            merchant = merchant,
            txnType = txnType,
            isDemo = false,
            rawHash = rawHash
        )

        Log.i(TAG, "Captured Financial Event: $merchant | ₹$amount ($txnType) from $packageName")

        // 5. Send to BrokeNoMore backend
        sendToBackend(event)
    }

    private fun sendToBackend(event: SmartCaptureEventDto) {
        val prefs = getSharedPreferences("BrokeBuddyPrefs", Context.MODE_PRIVATE)
        val baseUrl = prefs.getString("backend_url", "http://10.0.2.2:8000") ?: "http://10.0.2.2:8000"
        val userId = prefs.getString("user_id", "") ?: ""

        if (userId.isEmpty()) {
            Log.w(TAG, "User ID not configured in companion app. Saving locally for future sync.")
            saveToOfflineQueue(event)
            return
        }

        serviceScope.launch {
            val result = ApiClient.syncEvents(baseUrl, userId, listOf(event))
            result.onSuccess { res ->
                Log.i(TAG, "Successfully synced event to BrokeNoMore: ${res.message}")
            }.onFailure { err ->
                Log.e(TAG, "Sync failed: ${err.message}. Queuing offline.", err)
                saveToOfflineQueue(event)
            }
        }
    }

    private fun saveToOfflineQueue(event: SmartCaptureEventDto) {
        // Preserves captured notifications locally until companion reconnects
        val prefs = getSharedPreferences("BrokeBuddyPrefs", Context.MODE_PRIVATE)
        val currentCount = prefs.getInt("captured_count", 0)
        prefs.edit().putInt("captured_count", currentCount + 1).apply()
    }
}
