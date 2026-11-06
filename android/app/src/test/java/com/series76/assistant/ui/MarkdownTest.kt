package com.series76.assistant.ui

import com.series76.assistant.ui.chat.Span
import com.series76.assistant.ui.chat.parseMarkdown
import org.junit.Assert.assertEquals
import org.junit.Test

class MarkdownTest {
    private fun plain(text: String) = parseMarkdown(text).joinToString("") { it.text }

    @Test fun `bold loses its asterisks and is marked bold`() {
        assertEquals(
            listOf(Span("The ", false), Span("762A00-11300000/A", true), Span(" gives 150 Nm.", false)),
            parseMarkdown("The **762A00-11300000/A** gives 150 Nm."),
        )
    }

    @Test fun `dash bullets become dots`() {
        assertEquals("Options:\n• 110 V\n• 220 V", plain("Options:\n- 110 V\n- 220 V"))
    }

    @Test fun `numbered lists and plain text stay as written`() {
        assertEquals("1. First\n2. Second", plain("1. First\n2. Second"))
    }

    @Test fun `a heading loses its hashes and is bold`() {
        assertEquals(listOf(Span("Closest options", true)), parseMarkdown("### Closest options"))
    }

    @Test fun `a lone asterisk is not bold`() {
        assertEquals("Sizes 6 and 7* are not CSA certified", plain("Sizes 6 and 7* are not CSA certified"))
    }
}
