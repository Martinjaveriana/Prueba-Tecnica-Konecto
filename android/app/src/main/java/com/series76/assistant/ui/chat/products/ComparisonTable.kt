package com.series76.assistant.ui.chat.products

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.series76.assistant.R
import com.series76.assistant.data.Focus
import com.series76.assistant.data.Product

private val LABEL_WIDTH = 104.dp
private val COLUMN_WIDTH = 132.dp
private val ROW_HEIGHT = 28.dp
private val HEADER_HEIGHT = 56.dp

/**
 * One column per model, compared under the same service and frequency. The labels stay in place while
 * the models scroll sideways, so a row can be read across.
 */
@Composable
fun ComparisonTable(products: List<Product>, focus: Focus, modifier: Modifier = Modifier) {
    val initial = initialSelection(products, focus)
    var service by rememberSaveable(products) { mutableStateOf(initial.service) }
    var frequency by rememberSaveable(products) { mutableStateOf(initial.frequencyHz) }
    val selection = TableSelection(service, frequency)
    val rows = comparisonRows(products, selection)

    OutlinedCard(modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), itemVerticalAlignment = Alignment.CenterVertically) {
                for (s in servicesIn(products)) {
                    FilterChip(selected = s == service, onClick = { service = s }, label = { Text(serviceName(s)) })
                }
                for (hz in frequenciesIn(products)) {
                    FilterChip(selected = hz == frequency, onClick = { frequency = hz }, label = { Text("$hz Hz") })
                }
            }
            Row {
                Column(Modifier.width(LABEL_WIDTH)) {
                    Cell("", HEADER_HEIGHT)
                    rows.forEach { Cell(it.label, ROW_HEIGHT, bold = true) }
                }
                Row(Modifier.horizontalScroll(rememberScrollState())) {
                    products.forEachIndexed { column, product ->
                        Column(Modifier.width(COLUMN_WIDTH)) {
                            Cell("${product.partNumber}\n${product.alias}", HEADER_HEIGHT, bold = true, lines = 2)
                            rows.forEach { Cell(it.cells[column], ROW_HEIGHT) }
                        }
                    }
                }
            }
            HorizontalDivider()
            val marks = marksIn(rows)
            if (MARK_UNSPECIFIED in marks) Footnote(stringResource(R.string.table_note_unspecified, serviceName(service)))
            if (MARK_ANY_FREQUENCY in marks) Footnote(stringResource(R.string.table_note_any_frequency))
            // Differences and notes belong to one model, so they go below the table, by part number.
            products.forEach { product ->
                product.differences.forEach { Footnote("${product.partNumber}: ${differenceText(it)}", error = true) }
            }
            products.flatMap { p -> p.notes.map { it to p.alias } }
                .groupBy({ it.first }, { it.second })
                .forEach { (note, aliases) -> Footnote("⚠ ${aliases.distinct().joinToString(", ")}: $note") }
        }
    }
}

@Composable
private fun Cell(text: String, height: androidx.compose.ui.unit.Dp, bold: Boolean = false, lines: Int = 1) {
    Text(
        text,
        modifier = Modifier.height(height).padding(end = 8.dp),
        style = MaterialTheme.typography.bodySmall,
        fontWeight = if (bold) FontWeight.SemiBold else null,
        maxLines = lines,
        overflow = TextOverflow.Ellipsis,
    )
}

@Composable
private fun Footnote(text: String, error: Boolean = false) {
    Text(
        text,
        style = MaterialTheme.typography.bodySmall,
        color = if (error) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
    )
}
