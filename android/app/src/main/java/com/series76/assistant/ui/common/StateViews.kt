package com.series76.assistant.ui.common

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.series76.assistant.R
import com.series76.assistant.data.AppError

@Composable
fun messageFor(error: AppError): String = when (error) {
    AppError.Unreachable -> stringResource(R.string.error_unreachable)
    is AppError.Unavailable -> stringResource(R.string.error_unavailable)
    AppError.NotFound -> stringResource(R.string.error_not_found)
    is AppError.Unexpected -> stringResource(R.string.error_unexpected, error.code)
}

@Composable
fun LoadingView(modifier: Modifier = Modifier) {
    Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator()
    }
}

/** Full-screen error, for when there is nothing else to show. */
@Composable
fun ErrorView(error: AppError, onRetry: (() -> Unit)?, modifier: Modifier = Modifier) {
    Column(
        modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(messageFor(error), textAlign = TextAlign.Center, style = MaterialTheme.typography.bodyLarge)
        if (onRetry != null) Button(onClick = onRetry) { Text(stringResource(R.string.retry)) }
    }
}

/** Error above content that is still useful, such as a list loaded before the backend went down. */
@Composable
fun ErrorBanner(error: AppError, onRetry: () -> Unit, modifier: Modifier = Modifier) {
    Surface(color = MaterialTheme.colorScheme.errorContainer, modifier = modifier.fillMaxWidth()) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
            Text(messageFor(error), color = MaterialTheme.colorScheme.onErrorContainer, style = MaterialTheme.typography.bodyMedium)
            TextButton(onClick = onRetry, modifier = Modifier.align(Alignment.End)) { Text(stringResource(R.string.retry)) }
        }
    }
}

@Composable
fun EmptyView(title: String, hint: String, modifier: Modifier = Modifier) {
    Column(
        modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text(hint, textAlign = TextAlign.Center, style = MaterialTheme.typography.bodyMedium)
    }
}
