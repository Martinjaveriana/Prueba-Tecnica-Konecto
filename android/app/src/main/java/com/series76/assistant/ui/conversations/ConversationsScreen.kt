package com.series76.assistant.ui.conversations

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ListItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.series76.assistant.R
import com.series76.assistant.data.SessionSummary
import com.series76.assistant.ui.common.EmptyView
import com.series76.assistant.ui.common.ErrorBanner
import com.series76.assistant.ui.common.ErrorView
import com.series76.assistant.ui.common.LoadingView
import com.series76.assistant.ui.common.formatDate

@Composable
fun ConversationsScreen(
    viewModel: ConversationsViewModel,
    onOpen: (String) -> Unit,
    onNew: () -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { viewModel.load() }
    ConversationsContent(state, onRetry = viewModel::load, onOpen = onOpen, onNew = onNew)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConversationsContent(
    state: ConversationsUiState,
    onRetry: () -> Unit,
    onOpen: (String) -> Unit,
    onNew: () -> Unit,
) {
    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.conversations_title)) }) },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = onNew,
                icon = { Icon(painterResource(R.drawable.ic_add), contentDescription = null) },
                text = { Text(stringResource(R.string.new_conversation)) },
            )
        },
    ) { padding ->
        val sessions = state.sessions
        Column(Modifier.padding(padding).fillMaxSize()) {
            when {
                sessions == null && state.error != null -> ErrorView(state.error, onRetry)
                sessions == null -> LoadingView()
                else -> {
                    if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
                    state.error?.let { ErrorBanner(it, onRetry) }
                    if (sessions.isEmpty()) {
                        EmptyView(stringResource(R.string.no_conversations), stringResource(R.string.no_conversations_hint))
                    } else {
                        SessionList(sessions, onOpen)
                    }
                }
            }
        }
    }
}

@Composable
private fun SessionList(sessions: List<SessionSummary>, onOpen: (String) -> Unit) {
    // Bottom padding keeps the last row above the floating button.
    LazyColumn(contentPadding = PaddingValues(bottom = 88.dp)) {
        items(sessions, key = { it.id }) { session ->
            ListItem(
                headlineContent = { Text(session.title, maxLines = 2, overflow = TextOverflow.Ellipsis) },
                supportingContent = {
                    Text(
                        formatDate(session.updatedAt) + " · " +
                            stringResource(R.string.message_count, session.messageCount)
                    )
                },
                modifier = Modifier.clickable { onOpen(session.id) },
            )
            HorizontalDivider()
        }
    }
}
