package com.series76.assistant.ui.debug

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.longOrNull

private val PRETTY = Json { prettyPrint = true }

fun pretty(element: JsonElement): String = PRETTY.encodeToString(JsonElement.serializer(), element)

data class ToolCallInfo(
    val name: String,
    val args: List<Pair<String, String>>,
    /** found, ambiguous, no_matches…; "rejected" when the tool refused the arguments; null without output. */
    val status: String?,
    /** The tool's message when it rejected the arguments, such as "Invalid arguments: torque_unit is required". */
    val rejection: String?,
    val output: String,
)

/**
 * The debug of one answer, read into what the screen shows. Every field is optional: messages saved
 * before a field existed simply do not show it.
 */
data class DebugInfo(
    val model: String?,
    val latencyMs: Long?,
    val inputTokens: Long?,
    val outputTokens: Long?,
    val finishReason: String?,
    val unverifiedNumbers: List<String>,
    val partNumbersConsulted: List<String>,
    /** Only the warnings that happened: an empty answer, a removed marker, a Markdown table. */
    val flags: List<String>,
    val toolCalls: List<ToolCallInfo>,
    val raw: String,
) {
    companion object {
        private val FLAGS = listOf(
            "empty_answer" to "Empty answer replaced",
            "marker_removed" to "Internal marker removed",
            "markdown_table" to "Markdown table in the answer",
        )

        fun from(debug: JsonObject): DebugInfo = DebugInfo(
            model = debug.text("model"),
            latencyMs = debug.number("latency_ms"),
            inputTokens = debug.number("input_tokens"),
            outputTokens = debug.number("output_tokens"),
            finishReason = debug.text("finish_reason"),
            unverifiedNumbers = debug.texts("unverified_numbers"),
            partNumbersConsulted = debug.texts("part_numbers_consulted"),
            flags = FLAGS.filter { (key, _) -> (debug[key] as? JsonPrimitive)?.booleanOrNull == true }.map { it.second },
            toolCalls = (debug["tool_calls"] as? JsonArray).orEmpty().mapNotNull { (it as? JsonObject)?.let(::toolCall) },
            raw = pretty(debug),
        )

        private fun toolCall(call: JsonObject): ToolCallInfo {
            val output = call["output"]
            val rejection = (output as? JsonPrimitive)?.contentOrNull
            return ToolCallInfo(
                name = call.text("name") ?: "?",
                args = (call["args"] as? JsonObject).orEmpty().map { (key, value) -> key to valueText(value) },
                status = when {
                    output is JsonObject -> output.text("status")
                    rejection != null -> "rejected"
                    else -> null
                },
                rejection = rejection,
                output = output?.let(::pretty) ?: "null",
            )
        }

        private fun valueText(value: JsonElement): String = when (value) {
            is JsonPrimitive -> value.contentOrNull ?: "null"
            JsonNull -> "null"
            else -> value.toString()
        }

        private fun JsonObject.text(key: String) = (this[key] as? JsonPrimitive)?.takeIf { it !is JsonNull }?.contentOrNull
        private fun JsonObject.number(key: String) = (this[key] as? JsonPrimitive)?.longOrNull
        private fun JsonObject.texts(key: String) =
            (this[key] as? JsonArray).orEmpty().mapNotNull { (it as? JsonPrimitive)?.contentOrNull }
    }
}
