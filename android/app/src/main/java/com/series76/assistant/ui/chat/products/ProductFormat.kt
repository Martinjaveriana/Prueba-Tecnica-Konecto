package com.series76.assistant.ui.chat.products

import com.series76.assistant.data.Difference
import com.series76.assistant.data.Product
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive

// Plain functions, without Compose, so every label and value can be tested on the JVM.
// Values are shown exactly as the backend sends them: the app never rounds or converts a number.

const val DASH = "—"

fun serviceName(service: String): String = when (service) {
    "on_off" -> "On/Off"
    "modulating" -> "Modulating"
    "unspecified" -> "Not specified"
    else -> service
}

fun enclosureName(enclosure: String): String = when (enclosure) {
    "weatherproof" -> "Weatherproof"
    "explosionproof" -> "Explosionproof"
    else -> enclosure
}

fun supply(p: Product): String =
    "${p.voltageV} V · ${if (p.phases == 1) "1 phase" else "${p.phases} phases"} · ${p.currentType}"

fun frequencyName(hz: Int?): String = hz?.let { "$it Hz" } ?: "Any frequency"

fun withUnit(value: Number?, unit: String): String = value?.let { "$it $unit" } ?: DASH

private val TORQUE_UNITS = mapOf("nm" to "Nm", "in_lbs" to "in-lbs", "ft_lbs" to "ft-lb", "kgf_m" to "kgf·m")

private data class Requirement(val label: String, val unit: String = "", val bound: String = "")

private val REQUIREMENTS = mapOf(
    "voltage_v" to Requirement("Voltage", " V"),
    "phases" to Requirement("Phases"),
    "current_type" to Requirement("Current"),
    "enclosure" to Requirement("Enclosure"),
    "service" to Requirement("Service"),
    "certification" to Requirement("Certification"),
    "size" to Requirement("Size"),
    "max_motor_power_w" to Requirement("Motor power", " W", "at most "),
    "min_duty_cycle_pct" to Requirement("Duty cycle", " %", "at least "),
    "min_cycles_per_hour" to Requirement("Cycles per hour", "", "at least "),
    "min_starts_per_hour" to Requirement("Starts per hour", "", "at least "),
    "max_speed_sec" to Requirement("Speed", " s", "at most "),
    "max_fla_a" to Requirement("FLA", " A", "at most "),
    "max_lra_a" to Requirement("LRA", " A", "at most "),
)

/** "Torque: asked at least 500 Nm, has 450 Nm". The user's own number loses a trailing ".0"; table values are kept. */
fun differenceText(d: Difference): String {
    val names: (String) -> String = when (d.requirement) {
        "service" -> ::serviceName
        "enclosure" -> ::enclosureName
        else -> { s -> s }
    }
    val asked = jsonText(d.requested, names)?.removeSuffix(".0") ?: DASH
    val has = jsonText(d.actual, names)
    if (d.requirement == "min_torque" || d.requirement == "max_torque") {
        val bound = when {
            d.requirement == "max_torque" -> "at most"
            d.exclusive == true -> "more than"
            else -> "at least"
        }
        val askedUnit = TORQUE_UNITS[d.requestedUnit] ?: d.requestedUnit.orEmpty()
        val tableUnit = TORQUE_UNITS[d.tableUnit] ?: d.tableUnit.orEmpty()
        return "Torque: asked $bound $asked $askedUnit, has ${has ?: DASH} $tableUnit".trim()
    }
    if (d.requirement == "exclude_certification") return "Certification: asked without $asked, has ${has ?: DASH}"
    val r = REQUIREMENTS[d.requirement] ?: Requirement(d.requirement)
    val actual = has?.let { "has $it${r.unit}" } ?: "not in the table"
    return "${r.label}: asked ${r.bound}$asked${r.unit}, $actual"
}

private fun jsonText(e: JsonElement?, names: (String) -> String): String? = when (e) {
    null, JsonNull -> null
    is JsonPrimitive -> names(e.content)
    is JsonArray -> e.mapNotNull { jsonText(it, names) }.joinToString(", ")
    else -> e.toString()
}

fun productSummary(p: Product): String =
    listOf(p.alias, supply(p), enclosureName(p.enclosure)).joinToString(" · ")
