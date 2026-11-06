package com.series76.assistant.ui.debug

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.series76.assistant.data.AppError
import com.series76.assistant.data.AppException
import com.series76.assistant.data.ConversationRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface DebugUiState {
    data object Loading : DebugUiState
    data class Loaded(val info: DebugInfo) : DebugUiState
    /** The message is not in the conversation, or it has no debug: a question, or an old answer. */
    data object NoDebug : DebugUiState
    data class Failed(val error: AppError) : DebugUiState
}

/**
 * Reads the answer's debug from the backend, as it was saved, instead of passing it through navigation:
 * it shows what the database holds, and works the same for a resumed conversation.
 */
class DebugViewModel(
    private val repository: ConversationRepository,
    private val sessionId: String,
    private val messageId: Long,
) : ViewModel() {

    private val _state = MutableStateFlow<DebugUiState>(DebugUiState.Loading)
    val state: StateFlow<DebugUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        _state.value = DebugUiState.Loading
        viewModelScope.launch {
            _state.value = try {
                val debug = repository.session(sessionId).messages.firstOrNull { it.id == messageId }?.debug
                if (debug.isNullOrEmpty()) DebugUiState.NoDebug else DebugUiState.Loaded(DebugInfo.from(debug))
            } catch (e: AppException) {
                DebugUiState.Failed(e.error)
            }
        }
    }
}
