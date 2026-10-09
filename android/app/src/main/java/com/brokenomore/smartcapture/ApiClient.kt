package com.brokenomore.smartcapture

import com.google.gson.Gson
import com.google.gson.annotations.SerializedName
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

data class SmartCaptureEventDto(
    @SerializedName("raw_text") val rawText: String,
    @SerializedName("source_app") val sourceApp: String,
    @SerializedName("timestamp") val timestamp: String,
    @SerializedName("amount") val amount: Double?,
    @SerializedName("merchant") val merchant: String?,
    @SerializedName("txn_type") val txnType: String?,
    @SerializedName("category") val category: String? = null,
    @SerializedName("is_demo") val isDemo: Boolean = false,
    @SerializedName("raw_hash") val rawHash: String? = null
)

data class SmartCaptureSyncRequestDto(
    @SerializedName("user_id") val userId: String,
    @SerializedName("events") val events: List<SmartCaptureEventDto>,
    @SerializedName("auto_approve_high_confidence") val autoApprove: Boolean = false
)

data class SmartCaptureSyncResponseDto(
    @SerializedName("success") val success: Boolean,
    @SerializedName("message") val message: String?,
    @SerializedName("data") val data: SyncResultData?
)

data class SyncResultData(
    @SerializedName("total_received") val totalReceived: Int,
    @SerializedName("processed_count") val processedCount: Int,
    @SerializedName("duplicate_count") val duplicateCount: Int,
    @SerializedName("demo_count") val demoCount: Int
)

object ApiClient {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    private val gson = Gson()
    private val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()

    suspend fun syncEvents(
        baseUrl: String,
        userId: String,
        events: List<SmartCaptureEventDto>
    ): Result<SmartCaptureSyncResponseDto> = withContext(Dispatchers.IO) {
        try {
            val cleanBase = baseUrl.trimEnd('/')
            val endpoint = "$cleanBase/api/v1/smart-capture/sync"

            val body = SmartCaptureSyncRequestDto(
                userId = userId,
                events = events,
                autoApprove = false // User review requested for safety
            )

            val jsonBody = gson.toJson(body)
            val request = Request.Builder()
                .url(endpoint)
                .post(jsonBody.toRequestBody(JSON_MEDIA_TYPE))
                .header("Content-Type", "application/json")
                .header("User-Agent", "BrokeBuddy-Android/1.0")
                .build()

            client.newCall(request).execute().use { response ->
                val responseString = response.body?.string() ?: ""
                if (response.isSuccessful) {
                    val result = gson.fromJson(responseString, SmartCaptureSyncResponseDto::class.java)
                    Result.success(result)
                } else {
                    Result.failure(Exception("HTTP Error ${response.code}: $responseString"))
                }
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    fun computeSha256(text: String): String {
        val bytes = MessageDigest.getInstance("SHA-256").digest(text.toByteArray())
        return bytes.joinToString("") { "%02x".format(it) }
    }
}
