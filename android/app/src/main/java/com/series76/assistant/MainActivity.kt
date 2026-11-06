package com.series76.assistant

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.Composable
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.toRoute
import com.series76.assistant.data.ConversationRepository
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

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val repository = (application as Series76App).container.repository
        setContent {
            Series76Theme {
                LocalNetworkGate(BuildConfig.BACKEND_URL) { AppNavigation(repository) }
            }
        }
    }
}

@Composable
private fun AppNavigation(repository: ConversationRepository) {
    val nav = rememberNavController()
    NavHost(navController = nav, startDestination = ConversationsRoute) {
        composable<ConversationsRoute> {
            ConversationsScreen(
                viewModel = viewModel { ConversationsViewModel(repository) },
                onOpen = { id -> nav.navigate(ChatRoute(id)) },
                onNew = { nav.navigate(ChatRoute()) },
            )
        }
        composable<ChatRoute> { entry ->
            val route = entry.toRoute<ChatRoute>()
            ChatScreen(
                viewModel = viewModel { ChatViewModel(repository, route.sessionId) },
                onBack = { nav.popBackStack() },
            )
        }
    }
}
