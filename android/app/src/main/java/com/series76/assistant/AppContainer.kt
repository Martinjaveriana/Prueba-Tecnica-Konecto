package com.series76.assistant

import com.series76.assistant.data.ApiService
import com.series76.assistant.data.ConversationRepository
import com.series76.assistant.data.HttpConversationRepository
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit

/**
 * Creates the HTTP client and the repository once, for the whole app.
 * Manual dependency injection: three screens do not need a framework such as Hilt.
 */
class AppContainer(baseUrl: String = BuildConfig.BACKEND_URL) {

    // The backend may add fields; the app ignores the ones it does not use.
    private val json = Json { ignoreUnknownKeys = true }

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        // An answer can take several seconds: the agent calls tools and the model writes.
        .readTimeout(90, TimeUnit.SECONDS)
        .build()

    private val api: ApiService = Retrofit.Builder()
        .baseUrl(baseUrl)
        .client(client)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()
        .create(ApiService::class.java)

    val repository: ConversationRepository = HttpConversationRepository(api, json)
}
