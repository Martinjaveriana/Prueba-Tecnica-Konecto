package com.series76.assistant

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.toRoute
import com.series76.assistant.data.ConversationRepository
import com.series76.assistant.data.DebugSettings
import com.series76.assistant.ui.debug.DebugScreen
import com.series76.assistant.ui.debug.DebugViewModel
import com.series76.assistant.ui.chat.ChatScreen
import com.series76.assistant.ui.chat.ChatViewModel
import com.series76.assistant.ui.conversations.ConversationsScreen
import com.series76.assistant.ui.common.LocalNetworkGate
import com.series76.assistant.ui.conversations.ConversationsViewModel
import com.series76.assistant.ui.theme.Series76Theme
import kotlinx.serialization.Serializable

@Serializable
object ConversationsRoute

/** sessionId null opens a new conversation. */
@Serializable
data class ChatRoute(val sessionId: String? = null)

/** The debug of one saved answer. Reached only with debug mode on. */
@Serializable
data class DebugRoute(val sessionId: String, val messageId: Long)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = application as Series76App
        setContent {
            Series76Theme {
                LocalNetworkGate(BuildConfig.BACKEND_URL) { AppNavigation(app.container.repository, app.debugSettings) }
            }
        }
    }
}

@Composable
private fun AppNavigation(repository: ConversationRepository, debugSettings: DebugSettings) {
    val nav = rememberNavController()
    val debugMode by debugSettings.enabled.collectAsStateWithLifecycle()
    NavHost(navController = nav, startDestination = ConversationsRoute) {
        composable<ConversationsRoute> {
            ConversationsScreen(
                viewModel = viewModel { ConversationsViewModel(repository) },
                debugMode = debugMode,
                onDebugModeChange = debugSettings::setEnabled,
                onOpen = { id -> nav.navigate(ChatRoute(id)) },
                onNew = { nav.navigate(ChatRoute()) },
            )
        }
        composable<ChatRoute> { entry ->
            val route = entry.toRoute<ChatRoute>()
            ChatScreen(
                viewModel = viewModel { ChatViewModel(repository, route.sessionId) },
                debugMode = debugMode,
                onOpenDebug = { sessionId, messageId -> nav.navigate(DebugRoute(sessionId, messageId)) },
                onBack = { nav.popBackStack() },
            )
        }
        composable<DebugRoute> { entry ->
            val route = entry.toRoute<DebugRoute>()
            DebugScreen(
                viewModel = viewModel { DebugViewModel(repository, route.sessionId, route.messageId) },
                messageId = route.messageId,
                onBack = { nav.popBackStack() },
            )
        }
    }
}
