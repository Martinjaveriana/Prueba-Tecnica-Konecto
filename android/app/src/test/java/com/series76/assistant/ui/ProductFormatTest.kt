package com.series76.assistant.ui

import com.series76.assistant.data.Difference
import com.series76.assistant.data.ElectricalRating
import com.series76.assistant.data.Focus
import com.series76.assistant.data.ServiceRating
import com.series76.assistant.product
import com.series76.assistant.ui.chat.products.DASH
import com.series76.assistant.ui.chat.products.MARK_ANY_FREQUENCY
import com.series76.assistant.ui.chat.products.MARK_UNSPECIFIED
import com.series76.assistant.ui.chat.products.TableSelection
import com.series76.assistant.ui.chat.products.comparisonRows
import com.series76.assistant.ui.chat.products.differenceText
import com.series76.assistant.ui.chat.products.groupsOf
import com.series76.assistant.ui.chat.products.initialSelection
import com.series76.assistant.ui.chat.products.marksIn
import com.series76.assistant.ui.chat.products.supply
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Test

class ProductFormatTest {
    private val threePhase = product(
        partNumber = "763B00-11330C00/A",
        services = listOf(ServiceRating("unspecified", 4430, 500, 25, 10, null)),
    )
    private val dc24 = product(partNumber = "761E00-11400000/A", electrical = listOf(ElectricalRating(null, 30, 1.5, 3.0)))

    private fun row(label: String, products: List<com.series76.assistant.data.Product>, selection: TableSelection) =
        comparisonRows(products, selection).single { it.label == label }.cells

    @Test fun `values are shown as the tables give them, with their unit`() {
        val cells = row("FLA", listOf(product()), TableSelection("on_off", 60))
        assertEquals(listOf("2.3 A"), cells)
        assertEquals(listOf("150 Nm"), row("Torque", listOf(product()), TableSelection("on_off", 60)))
    }

    @Test fun `the table follows the service and frequency selected`() {
        val selection = TableSelection("modulating", 50)
        assertEquals(listOf("120 Nm"), row("Torque", listOf(product()), selection))
        assertEquals(listOf("21 s"), row("Speed (90°)", listOf(product()), selection))
        assertEquals(listOf("1200 /h"), row("Starts per hour", listOf(product()), selection))
    }

    @Test fun `a 3-phase rating is shown under either service, marked`() {
        val rows = comparisonRows(listOf(product(), threePhase), TableSelection("modulating", 60))
        assertEquals(listOf("120 Nm", "500 Nm $MARK_UNSPECIFIED"), rows.single { it.label == "Torque" }.cells)
        assertEquals(setOf(MARK_UNSPECIFIED), marksIn(rows))
    }

    @Test fun `a 24 V rating is shown at any frequency, marked`() {
        assertEquals(listOf("30 s $MARK_ANY_FREQUENCY"), row("Speed (90°)", listOf(dc24), TableSelection("on_off", 50)))
    }

    @Test fun `a missing value is a dash, never a zero`() {
        val noCycles = product(services = listOf(ServiceRating("on_off", 1330, 150, 30, null, null)))
        assertEquals(listOf(DASH), row("Cycles per hour", listOf(noCycles), TableSelection("on_off", 60)))
        val noData = product(hasData = false, services = emptyList(), electrical = emptyList())
        assertEquals(listOf(DASH), row("Torque", listOf(noData), TableSelection("on_off", 60)))
    }

    @Test fun `the table opens on what the user asked for`() {
        assertEquals(TableSelection("modulating", 50), initialSelection(listOf(product()), Focus("modulating", 50)))
    }

    @Test fun `without a focus it opens On-Off at 60 Hz`() {
        assertEquals(TableSelection("on_off", 60), initialSelection(listOf(product()), Focus()))
    }

    @Test fun `a focus the models do not have is ignored`() {
        val modulatingOnly = product(services = listOf(ServiceRating("modulating", 1, 1, 1, null, 1)), electrical = listOf(ElectricalRating(null, 1, 1.0, 1.0)))
        assertEquals(TableSelection("modulating", null), initialSelection(listOf(modulatingOnly), Focus("on_off", 60)))
    }

    @Test fun `products are grouped by role in the order they came`() {
        val groups = groupsOf(listOf(product(role = "specs"), product("B", role = "alternative"), product("C", role = "alternative")))
        assertEquals(listOf("specs" to 1, "alternative" to 2), groups.map { it.role to it.products.size })
    }

    @Test fun `supply reads naturally`() {
        assertEquals("110 V · 1 phase · AC", supply(product()))
    }

    @Test fun `a torque difference names both units`() {
        val d = Difference("min_torque", JsonPrimitive(500.0), JsonPrimitive(450), requestedUnit = "nm", tableUnit = "nm")
        assertEquals("Torque: asked at least 500 Nm, has 450 Nm", differenceText(d))
        val ft = Difference("min_torque", JsonPrimitive(6000.0), JsonPrimitive(70000), requestedUnit = "ft_lbs", tableUnit = "in_lbs")
        assertEquals("Torque: asked at least 6000 ft-lb, has 70000 in-lbs", differenceText(ft))
    }

    @Test fun `the new torque limits read in plain words`() {
        assertEquals(
            "Torque: asked more than 500 Nm, has 500 Nm",
            differenceText(Difference("min_torque", JsonPrimitive(500.0), JsonPrimitive(500), requestedUnit = "nm", tableUnit = "nm", exclusive = true)),
        )
        assertEquals(
            "Torque: asked at most 200 Nm, has 300 Nm",
            differenceText(Difference("max_torque", JsonPrimitive(200.0), JsonPrimitive(300), requestedUnit = "nm", tableUnit = "nm")),
        )
    }

    @Test fun `a certification to avoid and a size read in plain words`() {
        assertEquals(
            "Certification: asked without CSA, has CSA, CE",
            differenceText(Difference("exclude_certification", JsonPrimitive("CSA"), JsonArray(listOf(JsonPrimitive("CSA"), JsonPrimitive("CE"))))),
        )
        assertEquals("Size: asked 5, has 4", differenceText(Difference("size", JsonPrimitive(5), JsonPrimitive(4))))
    }

    @Test fun `other differences read in plain words`() {
        assertEquals("Voltage: asked 24 V, has 110 V", differenceText(Difference("voltage_v", JsonPrimitive(24), JsonPrimitive(110))))
        assertEquals(
            "Service: asked Modulating, has On/Off",
            differenceText(Difference("service", JsonPrimitive("modulating"), JsonArray(listOf(JsonPrimitive("on_off"))))),
        )
        assertEquals("Speed: asked at most 10 s, has 18 s", differenceText(Difference("max_speed_sec", JsonPrimitive(10.0), JsonPrimitive(18))))
    }
}
