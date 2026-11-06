package com.series76.assistant.ui.conversations

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.series76.assistant.data.AppError
import com.series76.assistant.data.AppException
import com.series76.assistant.data.ConversationRepository
import com.series76.assistant.data.SessionSummary
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * sessions is null until the first load succeeds. A later failure keeps the list on screen and adds the
 * error above it, so a backend that goes down does not hide what the user already saw.
 */
data class ConversationsUiState(
    val sessions: List<SessionSummary>? = null,
    val loading: Boolean = false,
    val error: AppError? = null,
)

class ConversationsViewModel(private val repository: ConversationRepository) : ViewModel() {

    private val _state = MutableStateFlow(ConversationsUiState())
    val state: StateFlow<ConversationsUiState> = _state.asStateFlow()

    private var job: Job? = null

    /** Called each time the screen appears, so a conversation created in the chat shows up on return. */
    fun load() {
        if (job?.isActive == true) return
        _state.update { it.copy(loading = true, error = null) }
        job = viewModelScope.launch {
            try {
                val sessions = repository.sessions()
                _state.update { it.copy(sessions = sessions, loading = false) }
            } catch (e: AppException) {
                _state.update { it.copy(loading = false, error = e.error) }
            }
        }
    }
}
