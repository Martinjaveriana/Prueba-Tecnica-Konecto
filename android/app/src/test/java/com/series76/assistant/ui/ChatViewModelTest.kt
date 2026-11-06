package com.series76.assistant.ui

import com.series76.assistant.FakeRepository
import com.series76.assistant.MainDispatcherRule
import com.series76.assistant.data.AppError
import com.series76.assistant.data.SessionDetail
import com.series76.assistant.message
import com.series76.assistant.ui.chat.ChatViewModel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class ChatViewModelTest {
    @get:Rule val main = MainDispatcherRule()

    private val repository = FakeRepository()

    private fun saved(id: String) = SessionDetail(
        id, "Torque of the 2A", "2026-11-06T18:00:00Z", "2026-11-06T18:01:00Z",
        listOf(message(1, "user", "Torque of the 2A?"), message(2, "assistant", "Which voltage?")),
    )

    @Test fun `a new conversation loads nothing`() {
        val viewModel = ChatViewModel(repository, sessionId = null)
        assertEquals(0, repository.calls)
        assertEquals(emptyList<Any>(), viewModel.state.value.messages)
    }

    @Test fun `opening a conversation loads its history in order`() {
        repository.details = mapOf("s1" to saved("s1"))
        val state = ChatViewModel(repository, "s1").state.value
        assertEquals("Torque of the 2A", state.title)
        assertEquals(listOf(true, false), state.messages.map { it.isUser })
        assertNull(state.error)
    }

    @Test fun `a conversation that no longer exists says so and cannot be continued`() {
        val state = ChatViewModel(repository, "missing").state.value
        assertEquals(AppError.NotFound, state.error)
        assertFalse(state.canSend)
    }

    @Test fun `the first question creates the conversation and keeps its id`() {
        repository.answer = { _, _ -> com.series76.assistant.response("s-created") }
        val viewModel = ChatViewModel(repository, sessionId = null)
        assertTrue(viewModel.send("  Torque of 762A00-11300000/A?  "))
        val state = viewModel.state.value
        assertEquals("s-created", state.sessionId)
        assertEquals("Torque of 762A00-11300000/A?", state.title)
        assertEquals(listOf("Torque of 762A00-11300000/A?", "On/Off gives 150 Nm."), state.messages.map { it.text })
        assertFalse(state.sending)
    }

    @Test fun `a follow-up goes to the same conversation`() {
        repository.answer = { id, _ -> com.series76.assistant.response(id ?: "s-created") }
        val viewModel = ChatViewModel(repository, sessionId = null)
        viewModel.send("Torque of the 2A at 110 V?")
        viewModel.send("And how much power does it draw?")
        assertEquals(listOf(null, "s-created"), repository.asked.map { it.first })
    }

    @Test fun `a blank question is not sent`() {
        val viewModel = ChatViewModel(repository, sessionId = null)
        assertFalse(viewModel.send("   "))
        assertEquals(0, repository.calls)
    }

    @Test fun `a failed question stays on screen, marked, with the error`() {
        repository.error = AppError.Unreachable
        val viewModel = ChatViewModel(repository, sessionId = null)
        viewModel.send("Torque of 762A00-11300000/A?")
        val state = viewModel.state.value
        assertEquals(1, state.messages.size)
        assertTrue(state.messages.single().failed)
        assertEquals(AppError.Unreachable, state.sendError)
        assertTrue(state.canSend)
    }

    @Test fun `retry sends the same question again without duplicating it`() {
        repository.error = AppError.Unavailable("busy")
        val viewModel = ChatViewModel(repository, sessionId = null)
        viewModel.send("Torque of 762A00-11300000/A?")
        repository.error = null
        viewModel.retry()
        val state = viewModel.state.value
        assertEquals(listOf("Torque of 762A00-11300000/A?", "On/Off gives 150 Nm."), state.messages.map { it.text })
        assertFalse(state.messages.any { it.failed })
        assertNull(state.sendError)
        assertEquals(2, repository.asked.size)
    }

    @Test fun `asking something else drops the question that was never sent`() {
        repository.error = AppError.Unreachable
        val viewModel = ChatViewModel(repository, sessionId = null)
        viewModel.send("First question")
        repository.error = null
        viewModel.send("Second question")
        assertEquals(listOf("Second question", "On/Off gives 150 Nm."), viewModel.state.value.messages.map { it.text })
    }
}
