package com.series76.assistant.ui.debug

import android.content.ClipData
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.ClipEntry
import androidx.compose.ui.platform.LocalClipboard
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.series76.assistant.R
import com.series76.assistant.data.AppError
import com.series76.assistant.ui.common.EmptyView
import com.series76.assistant.ui.common.ErrorView
import com.series76.assistant.ui.common.LoadingView
import kotlinx.coroutines.launch

@Composable
fun DebugScreen(viewModel: DebugViewModel, messageId: Long, onBack: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    DebugContent(state, messageId, onBack, onRetry = viewModel::load)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DebugContent(state: DebugUiState, messageId: Long, onBack: () -> Unit, onRetry: () -> Unit) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.debug_title, messageId)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(painterResource(R.drawable.ic_back), contentDescription = stringResource(R.string.back))
                    }
                },
            )
        },
    ) { padding ->
        val modifier = Modifier.padding(padding).fillMaxSize()
        when (state) {
            DebugUiState.Loading -> LoadingView(modifier)
            is DebugUiState.Failed -> ErrorView(state.error, onRetry.takeIf { state.error != AppError.NotFound }, modifier)
            DebugUiState.NoDebug -> EmptyView(stringResource(R.string.debug_none), stringResource(R.string.debug_none_hint), modifier)
            is DebugUiState.Loaded -> DebugDetails(state.info, modifier)
        }
    }
}

@Composable
private fun DebugDetails(info: DebugInfo, modifier: Modifier) {
    LazyColumn(modifier, contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Summary(info) }
        itemsIndexed(info.toolCalls) { index, call -> ToolCallCard(index + 1, call) }
        if (info.toolCalls.isEmpty()) item { Text(stringResource(R.string.debug_no_tools), style = MaterialTheme.typography.bodyMedium) }
        item { Expandable(stringResource(R.string.debug_full_json), info.raw) }
    }
}

@Composable
private fun Summary(info: DebugInfo) {
    OutlinedCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(info.model ?: "—", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            val stats = listOfNotNull(
                info.latencyMs?.let { "%.1f s".format(it / 1000.0) },
                if (info.inputTokens != null && info.outputTokens != null) "${info.inputTokens} → ${info.outputTokens} tokens" else null,
                info.finishReason?.let { "finish_reason: $it" },
            )
            Text(stats.joinToString(" · "), style = MaterialTheme.typography.bodySmall)
            if (info.unverifiedNumbers.isEmpty()) {
                Text(stringResource(R.string.debug_numbers_ok), style = MaterialTheme.typography.bodyMedium)
            } else {
                Text(
                    stringResource(R.string.debug_numbers_unverified, info.unverifiedNumbers.joinToString(", ")),
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            if (info.partNumbersConsulted.isNotEmpty()) {
                Text(stringResource(R.string.debug_consulted, info.partNumbersConsulted.joinToString(", ")), style = MaterialTheme.typography.bodySmall)
            }
            info.flags.forEach { Text("⚠ $it", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        }
    }
}

@Composable
private fun ToolCallCard(number: Int, call: ToolCallInfo) {
    OutlinedCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("$number. ${call.name}", Modifier.weight(1f), fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold)
                call.status?.let {
                    Text(it, color = if (it == "rejected") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
                }
            }
            if (call.args.isEmpty()) Text(stringResource(R.string.debug_no_args), style = MaterialTheme.typography.bodySmall)
            call.args.forEach { (key, value) ->
                Text("$key: $value", fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall)
            }
            call.rejection?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            Expandable(stringResource(R.string.debug_output), call.output)
        }
    }
}

/** Long JSON stays folded until asked for, and can be copied whole. */
@Composable
private fun Expandable(title: String, json: String) {
    var open by rememberSaveable(json) { mutableStateOf(false) }
    val clipboard = LocalClipboard.current
    val scope = rememberCoroutineScope()
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                (if (open) "▾ " else "▸ ") + title,
                Modifier.weight(1f).clickable { open = !open }.padding(vertical = 8.dp),
                style = MaterialTheme.typography.labelLarge,
            )
            TextButton(onClick = {
                scope.launch { clipboard.setClipEntry(ClipEntry(ClipData.newPlainText(title, json))) }
            }) { Text(stringResource(R.string.debug_copy)) }
        }
        if (open) {
            Text(
                json,
                Modifier.horizontalScroll(rememberScrollState()),
                fontFamily = FontFamily.Monospace,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}
