package com.series76.assistant.ui.chat.products

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.series76.assistant.R
import com.series76.assistant.data.Focus
import com.series76.assistant.data.Product

/**
 * The models of one answer, drawn from products (database values), never from the answer text.
 * One model gets a card; several matches or alternatives get a table; options and suggestions are a list to tap.
 */
@Composable
fun ProductsView(products: List<Product>, focus: Focus, onChoose: (String) -> Unit, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        val groups = groupsOf(products)
        // "alternative" means two things: the closest models when nothing qualifies, or models with data
        // to look at instead of one listed as N/A.
        val besideNoData = groups.any { it.role == "no_data" }
        for (group in groups) {
            groupTitle(group.role, besideNoData)?.let { Text(it, style = MaterialTheme.typography.titleSmall) }
            when (group.role) {
                "option", "suggestion" -> ChoiceList(group.products, onChoose)
                "match", "alternative" ->
                    if (group.products.size == 1) ProductCard(group.products.single())
                    else ComparisonTable(group.products, focus)
                else -> group.products.forEach { ProductCard(it) }
            }
        }
    }
}

@Composable
private fun groupTitle(role: String, besideNoData: Boolean): String? = when (role) {
    "match" -> stringResource(R.string.group_match)
    "alternative" -> stringResource(if (besideNoData) R.string.group_alternative_to_no_data else R.string.group_alternative)
    "option" -> stringResource(R.string.group_option)
    "suggestion" -> stringResource(R.string.group_suggestion)
    else -> null
}
