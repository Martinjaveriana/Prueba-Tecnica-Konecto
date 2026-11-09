package com.series76.assistant.ui

import com.series76.assistant.data.SessionDetail
import com.series76.assistant.ui.debug.DebugInfo
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DebugInfoTest {
    private val json = Json { ignoreUnknownKeys = true }

    private fun debugOf(text: String) = json.decodeFromString<JsonObject>(text)

    @Test fun `reads a real answer's debug, saved before markdown_table existed`() {
        val session = json.decodeFromString<SessionDetail>(javaClass.getResource("/session_with_options.json")!!.readText())
        val info = DebugInfo.from(session.messages[1].debug!!)
        assertEquals("anthropic/claude-haiku-5.5", info.model)
        assertEquals(5304L, info.latencyMs)
        assertEquals("stop", info.finishReason)
        assertEquals(emptyList<String>(), info.unverifiedNumbers)
        assertEquals(emptyList<String>(), info.flags)
        val call = info.toolCalls.single()
        assertEquals("get_actuator_specs", call.name)
        assertEquals(listOf("identifier" to "1A"), call.args)
        assertEquals("ambiguous", call.status)
        assertTrue(call.output.contains("761A00-11300000/A"))
    }

    @Test fun `a call the tool rejected shows the reason`() {
        val info = DebugInfo.from(debugOf("""{"tool_calls":[{"name":"recommend_actuators","args":{"min_torque":500},
            "output":"Invalid arguments: torque_unit is required with min_torque"}]}"""))
        val call = info.toolCalls.single()
        assertEquals("rejected", call.status)
        assertEquals("Invalid arguments: torque_unit is required with min_torque", call.rejection)
        assertEquals(listOf("min_torque" to "500"), call.args)
    }

    @Test fun `warnings and unverified numbers are listed`() {
        val info = DebugInfo.from(debugOf("""{"marker_removed":true,"markdown_table":false,"empty_answer":false,
            "unverified_numbers":["2780"],"unverified_part_numbers":["767C00-11320000/C"],"part_numbers_consulted":["762A00-11300000/A"],"tool_calls":[]}"""))
        assertEquals(listOf("Internal marker removed"), info.flags)
        assertEquals(listOf("2780"), info.unverifiedNumbers)
        assertEquals(listOf("767C00-11320000/C"), info.unverifiedPartNumbers)
        assertEquals(listOf("762A00-11300000/A"), info.partNumbersConsulted)
    }

    @Test fun `a debug with nothing in it does not fail`() {
        val info = DebugInfo.from(debugOf("{}"))
        assertEquals(null, info.model)
        assertEquals(emptyList<Any>(), info.toolCalls)
    }
}
