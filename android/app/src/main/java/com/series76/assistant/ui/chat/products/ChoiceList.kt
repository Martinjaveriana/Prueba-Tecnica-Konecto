package com.series76.assistant.ui.chat.products

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
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

/** Several models a partial part number names, or similar ones. Tapping one asks about it. */
@Composable
fun ChoiceList(products: List<Product>, onChoose: (String) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(stringResource(R.string.choose_hint), style = MaterialTheme.typography.bodySmall)
        products.forEach { product ->
            OutlinedCard(onClick = { onChoose(product.partNumber) }, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    Text(product.partNumber, fontWeight = FontWeight.SemiBold)
                    Text(productSummary(product), style = MaterialTheme.typography.bodySmall)
                    if (!product.hasData) Text(stringResource(R.string.no_values), style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}
