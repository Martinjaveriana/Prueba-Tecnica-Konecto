package com.series76.assistant.ui

import com.series76.assistant.ui.common.formatDate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneId

class DatesTest {
    @Test fun `a date from the backend is shown in the phone's time zone`() {
        val shown = formatDate("2026-11-06T18:45:00.123456Z", ZoneId.of("America/Bogota"))
        assertTrue(shown, shown.contains("1:45"))
    }

    @Test fun `a date that cannot be read is shown as it came`() {
        assertEquals("yesterday", formatDate("yesterday"))
    }
}
