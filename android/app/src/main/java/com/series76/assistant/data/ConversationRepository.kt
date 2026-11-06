package com.series76.assistant.data

import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import retrofit2.HttpException
import java.io.IOException

/** The screens talk to this, never to Retrofit, so tests can replace it with a fake. */
interface ConversationRepository {
    suspend fun sessions(): List<SessionSummary>
    suspend fun session(id: String): SessionDetail
    suspend fun ask(sessionId: String?, query: String): ConversationResponse
}

class HttpConversationRepository(
    private val api: ApiService,
    private val json: Json,
) : ConversationRepository {

    override suspend fun sessions() = call { api.sessions() }

    override suspend fun session(id: String) = call { api.session(id) }

    override suspend fun ask(sessionId: String?, query: String) =
        call { api.converse(ConversationRequest(sessionId, query)) }

    private suspend fun <T> call(block: suspend () -> T): T = try {
        block()
    } catch (e: HttpException) {
        throw AppException(errorFor(e), e)
    } catch (e: IOException) {
        throw AppException(AppError.Unreachable, e)
    } catch (e: SerializationException) {
        // The backend answered something this app does not understand: a version mismatch.
        throw AppException(AppError.Unexpected(200), e)
    }

    private fun errorFor(e: HttpException): AppError = when (e.code()) {
        404 -> AppError.NotFound
        503 -> AppError.Unavailable(detailOf(e))
        else -> AppError.Unexpected(e.code())
    }

    private fun detailOf(e: HttpException): String? = try {
        e.response()?.errorBody()?.string()?.let { json.decodeFromString<ErrorBody>(it).detail }
    } catch (_: Exception) {
        null
    }
}
