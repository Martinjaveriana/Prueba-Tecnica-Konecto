package com.series76.assistant.ui.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.series76.assistant.data.AppError
import com.series76.assistant.data.AppException
import com.series76.assistant.data.ConversationRepository
import com.series76.assistant.data.Focus
import com.series76.assistant.data.Message
import com.series76.assistant.data.Product
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject

/** One bubble. A question shows before the backend saves it, so it has a local key until then. */
data class ChatMessage(
    val key: String,
    /** The backend's id, once saved. The debug screen looks the message up by it. */
    val id: Long? = null,
    val isUser: Boolean,
    val text: String,
    val products: List<Product> = emptyList(),
    val focus: Focus = Focus(),
    val needsClarification: Boolean = false,
    val debug: JsonObject? = null,
    /** The question could not be sent. It is not part of the conversation until a retry works. */
    val failed: Boolean = false,
)

fun Message.toChat() = ChatMessage("m$id", id, isUser, content, products, focus, needsClarification, debug)

data class ChatUiState(
    val sessionId: String? = null,
    val title: String? = null,
    val messages: List<ChatMessage> = emptyList(),
    /** Loading the history of a saved conversation. */
    val loading: Boolean = false,
    /** The history could not be loaded: nothing can be sent until it is. */
    val error: AppError? = null,
    /** Waiting for an answer. Only one question at a time, so they reach the history in order. */
    val sending: Boolean = false,
    val sendError: AppError? = null,
) {
    val canSend: Boolean get() = !sending && !loading && error == null
}

/** sessionId null means a new conversation: the backend creates it with the first question. */
class ChatViewModel(
    private val repository: ConversationRepository,
    sessionId: String?,
) : ViewModel() {

    private val _state = MutableStateFlow(ChatUiState(sessionId = sessionId))
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    private var localCount = 0

    init {
        if (sessionId != null) loadHistory()
    }

    fun loadHistory() {
        val id = _state.value.sessionId ?: return
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val session = repository.session(id)
                _state.update {
                    it.copy(title = session.title, messages = session.messages.map(Message::toChat), loading = false)
                }
            } catch (e: AppException) {
                _state.update { it.copy(loading = false, error = e.error) }
            }
        }
    }

    /** Returns false when the question was not taken, so the screen keeps the text in the box. */
    fun send(text: String): Boolean {
        val question = text.trim()
        if (question.isEmpty() || !_state.value.canSend) return false
        val message = ChatMessage("local-${++localCount}", isUser = true, text = question)
        // A question that was never sent is dropped when the user asks something else instead.
        _state.update { it.copy(messages = it.messages.filterNot(ChatMessage::failed) + message, sending = true, sendError = null) }
        ask(message)
        return true
    }

    /** Sends the failed question again. The backend saved nothing when it failed, so nothing is duplicated. */
    fun retry() {
        val failed = _state.value.messages.lastOrNull { it.failed } ?: return
        if (!_state.value.canSend) return
        _state.update { state ->
            state.copy(
                messages = state.messages.map { if (it.key == failed.key) it.copy(failed = false) else it },
                sending = true,
                sendError = null,
            )
        }
        ask(failed)
    }

    private fun ask(question: ChatMessage) {
        viewModelScope.launch {
            try {
                val response = repository.ask(_state.value.sessionId, question.text)
                val answer = ChatMessage(
                    key = "m${response.messageId}",
                    id = response.messageId,
                    isUser = false,
                    text = response.answer,
                    products = response.products,
                    focus = response.focus,
                    needsClarification = response.needsClarification,
                    debug = response.debug,
                )
                _state.update {
                    it.copy(
                        sessionId = response.sessionId,
                        title = it.title ?: question.text,
                        messages = it.messages + answer,
                        sending = false,
                    )
                }
            } catch (e: AppException) {
                _state.update { state ->
                    state.copy(
                        sending = false,
                        sendError = e.error,
                        messages = state.messages.map { if (it.key == question.key) it.copy(failed = true) else it },
                    )
                }
            }
        }
    }
}
