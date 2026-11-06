package com.series76.assistant.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

private val Light = lightColorScheme(primary = Color(0xFF1F4E79), secondary = Color(0xFF4F6B85))
private val Dark = darkColorScheme(primary = Color(0xFF9CCBFF), secondary = Color(0xFFB6C9DE))

@Composable
fun Series76Theme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    val colors = when {
        // Android 12+ takes its colors from the wallpaper, like the rest of the phone.
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            if (dark) dynamicDarkColorScheme(LocalContext.current) else dynamicLightColorScheme(LocalContext.current)
        dark -> Dark
        else -> Light
    }
    MaterialTheme(colorScheme = colors, content = content)
}
