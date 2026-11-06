package com.series76.assistant.ui.chat

import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle

/**
 * The agent writes a little Markdown: **bold**, "- " bullets and "### " headings. The app shows only
 * that, with a few lines of code, instead of a Markdown library. Anything else is shown as written.
 */
data class Span(val text: String, val bold: Boolean)

private val BOLD = Regex("""\*\*(.+?)\*\*""")
private val BULLET = Regex("""^(\s*)[-*]\s+""")
private val HEADING = Regex("""^#{1,6}\s+""")

fun parseMarkdown(text: String): List<Span> {
    val spans = mutableListOf<Span>()
    text.lines().forEachIndexed { index, raw ->
        if (index > 0) spans += Span("\n", false)
        var line = raw
        val heading = HEADING.containsMatchIn(line)
        line = line.replace(HEADING, "").replace(BULLET) { "${it.groupValues[1]}• " }
        var last = 0
        for (match in BOLD.findAll(line)) {
            if (match.range.first > last) spans += Span(line.substring(last, match.range.first), heading)
            spans += Span(match.groupValues[1], true)
            last = match.range.last + 1
        }
        if (last < line.length) spans += Span(line.substring(last), heading)
    }
    return spans.filter { it.text.isNotEmpty() }
}

fun markdownToAnnotated(text: String): AnnotatedString = buildAnnotatedString {
    for (span in parseMarkdown(text)) {
        if (span.bold) withStyle(SpanStyle(fontWeight = FontWeight.SemiBold)) { append(span.text) } else append(span.text)
    }
}
