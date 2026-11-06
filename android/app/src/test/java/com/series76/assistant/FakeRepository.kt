package com.series76.assistant

import com.series76.assistant.data.AppError
import com.series76.assistant.data.AppException
import com.series76.assistant.data.ConversationRepository
import com.series76.assistant.data.ConversationResponse
import com.series76.assistant.data.Message
import com.series76.assistant.data.SessionDetail
import com.series76.assistant.data.SessionSummary

/** Answers what each test sets, or fails with the error it sets. */
class FakeRepository : ConversationRepository {
    var sessions: List<SessionSummary> = emptyList()
    var details: Map<String, SessionDetail> = emptyMap()
    var error: AppError? = null
    var calls = 0

    override suspend fun sessions(): List<SessionSummary> {
        calls++
        error?.let { throw AppException(it) }
        return sessions
    }

    override suspend fun session(id: String): SessionDetail {
        calls++
        error?.let { throw AppException(it) }
        return details[id] ?: throw AppException(AppError.NotFound)
    }

    override suspend fun ask(sessionId: String?, query: String): ConversationResponse =
        throw UnsupportedOperationException("Not used before phase 4b")
}

fun summary(id: String, title: String = "Torque of 762A00-11300000/A?") =
    SessionSummary(id, title, "2026-11-06T18:00:00Z", "2026-11-06T18:05:00Z", 2)

fun message(id: Long, role: String, content: String) =
    Message(id, role, content, emptyList(), false, null, "2026-11-06T18:00:00Z")
