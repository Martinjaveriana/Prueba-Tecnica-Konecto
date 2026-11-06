package com.series76.assistant.ui

import com.series76.assistant.ui.common.needsLocalNetworkPermission
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LocalNetworkTest {
    @Test fun `the emulator address needs the permission on Android 17`() =
        assertTrue(needsLocalNetworkPermission("http://10.0.2.2:8000/", sdk = 37))

    @Test fun `a computer on the local network needs it too`() =
        assertTrue(needsLocalNetworkPermission("http://192.168.1.50:8000/", sdk = 37))

    @Test fun `adb reverse to localhost does not`() =
        assertFalse(needsLocalNetworkPermission("http://localhost:8000/", sdk = 37))

    @Test fun `older Android versions never ask`() =
        assertFalse(needsLocalNetworkPermission("http://10.0.2.2:8000/", sdk = 36))
}
