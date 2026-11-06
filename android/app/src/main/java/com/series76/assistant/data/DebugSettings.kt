package com.series76.assistant.data

import android.content.Context
import androidx.core.content.edit
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Debug mode: only when it is on does a long press on an answer open its debug screen. It is turned on by
 * holding "New conversation" for 3 seconds and confirming, and it is kept on this phone until turned off.
 */
class DebugSettings(context: Context) {
    private val prefs = context.getSharedPreferences("developer", Context.MODE_PRIVATE)
    private val _enabled = MutableStateFlow(prefs.getBoolean(KEY, false))
    val enabled: StateFlow<Boolean> = _enabled.asStateFlow()

    fun setEnabled(on: Boolean) {
        prefs.edit { putBoolean(KEY, on) }
        _enabled.value = on
    }

    private companion object {
        const val KEY = "debug_mode"
    }
}
