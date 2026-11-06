package com.series76.assistant

import android.app.Application
import com.series76.assistant.data.DebugSettings

class Series76App : Application() {
    lateinit var container: AppContainer
        private set

    lateinit var debugSettings: DebugSettings
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer()
        debugSettings = DebugSettings(this)
    }
}
