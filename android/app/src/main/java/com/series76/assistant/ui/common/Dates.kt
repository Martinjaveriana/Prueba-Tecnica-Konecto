package com.series76.assistant.ui.common

import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle

private val FORMAT = DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM, FormatStyle.SHORT)

/** "Nov 6, 2026, 1:45 PM" in the phone's time zone and language. The backend sends ISO 8601. */
fun formatDate(iso: String, zone: ZoneId = ZoneId.systemDefault()): String =
    runCatching { OffsetDateTime.parse(iso).atZoneSameInstant(zone).format(FORMAT) }.getOrDefault(iso)
