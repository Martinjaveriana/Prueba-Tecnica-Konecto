package com.series76.assistant.ui

import com.series76.assistant.FakeRepository
import com.series76.assistant.MainDispatcherRule
import com.series76.assistant.data.AppError
import com.series76.assistant.data.SessionDetail
import com.series76.assistant.message
import com.series76.assistant.ui.chat.ChatViewModel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test

class ChatViewModelTest {
    @get:Rule val main = MainDispatcherRule()

    private val repository = FakeRepository()

    @Test fun `a new conversation loads nothing`() {
        val viewModel = ChatViewModel(repository, sessionId = null)
        assertEquals(0, repository.calls)
        assertEquals(emptyList<Any>(), viewModel.state.value.messages)
    }

    @Test fun `opening a conversation loads its history in order`() {
        repository.details = mapOf(
            "s1" to SessionDetail(
                "s1", "Torque of the 2A", "2026-11-06T18:00:00Z", "2026-11-06T18:01:00Z",
                listOf(message(1, "user", "Torque of the 2A?"), message(2, "assistant", "Which voltage?")),
            )
        )
        val state = ChatViewModel(repository, "s1").state.value
        assertEquals("Torque of the 2A", state.title)
        assertEquals(listOf("user", "assistant"), state.messages.map { it.role })
        assertNull(state.error)
    }

    @Test fun `a conversation that no longer exists says so`() {
        val state = ChatViewModel(repository, "missing").state.value
        assertEquals(AppError.NotFound, state.error)
    }
}
