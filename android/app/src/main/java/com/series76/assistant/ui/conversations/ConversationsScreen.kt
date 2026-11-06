package com.series76.assistant.ui.conversations

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.TextButton
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
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
import com.series76.assistant.ui.common.holdToTrigger
import kotlinx.coroutines.launch

/** Holding "New conversation" this long offers debug mode: long enough that nobody gets there by accident. */
const val DEBUG_HOLD_MILLIS = 3_000L

@Composable
fun ConversationsScreen(
    viewModel: ConversationsViewModel,
    debugMode: Boolean,
    onDebugModeChange: (Boolean) -> Unit,
    onOpen: (String) -> Unit,
    onNew: () -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { viewModel.load() }
    ConversationsContent(state, debugMode, onDebugModeChange, onRetry = viewModel::load, onOpen = onOpen, onNew = onNew)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConversationsContent(
    state: ConversationsUiState,
    debugMode: Boolean,
    onDebugModeChange: (Boolean) -> Unit,
    onRetry: () -> Unit,
    onOpen: (String) -> Unit,
    onNew: () -> Unit,
) {
    var askingDebug by remember { mutableStateOf(false) }
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val haptics = LocalHapticFeedback.current
    val enabledMessage = stringResource(R.string.debug_enabled_message)
    val disabledMessage = stringResource(R.string.debug_disabled_message)

    if (askingDebug) {
        DebugModeDialog(
            turningOn = !debugMode,
            onConfirm = {
                askingDebug = false
                onDebugModeChange(!debugMode)
                scope.launch { snackbar.showSnackbar(if (debugMode) disabledMessage else enabledMessage) }
            },
            onDismiss = { askingDebug = false },
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.conversations_title)) },
                actions = {
                    // Only whoever turned debug mode on sees this, so they know it is on.
                    if (debugMode) {
                        Text(
                            stringResource(R.string.debug_mode),
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.labelLarge,
                            modifier = Modifier.padding(end = 16.dp),
                        )
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = onNew,
                modifier = Modifier.holdToTrigger(DEBUG_HOLD_MILLIS) {
                    haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                    askingDebug = true
                },
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
private fun DebugModeDialog(turningOn: Boolean, onConfirm: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(if (turningOn) R.string.debug_enable_title else R.string.debug_disable_title)) },
        text = { Text(stringResource(if (turningOn) R.string.debug_enable_text else R.string.debug_disable_text)) },
        confirmButton = {
            TextButton(onClick = onConfirm) {
                Text(stringResource(if (turningOn) R.string.debug_enable else R.string.debug_disable))
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.cancel)) } },
    )
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
