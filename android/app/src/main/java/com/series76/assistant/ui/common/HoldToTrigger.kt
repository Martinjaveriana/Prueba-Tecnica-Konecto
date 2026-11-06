package com.series76.assistant.ui.common

import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.pointerInput

/**
 * Calls onHold after the finger stays down for holdMillis. A shorter tap still reaches the element's own
 * onClick; a completed hold swallows the release, so it does not also count as a tap.
 * It listens before the element does (Initial pass) without consuming the press.
 */
fun Modifier.holdToTrigger(holdMillis: Long, onHold: () -> Unit): Modifier = pointerInput(holdMillis) {
    awaitEachGesture {
        awaitFirstDown(requireUnconsumed = false, pass = PointerEventPass.Initial)
        val released = withTimeoutOrNull(holdMillis) { waitForUpOrCancellation(PointerEventPass.Initial) }
        if (released == null) {
            onHold()
            do {
                val event = awaitPointerEvent(PointerEventPass.Initial)
                event.changes.forEach { it.consume() }
            } while (event.changes.any { it.pressed })
        }
    }
}
