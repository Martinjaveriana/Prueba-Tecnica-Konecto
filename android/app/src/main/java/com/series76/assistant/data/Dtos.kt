package com.series76.assistant.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

// Mirrors of the backend's response models (see /docs). Field names follow the JSON, in snake_case.

@Serializable
data class ConversationRequest(
    @SerialName("session_id") val sessionId: String? = null,
    val query: String,
)

@Serializable
data class ConversationResponse(
    @SerialName("session_id") val sessionId: String,
    val answer: String,
    val products: List<Product>,
    @SerialName("needs_clarification") val needsClarification: Boolean,
    val focus: Focus = Focus(),
    val debug: JsonObject,
    @SerialName("message_id") val messageId: Long,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class SessionSummary(
    val id: String,
    val title: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("message_count") val messageCount: Int,
)

@Serializable
data class SessionDetail(
    val id: String,
    val title: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    val messages: List<Message>,
)

@Serializable
data class Message(
    val id: Long,
    val role: String,
    val content: String,
    val products: List<Product>,
    @SerialName("needs_clarification") val needsClarification: Boolean,
    val focus: Focus = Focus(),
    // Tools called, their arguments and results. Only the debug screen reads it.
    val debug: JsonObject? = null,
    @SerialName("created_at") val createdAt: String,
) {
    val isUser: Boolean get() = role == "user"
}

@Serializable
data class Product(
    // specs, match, alternative, option, suggestion or no_data
    val role: String,
    @SerialName("part_number") val partNumber: String,
    val alias: String,
    val enclosure: String,
    @SerialName("voltage_v") val voltageV: Int,
    val phases: Int,
    @SerialName("current_type") val currentType: String,
    @SerialName("motor_power_w") val motorPowerW: Int? = null,
    val certifications: List<String> = emptyList(),
    @SerialName("hazardous_classification") val hazardousClassification: List<String> = emptyList(),
    @SerialName("has_data") val hasData: Boolean,
    @SerialName("source_page") val sourcePage: Int,
    @SerialName("service_ratings") val serviceRatings: List<ServiceRating> = emptyList(),
    @SerialName("electrical_ratings") val electricalRatings: List<ElectricalRating> = emptyList(),
    val notes: List<String> = emptyList(),
    val differences: List<Difference> = emptyList(),
)

@Serializable
data class ServiceRating(
    // on_off, modulating or unspecified (the 3-phase table does not say which)
    val service: String,
    @SerialName("torque_in_lbs") val torqueInLbs: Int,
    @SerialName("torque_nm") val torqueNm: Int,
    @SerialName("duty_cycle_pct") val dutyCyclePct: Int,
    @SerialName("cycles_per_hour") val cyclesPerHour: Int? = null,
    @SerialName("starts_per_hour") val startsPerHour: Int? = null,
)

@Serializable
data class ElectricalRating(
    // null for 24 V models, whose tables have a single value
    @SerialName("frequency_hz") val frequencyHz: Int? = null,
    @SerialName("speed_sec") val speedSec: Int,
    @SerialName("fla_a") val flaA: Double,
    @SerialName("lra_a") val lraA: Double,
)

@Serializable
data class Difference(
    val requirement: String,
    val requested: JsonElement? = null,
    val actual: JsonElement? = null,
    @SerialName("requested_unit") val requestedUnit: String? = null,
    @SerialName("table_unit") val tableUnit: String? = null,
)

/** The service and frequency the question was about. null: the user did not say. */
@Serializable
data class Focus(
    val service: String? = null,
    @SerialName("frequency_hz") val frequencyHz: Int? = null,
)

@Serializable
data class ErrorBody(val detail: String? = null)
