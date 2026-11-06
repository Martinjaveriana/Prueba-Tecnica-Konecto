package com.series76.assistant.ui.common

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.series76.assistant.R
import java.net.URI

// Android 17 blocks apps from private addresses such as 10.0.2.2 or 192.168.x.x unless the user allows it.
// Without the permission, connections do not fail: they hang until the timeout.
private const val ACCESS_LOCAL_NETWORK = "android.permission.ACCESS_LOCAL_NETWORK"
private const val ANDROID_17 = 37

/** Loopback (adb reverse, localhost) is not the local network, so it needs no permission. */
fun needsLocalNetworkPermission(backendUrl: String, sdk: Int = Build.VERSION.SDK_INT): Boolean {
    if (sdk < ANDROID_17) return false
    val host = runCatching { URI(backendUrl).host }.getOrNull() ?: return true
    return host != "localhost" && host != "127.0.0.1" && host != "::1"
}

private fun Context.hasLocalNetwork() =
    ContextCompat.checkSelfPermission(this, ACCESS_LOCAL_NETWORK) == PackageManager.PERMISSION_GRANTED

/** Shows the app once the backend can be reached; before that, asks for the permission and says why. */
@Composable
fun LocalNetworkGate(backendUrl: String, content: @Composable () -> Unit) {
    val context = LocalContext.current
    if (!needsLocalNetworkPermission(backendUrl)) return content()

    var granted by remember { mutableStateOf(context.hasLocalNetwork()) }
    var denied by remember { mutableStateOf(false) }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        granted = ok
        denied = !ok
    }
    LaunchedEffect(Unit) { if (!granted) launcher.launch(ACCESS_LOCAL_NETWORK) }

    if (granted) return content()
    Surface(Modifier.fillMaxSize()) {
        Column(
            Modifier.fillMaxSize().padding(32.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(stringResource(R.string.local_network_title), style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
            Text(
                stringResource(if (denied) R.string.local_network_denied else R.string.local_network_why),
                style = MaterialTheme.typography.bodyLarge,
                textAlign = TextAlign.Center,
            )
            Button(onClick = { launcher.launch(ACCESS_LOCAL_NETWORK) }) { Text(stringResource(R.string.local_network_allow)) }
            if (denied) {
                // After a second "Don't allow", Android stops showing the dialog: only Settings can grant it.
                OutlinedButton(onClick = {
                    context.startActivity(
                        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", context.packageName, null))
                    )
                }) { Text(stringResource(R.string.local_network_settings)) }
            }
        }
    }
}
