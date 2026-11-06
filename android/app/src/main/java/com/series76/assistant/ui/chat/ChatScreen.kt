package com.series76.assistant.ui.chat

import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.series76.assistant.R
import com.series76.assistant.data.AppError
import com.series76.assistant.ui.chat.products.ProductsView
import com.series76.assistant.ui.common.ErrorView
import com.series76.assistant.ui.common.LoadingView
import com.series76.assistant.ui.common.messageFor

@Composable
fun ChatScreen(
    viewModel: ChatViewModel,
    debugMode: Boolean,
    onOpenDebug: (sessionId: String, messageId: Long) -> Unit,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    // Only with debug mode on, and only for answers the backend saved.
    val openDebug: ((Long) -> Unit)? = state.sessionId?.takeIf { debugMode }?.let { id -> { messageId -> onOpenDebug(id, messageId) } }
    ChatContent(
        state = state,
        onOpenDebug = openDebug,
        onBack = onBack,
        onRetryHistory = viewModel::loadHistory,
        onSend = viewModel::send,
        onRetrySend = viewModel::retry,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatContent(
    state: ChatUiState,
    onOpenDebug: ((Long) -> Unit)?,
    onBack: () -> Unit,
    onRetryHistory: () -> Unit,
    onSend: (String) -> Boolean,
    onRetrySend: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(state.title ?: stringResource(R.string.chat_title_new), maxLines = 1, overflow = TextOverflow.Ellipsis)
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(painterResource(R.drawable.ic_back), contentDescription = stringResource(R.string.back))
                    }
                },
            )
        },
    ) { padding ->
        Column(Modifier.padding(padding).consumeWindowInsets(padding).imePadding().fillMaxSize()) {
            Box(Modifier.weight(1f)) {
                when {
                    state.loading && state.messages.isEmpty() -> LoadingView()
                    // A deleted conversation cannot be retried: the way out is the back arrow.
                    state.error != null && state.messages.isEmpty() ->
                        ErrorView(state.error, onRetryHistory.takeIf { state.error != AppError.NotFound })
                    state.messages.isEmpty() -> Examples(onSend)
                    else -> MessageList(state, onChoose = { onSend(it) }, onRetrySend = onRetrySend, onOpenDebug = onOpenDebug)
                }
            }
            InputBar(enabled = state.canSend, onSend = onSend)
        }
    }
}

@Composable
private fun MessageList(
    state: ChatUiState,
    onChoose: (String) -> Unit,
    onRetrySend: () -> Unit,
    onOpenDebug: ((Long) -> Unit)?,
) {
    val list = rememberLazyListState()
    // Follow the conversation: the waiting indicator, then the answer's first line, at the top of the screen.
    // Keyed on both, because the answer replaces the indicator and the item count does not change.
    // Without animation: an animated scroll starts before a tall answer is measured and stops short.
    LaunchedEffect(state.messages.size, state.sending) {
        val last = state.messages.size - if (state.sending) 0 else 1
        if (last >= 0) list.scrollToItem(last)
    }
    LazyColumn(
        state = list,
        contentPadding = PaddingValues(12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        modifier = Modifier.fillMaxSize(),
    ) {
        items(state.messages, key = { it.key }) { message ->
            if (message.isUser) {
                UserBubble(message, state.sendError.takeIf { message.failed }, onRetrySend)
            } else {
                AssistantMessage(message, onChoose, onOpenDebug)
            }
        }
        if (state.sending) item(key = "thinking") { Thinking() }
    }
}

@Composable
private fun UserBubble(message: ChatMessage, error: AppError?, onRetry: () -> Unit) {
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.End) {
        Surface(
            color = MaterialTheme.colorScheme.primaryContainer,
            shape = MaterialTheme.shapes.large,
            modifier = Modifier.widthIn(max = 320.dp),
        ) {
            Text(message.text, Modifier.padding(12.dp), style = MaterialTheme.typography.bodyLarge)
        }
        if (message.failed) {
            Text(
                stringResource(R.string.not_sent) + " " + (error?.let { messageFor(it) } ?: ""),
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                textAlign = TextAlign.End,
                modifier = Modifier.widthIn(max = 320.dp),
            )
            TextButton(onClick = onRetry) { Text(stringResource(R.string.retry)) }
        }
    }
}

@Composable
private fun AssistantMessage(message: ChatMessage, onChoose: (String) -> Unit, onOpenDebug: ((Long) -> Unit)?) {
    val haptics = LocalHapticFeedback.current
    val id = message.id
    val debug = if (onOpenDebug != null && id != null) {
        Modifier.combinedClickable(onClick = {}, onLongClick = {
            haptics.performHapticFeedback(HapticFeedbackType.LongPress)
            onOpenDebug(id)
        })
    } else {
        Modifier
    }
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Surface(
            color = MaterialTheme.colorScheme.surfaceVariant,
            shape = MaterialTheme.shapes.large,
            modifier = Modifier.widthIn(max = 340.dp).clip(MaterialTheme.shapes.large).then(debug),
        ) {
            Text(markdownToAnnotated(message.text), Modifier.padding(12.dp), style = MaterialTheme.typography.bodyLarge)
        }
        if (message.products.isNotEmpty()) ProductsView(message.products, message.focus, onChoose)
    }
}

@Composable
private fun Thinking() {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
        Text(stringResource(R.string.thinking), style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun Examples(onSend: (String) -> Boolean) {
    val examples = listOf(
        stringResource(R.string.example_specs),
        stringResource(R.string.example_recommend),
        stringResource(R.string.example_alias),
    )
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(stringResource(R.string.examples_title), style = MaterialTheme.typography.titleMedium, textAlign = TextAlign.Center)
        examples.forEach { example -> SuggestionChip(onClick = { onSend(example) }, label = { Text(example) }) }
    }
}

@Composable
private fun InputBar(enabled: Boolean, onSend: (String) -> Boolean) {
    // Survives rotation, and stays when a question could not be taken.
    var draft by rememberSaveable { mutableStateOf("") }
    val send = { if (onSend(draft)) draft = "" }
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        OutlinedTextField(
            value = draft,
            onValueChange = { draft = it },
            placeholder = { Text(stringResource(R.string.chat_input_hint)) },
            maxLines = 4,
            modifier = Modifier.weight(1f),
        )
        FilledIconButton(onClick = send, enabled = enabled && draft.isNotBlank()) {
            Icon(painterResource(R.drawable.ic_send), contentDescription = stringResource(R.string.send))
        }
    }
}
