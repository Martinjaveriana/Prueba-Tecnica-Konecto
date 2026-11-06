package com.series76.assistant.data

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface ApiService {
    @POST("api/conversation")
    suspend fun converse(@Body request: ConversationRequest): ConversationResponse

    @GET("api/sessions")
    suspend fun sessions(): List<SessionSummary>

    @GET("api/sessions/{id}/messages")
    suspend fun session(@Path("id") id: String): SessionDetail
}
