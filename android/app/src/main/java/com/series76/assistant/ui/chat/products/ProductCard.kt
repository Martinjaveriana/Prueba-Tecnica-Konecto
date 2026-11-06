package com.series76.assistant.ui.chat.products

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.series76.assistant.R
import com.series76.assistant.data.Product

/** Every value of one model: by service on top, by frequency below, then its notes and source page. */
@Composable
fun ProductCard(product: Product, modifier: Modifier = Modifier) {
    OutlinedCard(modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(product.partNumber, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(productSummary(product), style = MaterialTheme.typography.bodyMedium)
            val details = listOfNotNull(
                product.motorPowerW?.let { "Motor $it W" },
                product.certifications.takeIf { it.isNotEmpty() }?.joinToString(", "),
                product.hazardousClassification.takeIf { it.isNotEmpty() }?.joinToString(", "),
            )
            if (details.isNotEmpty()) Text(details.joinToString(" · "), style = MaterialTheme.typography.bodySmall)

            if (product.serviceRatings.isEmpty() && product.electricalRatings.isEmpty()) {
                Text(stringResource(R.string.no_values), style = MaterialTheme.typography.bodyMedium)
            }
            if (product.serviceRatings.isNotEmpty()) {
                HorizontalDivider()
                val ratings = product.serviceRatings.sortedBy { SERVICE_ORDER.indexOf(it.service) }
                MiniTable(
                    header = ratings.map { serviceName(it.service) },
                    rows = listOf(
                        "Torque" to ratings.map { withUnit(it.torqueNm, "Nm") },
                        "Torque (in-lbs)" to ratings.map { withUnit(it.torqueInLbs, "in-lbs") },
                        "Duty cycle" to ratings.map { withUnit(it.dutyCyclePct, "%") },
                        "Cycles per hour" to ratings.map { withUnit(it.cyclesPerHour, "/h") },
                        "Starts per hour" to ratings.map { withUnit(it.startsPerHour, "/h") },
                    ),
                )
            }
            if (product.electricalRatings.isNotEmpty()) {
                HorizontalDivider()
                val ratings = product.electricalRatings
                MiniTable(
                    header = ratings.map { frequencyName(it.frequencyHz) },
                    rows = listOf(
                        "Speed (90°)" to ratings.map { withUnit(it.speedSec, "s") },
                        "FLA" to ratings.map { withUnit(it.flaA, "A") },
                        "LRA" to ratings.map { withUnit(it.lraA, "A") },
                    ),
                )
            }
            product.differences.forEach {
                Text(differenceText(it), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            product.notes.forEach { Text("⚠ $it", style = MaterialTheme.typography.bodySmall) }
            Text(
                stringResource(R.string.source_page, product.sourcePage),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private val SERVICE_ORDER = listOf("on_off", "modulating", "unspecified")

@Composable
private fun MiniTable(header: List<String>, rows: List<Pair<String, List<String>>>) {
    Row(Modifier.horizontalScroll(rememberScrollState())) {
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("", style = MaterialTheme.typography.labelMedium)
            rows.forEach { (label, _) -> Text(label, Modifier.width(120.dp), style = MaterialTheme.typography.bodySmall) }
        }
        header.forEachIndexed { column, title ->
            Column(Modifier.width(96.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
                rows.forEach { (_, cells) -> Text(cells[column], style = MaterialTheme.typography.bodySmall) }
            }
        }
    }
}
