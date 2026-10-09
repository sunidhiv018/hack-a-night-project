# BrokeBuddy Smart Capture — Android Companion Module

Native Android companion service for **BrokeNoMore** to passively capture financial transactions from SMS and push notifications (PhonePe, Google Pay, Paytm, CRED, HDFC, SBI, ICICI, etc.) with zero manual data entry and strict on-device privacy isolation.

---

## Architecture Overview

```
                      ┌─────────────────────────────────────────┐
                      │             Android Device              │
                      │                                         │
┌──────────────────┐  │  ┌───────────────────────────────────┐  │
│  UPI / Banking   │──┼─>│ BrokeBuddy Notification Listener  │  │
│ App Notification │  │  │ (Android NotificationListener)   │  │
└──────────────────┘  │  └─────────────────┬─────────────────┘  │
                      │                    │ On-Device Regex    │
                      │                    │ & Privacy Filter   │
                      │                    ▼                    │
                      │  ┌───────────────────────────────────┐  │
                      │  │   SHA-256 Duplicate Detector      │  │
                      │  │   & Structured DTO Formatter      │  │
                      │  └─────────────────┬─────────────────┘  │
                      └────────────────────┼────────────────────┘
                                           │ Encrypted HTTPS POST
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │          BrokeNoMore Backend            │
                      │        /api/v1/smart-capture/sync       │
                      │                                         │
                      │  • ML Category Predictor                │
                      │  • Duplicate Flagging                   │
                      │  • Demo Isolation Shield                │
                      │  • Staged for Review Queue              │
                      └─────────────────────────────────────────┘
```

---

## Features

1. **Android `NotificationListenerService`**:
   - Listens exclusively to verified Indian and global banking/payment apps (`com.phonepe.app`, `com.google.android.apps.nbu.paisa.user`, `net.one97.paytm`, `com.dreamplug.androidapp`, etc.) and SMS messaging gateways.
2. **Deterministic On-Device Parsing**:
   - Extracts monetary amounts (`₹`, `INR`, `Rs.`), merchant/payee names, and transaction type (`debit` vs `credit`).
3. **On-Device Privacy & Security Guard**:
   - Filters out private chats, personal messages, OTPs, and balance inquiries. Only transaction confirmation notifications are processed.
4. **Offline Queueing**:
   - If device is offline, pending transaction events are safely queued and retried when network connectivity is restored.
5. **Deduplication Checksum**:
   - Calculates a SHA-256 fingerprint from `timestamp + merchant + amount + txnType + package` to prevent double-counting.

---

## Setup & Running the Companion App

### Prerequisites
- Android Studio Iguana / Jellyfish (or command-line Gradle 8.2+)
- Android SDK 34 (Minimum Android 8.0 / API 26)

### 1. Open the project in Android Studio
Open the `android/` directory in Android Studio. Gradle will sync dependencies (`OkHttp`, `Gson`, `Coroutines`, `Material Components`).

### 2. Run on Emulator or Physical Device
```bash
cd android
./gradlew assembleDebug
```
Install the generated APK onto your test phone or emulator:
```bash
adb install app/build/outputs/apk/debug/app-debug.apk
```

### 3. Grant Notification Access Permission
1. Launch the **BrokeBuddy Smart Capture** companion app on your phone.
2. Tap **"Grant Notification Access"**.
3. Toggle the switch to **Allow** for *BrokeBuddy Transaction Listener*.

### 4. Configure Backend URL & User ID
1. In the app settings screen, enter your BrokeNoMore backend URL:
   - For Android Emulator: `http://10.0.2.2:8000`
   - For physical device on same Wi-Fi: `http://192.168.x.x:8000`
   - For production / cloud: `https://your-backend.railway.app` or Vercel URL
2. Enter your BrokeNoMore **User ID** (copy from Web App Profile / Settings).
3. Tap **"Save Configuration"**.

### 5. Send Test Transaction
Tap **"Send Test Capture Event"** in the app to immediately verify end-to-end communication with your BrokeNoMore Smart Capture Review Queue.
