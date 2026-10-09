package com.brokenomore.smartcapture

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.text.TextUtils
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var etBackendUrl: EditText
    private lateinit var etUserId: EditText
    private lateinit var tvListenerStatus: TextView
    private lateinit var btnEnablePermission: Button
    private lateinit var btnSaveConfig: Button
    private lateinit var btnSendTestCapture: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        etBackendUrl = findViewById(R.id.etBackendUrl)
        etUserId = findViewById(R.id.etUserId)
        tvListenerStatus = findViewById(R.id.tvListenerStatus)
        btnEnablePermission = findViewById(R.id.btnEnablePermission)
        btnSaveConfig = findViewById(R.id.btnSaveConfig)
        btnSendTestCapture = findViewById(R.id.btnSendTestCapture)

        loadSavedConfig()
        updatePermissionStatus()

        btnEnablePermission.setOnClickListener {
            // Open Android Notification Listener settings
            startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
        }

        btnSaveConfig.setOnClickListener {
            val url = etBackendUrl.text.toString().trim()
            val uid = etUserId.text.toString().trim()

            if (url.isEmpty()) {
                Toast.makeText(this, "Please enter BrokeNoMore backend URL", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            val prefs = getSharedPreferences("BrokeBuddyPrefs", Context.MODE_PRIVATE)
            prefs.edit()
                .putString("backend_url", url)
                .putString("user_id", uid)
                .apply()

            Toast.makeText(this, "Configuration saved successfully!", Toast.LENGTH_SHORT).show()
        }

        btnSendTestCapture.setOnClickListener {
            val url = etBackendUrl.text.toString().trim()
            val uid = etUserId.text.toString().trim()

            if (uid.isEmpty()) {
                Toast.makeText(this, "Enter a User ID first", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            // Send a test transaction capture to the backend
            lifecycleScope.launch {
                val testEvent = SmartCaptureEventDto(
                    rawText = "Rs. 250.00 debited from A/C XX1294 at Blue Tokai Coffee on 10-Oct-2026. Avail Bal Rs 18,250.",
                    sourceApp = "com.phonepe.app",
                    timestamp = "2026-10-10T12:30:00Z",
                    amount = 250.0,
                    merchant = "Blue Tokai Coffee",
                    txnType = "debit",
                    category = "Dining & Food",
                    isDemo = false
                )

                val result = ApiClient.syncEvents(url, uid, listOf(testEvent))
                result.onSuccess {
                    Toast.makeText(this@MainActivity, "Test Sync Success: ${it.message}", Toast.LENGTH_LONG).show()
                }.onFailure {
                    Toast.makeText(this@MainActivity, "Test Sync Failed: ${it.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        updatePermissionStatus()
    }

    private fun loadSavedConfig() {
        val prefs = getSharedPreferences("BrokeBuddyPrefs", Context.MODE_PRIVATE)
        val savedUrl = prefs.getString("backend_url", "http://10.0.2.2:8000")
        val savedUid = prefs.getString("user_id", "")
        etBackendUrl.setText(savedUrl)
        etUserId.setText(savedUid)
    }

    private fun updatePermissionStatus() {
        val isEnabled = isNotificationServiceEnabled()
        if (isEnabled) {
            tvListenerStatus.text = "● Active & Listening for UPI / SMS Notifications"
            tvListenerStatus.setTextColor(0xFF10B981.toInt())
            btnEnablePermission.text = "Permission Granted (Settings)"
        } else {
            tvListenerStatus.text = "● Permission Required: Notifications Not Monitored"
            tvListenerStatus.setTextColor(0xFFEF4444.toInt())
            btnEnablePermission.text = "Grant Notification Access"
        }
    }

    private fun isNotificationServiceEnabled(): Boolean {
        val pkgName = packageName
        val flat = Settings.Secure.getString(contentResolver, "enabled_notification_listeners")
        if (!TextUtils.isEmpty(flat)) {
            val names = flat.split(":")
            for (name in names) {
                val cn = ComponentName.unflattenFromString(name)
                if (cn != null && TextUtils.equals(pkgName, cn.packageName)) {
                    return true
                }
            }
        }
        return false
    }
}
