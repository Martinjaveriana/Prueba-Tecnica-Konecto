package com.series76.assistant.data

/** What went wrong, in terms the screens can explain. HTTP and network details stay in the data layer. */
sealed interface AppError {
    /** No connection, the server is down or the request timed out. */
    data object Unreachable : AppError

    /** 503: the backend is up, but the language model or the database is not. */
    data class Unavailable(val detail: String?) : AppError

    /** 404: the conversation does not exist. */
    data object NotFound : AppError

    /** Any other response, such as a 500. */
    data class Unexpected(val code: Int) : AppError
}

class AppException(val error: AppError, cause: Throwable? = null) : Exception(error.toString(), cause)
