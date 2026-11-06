package com.series76.assistant.data

import com.series76.assistant.AppContainer
import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/** The real Retrofit setup of the app against a fake server: JSON parsing and error translation. */
class HttpConversationRepositoryTest {
    private val server = MockWebServer()
    private lateinit var repository: ConversationRepository

    @Before fun start() {
        server.start()
        repository = AppContainer(server.url("/").toString()).repository
    }

    @After fun stop() = server.close()

    private fun respond(code: Int, body: String) =
        server.enqueue(MockResponse.Builder().code(code).body(body).addHeader("Content-Type", "application/json").build())

    private suspend fun errorOf(block: suspend () -> Unit): AppError {
        try {
            block()
        } catch (e: AppException) {
            return e.error
        }
        fail("Expected an AppException")
        error("unreachable")
    }

    @Test fun `reads a real backend response with every product field`() = runTest {
        // Saved from GET /api/sessions/{id}/messages: if the backend changes a field name, this fails.
        respond(200, javaClass.getResource("/session_with_options.json")!!.readText())
        val session = repository.session("any")
        val options = session.messages[1].products
        assertEquals(3, options.size)
        assertTrue(options.all { it.role == "option" })
        val first = options.first()
        assertEquals("761A00-11300000/A", first.partNumber)
        assertTrue(first.serviceRatings.isNotEmpty())
        assertTrue(first.electricalRatings.isNotEmpty())
    }

    @Test fun `fields the app does not know are ignored`() = runTest {
        respond(200, """[{"id":"a","title":"t","created_at":"2026-11-06T18:00:00Z","updated_at":"2026-11-06T18:00:00Z","message_count":2,"new_field":1}]""")
        assertEquals("a", repository.sessions().single().id)
    }

    @Test fun `404 is a conversation that does not exist`() = runTest {
        respond(404, """{"detail":"Conversation not found."}""")
        assertEquals(AppError.NotFound, errorOf { repository.session("x") })
    }

    @Test fun `503 keeps the backend's explanation`() = runTest {
        respond(503, """{"detail":"The database is not available yet. Try again in a moment."}""")
        assertEquals(
            AppError.Unavailable("The database is not available yet. Try again in a moment."),
            errorOf { repository.sessions() },
        )
    }

    @Test fun `500 is unexpected`() = runTest {
        respond(500, "Internal Server Error")
        assertEquals(AppError.Unexpected(500), errorOf { repository.sessions() })
    }

    @Test fun `a server that is not running is unreachable`() = runTest {
        val closed = AppContainer("http://127.0.0.1:1/").repository
        assertEquals(AppError.Unreachable, errorOf { closed.sessions() })
    }

    @Test fun `the question is sent in the backend's format`() = runTest {
        respond(503, """{"detail":"x"}""")
        errorOf { repository.ask(null, "Torque of 762A00-11300000/A?") }
        val request = server.takeRequest()
        assertEquals("/api/conversation", request.url.encodedPath)
        assertEquals("""{"query":"Torque of 762A00-11300000/A?"}""", request.body?.utf8())
    }
}
