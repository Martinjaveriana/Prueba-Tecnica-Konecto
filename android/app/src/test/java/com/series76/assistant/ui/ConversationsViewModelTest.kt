package com.series76.assistant.ui

import com.series76.assistant.FakeRepository
import com.series76.assistant.MainDispatcherRule
import com.series76.assistant.data.AppError
import com.series76.assistant.summary
import com.series76.assistant.ui.conversations.ConversationsViewModel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test

class ConversationsViewModelTest {
    @get:Rule val main = MainDispatcherRule()

    private val repository = FakeRepository()
    private val viewModel = ConversationsViewModel(repository)

    @Test fun `loads the saved conversations`() {
        repository.sessions = listOf(summary("a"), summary("b"))
        viewModel.load()
        val state = viewModel.state.value
        assertEquals(listOf("a", "b"), state.sessions?.map { it.id })
        assertFalse(state.loading)
        assertNull(state.error)
    }

    @Test fun `no conversations is an empty list, not an error`() {
        viewModel.load()
        assertEquals(emptyList<Any>(), viewModel.state.value.sessions)
        assertNull(viewModel.state.value.error)
    }

    @Test fun `a backend that is down ends in an error, never loading forever`() {
        repository.error = AppError.Unreachable
        viewModel.load()
        val state = viewModel.state.value
        assertEquals(AppError.Unreachable, state.error)
        assertNull(state.sessions)
        assertFalse(state.loading)
    }

    @Test fun `a failure after a successful load keeps the list on screen`() {
        repository.sessions = listOf(summary("a"))
        viewModel.load()
        repository.error = AppError.Unavailable("The database is not available yet.")
        viewModel.load()
        val state = viewModel.state.value
        assertEquals(listOf("a"), state.sessions?.map { it.id })
        assertEquals(AppError.Unavailable("The database is not available yet."), state.error)
    }

    @Test fun `retry clears the error once the backend is back`() {
        repository.error = AppError.Unreachable
        viewModel.load()
        repository.error = null
        repository.sessions = listOf(summary("a"))
        viewModel.load()
        assertNull(viewModel.state.value.error)
        assertEquals(1, viewModel.state.value.sessions?.size)
    }
}
