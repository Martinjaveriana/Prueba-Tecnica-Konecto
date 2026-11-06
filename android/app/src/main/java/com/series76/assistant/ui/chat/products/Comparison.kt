package com.series76.assistant.ui.chat.products

import com.series76.assistant.data.ElectricalRating
import com.series76.assistant.data.Focus
import com.series76.assistant.data.Product
import com.series76.assistant.data.ServiceRating

/** Products of one role in one answer, in the order the backend sent them. */
data class ProductGroup(val role: String, val products: List<Product>)

fun groupsOf(products: List<Product>): List<ProductGroup> =
    products.groupBy { it.role }.map { (role, list) -> ProductGroup(role, list) }

/** The service and frequency the comparison table shows. frequencyHz null: no model has a 50/60 Hz table. */
data class TableSelection(val service: String, val frequencyHz: Int?)

private const val UNSPECIFIED = "unspecified"

fun servicesIn(products: List<Product>): List<String> = listOf("on_off", "modulating").filter { service ->
    products.any { p -> p.serviceRatings.any { it.service == service || it.service == UNSPECIFIED } }
}

fun frequenciesIn(products: List<Product>): List<Int> = listOf(60, 50).filter { hz ->
    products.any { p -> p.electricalRatings.any { it.frequencyHz == hz } }
}

/** Opens on what the user asked for (focus), else On/Off at 60 Hz, else whatever the models have. */
fun initialSelection(products: List<Product>, focus: Focus): TableSelection {
    val services = servicesIn(products)
    val frequencies = frequenciesIn(products)
    return TableSelection(
        service = focus.service?.takeIf { it in services } ?: services.firstOrNull() ?: "on_off",
        frequencyHz = focus.frequencyHz?.takeIf { it in frequencies } ?: frequencies.firstOrNull(),
    )
}

/** The rating for a service. A 3-phase model has one "unspecified" rating, shown with a mark. */
fun serviceRating(p: Product, service: String): ServiceRating? =
    p.serviceRatings.firstOrNull { it.service == service } ?: p.serviceRatings.firstOrNull { it.service == UNSPECIFIED }

/** The rating for a frequency. 24 V models have one rating for any frequency, shown with a mark. */
fun electricalRating(p: Product, frequencyHz: Int?): ElectricalRating? =
    frequencyHz?.let { hz -> p.electricalRatings.firstOrNull { it.frequencyHz == hz } }
        ?: p.electricalRatings.firstOrNull { it.frequencyHz == null }

const val MARK_UNSPECIFIED = "*"
const val MARK_ANY_FREQUENCY = "†"

data class TableRow(val label: String, val cells: List<String>)

fun comparisonRows(products: List<Product>, selection: TableSelection): List<TableRow> {
    val services = products.map { serviceRating(it, selection.service) }
    val electrical = products.map { electricalRating(it, selection.frequencyHz) }

    fun service(value: (ServiceRating) -> Number?, unit: String) = services.map { r ->
        if (r == null) DASH else withUnit(value(r), unit) + if (r.service == UNSPECIFIED) " $MARK_UNSPECIFIED" else ""
    }

    fun current(value: (ElectricalRating) -> Number, unit: String) = electrical.map { r ->
        if (r == null) DASH else withUnit(value(r), unit) + if (r.frequencyHz == null) " $MARK_ANY_FREQUENCY" else ""
    }

    val rate = if (selection.service == "modulating") {
        TableRow("Starts per hour", service({ it.startsPerHour }, "/h"))
    } else {
        TableRow("Cycles per hour", service({ it.cyclesPerHour }, "/h"))
    }
    return listOf(
        TableRow("Supply", products.map(::supply)),
        TableRow("Enclosure", products.map { enclosureName(it.enclosure) }),
        TableRow("Torque", service({ it.torqueNm }, "Nm")),
        TableRow("Torque (in-lbs)", service({ it.torqueInLbs }, "in-lbs")),
        TableRow("Duty cycle", service({ it.dutyCyclePct }, "%")),
        rate,
        TableRow("Speed (90°)", current({ it.speedSec }, "s")),
        TableRow("FLA", current({ it.flaA }, "A")),
        TableRow("LRA", current({ it.lraA }, "A")),
        TableRow("Motor power", products.map { withUnit(it.motorPowerW, "W") }),
    )
}

/** Which marks appear in the table, so only their footnotes are shown. */
fun marksIn(rows: List<TableRow>): Set<String> =
    setOf(MARK_UNSPECIFIED, MARK_ANY_FREQUENCY).filter { mark -> rows.any { row -> row.cells.any { it.endsWith(" $mark") } } }.toSet()
