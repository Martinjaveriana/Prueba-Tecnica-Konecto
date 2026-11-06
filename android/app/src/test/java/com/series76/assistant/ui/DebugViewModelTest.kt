package com.series76.assistant.ui

import com.series76.assistant.FakeRepository
import com.series76.assistant.MainDispatcherRule
import com.series76.assistant.data.AppError
import com.series76.assistant.data.Focus
import com.series76.assistant.data.Message
import com.series76.assistant.data.SessionDetail
import com.series76.assistant.ui.debug.DebugUiState
import com.series76.assistant.ui.debug.DebugViewModel
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class DebugViewModelTest {
    @get:Rule val main = MainDispatcherRule()

    private val repository = FakeRepository()
    private val debug = Json.decodeFromString<JsonObject>("""{"model":"m","tool_calls":[]}""")

    private fun session(vararg messages: Message) =
        SessionDetail("s1", "t", "2026-11-06T18:00:00Z", "2026-11-06T18:00:00Z", messages.toList())

    private fun message(id: Long, role: String, debug: JsonObject?) =
        Message(id, role, "text", emptyList(), false, Focus(), debug, "2026-11-06T18:00:00Z")

    @Test fun `shows the debug of the answer asked for`() {
        repository.details = mapOf("s1" to session(message(1, "user", null), message(2, "assistant", debug)))
        val state = DebugViewModel(repository, "s1", 2).state.value
        assertTrue(state is DebugUiState.Loaded)
        assertEquals("m", (state as DebugUiState.Loaded).info.model)
    }

    @Test fun `a message without debug says so`() {
        repository.details = mapOf("s1" to session(message(1, "user", null)))
        assertEquals(DebugUiState.NoDebug, DebugViewModel(repository, "s1", 1).state.value)
        assertEquals(DebugUiState.NoDebug, DebugViewModel(repository, "s1", 99).state.value)
    }

    @Test fun `a conversation that no longer exists is an error`() {
        assertEquals(DebugUiState.Failed(AppError.NotFound), DebugViewModel(repository, "missing", 1).state.value)
    }

    @Test fun `a backend that is down can be retried`() {
        repository.error = AppError.Unreachable
        val viewModel = DebugViewModel(repository, "s1", 2)
        assertEquals(DebugUiState.Failed(AppError.Unreachable), viewModel.state.value)
        repository.error = null
        repository.details = mapOf("s1" to session(message(2, "assistant", debug)))
        viewModel.load()
        assertTrue(viewModel.state.value is DebugUiState.Loaded)
    }
}
