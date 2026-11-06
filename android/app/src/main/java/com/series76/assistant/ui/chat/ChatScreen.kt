package com.series76.assistant.ui.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.series76.assistant.R
import com.series76.assistant.data.AppError
import com.series76.assistant.data.Message
import com.series76.assistant.ui.common.EmptyView
import com.series76.assistant.ui.common.ErrorView
import com.series76.assistant.ui.common.LoadingView

@Composable
fun ChatScreen(viewModel: ChatViewModel, onBack: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    ChatContent(state, onBack = onBack, onRetry = viewModel::loadHistory)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatContent(state: ChatUiState, onBack: () -> Unit, onRetry: () -> Unit) {
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
        Box(Modifier.padding(padding).fillMaxSize()) {
            when {
                state.loading && state.messages.isEmpty() -> LoadingView()
                // A deleted conversation cannot be retried: the way out is the back arrow.
                state.error != null && state.messages.isEmpty() ->
                    ErrorView(state.error, onRetry.takeIf { state.error != AppError.NotFound })
                state.messages.isEmpty() -> EmptyView(stringResource(R.string.chat_title_new), stringResource(R.string.chat_coming_soon))
                else -> MessageList(state.messages)
            }
        }
    }
}

@Composable
private fun MessageList(messages: List<Message>) {
    LazyColumn(
        contentPadding = PaddingValues(12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        modifier = Modifier.fillMaxSize(),
    ) {
        items(messages, key = { it.id }) { MessageBubble(it) }
    }
}

@Composable
private fun MessageBubble(message: Message) {
    val colors = MaterialTheme.colorScheme
    Box(Modifier.fillMaxWidth(), contentAlignment = if (message.isUser) Alignment.CenterEnd else Alignment.CenterStart) {
        Surface(
            color = if (message.isUser) colors.primaryContainer else colors.surfaceVariant,
            shape = MaterialTheme.shapes.large,
            modifier = Modifier.widthIn(max = 320.dp),
        ) {
            Column(Modifier.padding(12.dp)) {
                Text(message.content, style = MaterialTheme.typography.bodyLarge)
            }
        }
    }
}
