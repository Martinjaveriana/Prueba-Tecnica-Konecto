package com.series76.assistant.ui.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.series76.assistant.data.AppError
import com.series76.assistant.data.AppException
import com.series76.assistant.data.ConversationRepository
import com.series76.assistant.data.Message
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ChatUiState(
    val sessionId: String? = null,
    val title: String? = null,
    val messages: List<Message> = emptyList(),
    val loading: Boolean = false,
    val error: AppError? = null,
)

/** sessionId null means a new conversation: nothing to load until the first question. */
class ChatViewModel(
    private val repository: ConversationRepository,
    sessionId: String?,
) : ViewModel() {

    private val _state = MutableStateFlow(ChatUiState(sessionId = sessionId))
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    init {
        if (sessionId != null) loadHistory()
    }

    fun loadHistory() {
        val id = _state.value.sessionId ?: return
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val session = repository.session(id)
                _state.update { it.copy(title = session.title, messages = session.messages, loading = false) }
            } catch (e: AppException) {
                _state.update { it.copy(loading = false, error = e.error) }
            }
        }
    }
}
