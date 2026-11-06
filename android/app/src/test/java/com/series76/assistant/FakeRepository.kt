package com.series76.assistant

import com.series76.assistant.data.AppError
import com.series76.assistant.data.AppException
import com.series76.assistant.data.ConversationRepository
import com.series76.assistant.data.ConversationResponse
import com.series76.assistant.data.ElectricalRating
import com.series76.assistant.data.Focus
import com.series76.assistant.data.Message
import com.series76.assistant.data.Product
import com.series76.assistant.data.ServiceRating
import com.series76.assistant.data.SessionDetail
import com.series76.assistant.data.SessionSummary
import kotlinx.serialization.json.JsonObject

/** Answers what each test sets, or fails with the error it sets. */
class FakeRepository : ConversationRepository {
    var sessions: List<SessionSummary> = emptyList()
    var details: Map<String, SessionDetail> = emptyMap()
    var error: AppError? = null
    var calls = 0

    /** Each question the app sent, with the session it was sent to. */
    val asked = mutableListOf<Pair<String?, String>>()
    var answer: (sessionId: String?, query: String) -> ConversationResponse = { id, _ -> response(id ?: "new-session") }

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

    override suspend fun ask(sessionId: String?, query: String): ConversationResponse {
        calls++
        asked += sessionId to query
        error?.let { throw AppException(it) }
        return answer(sessionId, query)
    }
}

fun summary(id: String, title: String = "Torque of 762A00-11300000/A?") =
    SessionSummary(id, title, "2026-11-06T18:00:00Z", "2026-11-06T18:05:00Z", 2)

fun message(id: Long, role: String, content: String) =
    Message(id, role, content, emptyList(), false, Focus(), null, "2026-11-06T18:00:00Z")

private var nextMessageId = 100L

fun response(sessionId: String, answer: String = "On/Off gives 150 Nm.", products: List<Product> = emptyList(), focus: Focus = Focus()) =
    ConversationResponse(sessionId, answer, products, false, focus, JsonObject(emptyMap()), nextMessageId++, "2026-11-06T18:00:00Z")

fun product(
    partNumber: String = "762A00-11300000/A",
    role: String = "match",
    services: List<ServiceRating> = listOf(
        ServiceRating("on_off", 1330, 150, 30, 20, null),
        ServiceRating("modulating", 1060, 120, 50, null, 1200),
    ),
    electrical: List<ElectricalRating> = listOf(ElectricalRating(60, 18, 2.3, 4.0), ElectricalRating(50, 21, 2.1, 3.5)),
    hasData: Boolean = true,
) = Product(
    role = role, partNumber = partNumber, alias = "2A", enclosure = "weatherproof", voltageV = 110, phases = 1,
    currentType = "AC", motorPowerW = 40, hasData = hasData, sourcePage = 1,
    serviceRatings = services, electricalRatings = electrical,
)
