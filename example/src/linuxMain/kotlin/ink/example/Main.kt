@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package ink.example

import kotlinx.cinterop.*
import platform.posix.*

private const val MAX_PAYLOAD = 65536
private data class Message(val type: Int, val text: String)

// AppLoad sends an 8-byte native-endian header and a separate payload record.
// Both supported Linux targets are little-endian. Never combine the records.
private fun ByteArray.putInt(offset: Int, value: Int) {
    repeat(4) { this[offset + it] = (value ushr (it * 8)).toByte() }
}
private fun ByteArray.intAt(offset: Int): Int =
    (0..3).fold(0) { value, index ->
        value or ((this[offset + index].toInt() and 255) shl (index * 8))
    }

private class Connection(private val fd: Int) {
    private fun receiveRecord(size: Int): ByteArray? {
        val bytes = ByteArray(maxOf(size, 1))
        val count = bytes.usePinned { pinned ->
            var result: Long
            do {
                result = recv(fd, pinned.addressOf(0), bytes.size.convert(), MSG_TRUNC).toLong()
            } while (result < 0 && errno == EINTR)
            result
        }
        if (count == 0L && size != 0) return null
        check(count >= 0) { "recv failed: errno=$errno" }
        check(count == size.toLong()) { "Invalid record: expected $size bytes, received $count" }
        return bytes.copyOf(size)
    }

    fun receive(): Message? {
        val header = receiveRecord(8) ?: return null
        val length = header.intAt(4)
        check(length in 0..MAX_PAYLOAD) { "Invalid payload length: $length" }
        // Qt sends the payload as a separate record, including empty strings.
        val payload = receiveRecord(length) ?: error("Disconnected during payload")
        return Message(header.intAt(0), payload.decodeToString(throwOnInvalidSequence = true))
    }

    private fun sendRecord(bytes: ByteArray) {
        require(bytes.isNotEmpty())
        val count = bytes.usePinned { pinned ->
            var result: Long
            do {
                result = send(fd, pinned.addressOf(0), bytes.size.convert(), MSG_NOSIGNAL).toLong()
            } while (result < 0 && errno == EINTR)
            result
        }
        check(count == bytes.size.toLong()) { "send failed: errno=$errno" }
    }

    fun send(type: Int, text: String) {
        val payload = text.encodeToByteArray()
        require(payload.size in 1..MAX_PAYLOAD)
        val header = ByteArray(8)
        header.putInt(0, type)
        header.putInt(4, payload.size)
        sendRecord(header)
        sendRecord(payload)
    }
}

private fun connectTo(path: String): Int = memScoped {
    val bytes = path.encodeToByteArray()
    require(bytes.isNotEmpty() && bytes.size < 108 && 0.toByte() !in bytes) { "Invalid Unix socket path" }
    // AppLoad creates its listener asynchronously; tolerate that startup race.
    repeat(50) {
        val fd = socket(AF_UNIX, SOCK_SEQPACKET, 0)
        check(fd >= 0) { "socket failed: errno=$errno" }
        val address = alloc<sockaddr_un>()
        memset(address.ptr, 0, sizeOf<sockaddr_un>().convert())
        address.sun_family = AF_UNIX.convert()
        bytes.forEachIndexed { index, byte -> address.sun_path[index] = byte }
        if (connect(fd, address.ptr.reinterpret(), sizeOf<sockaddr_un>().convert()) == 0) return@memScoped fd
        val failure = errno
        close(fd)
        check(failure == ENOENT || failure == ECONNREFUSED || failure == EINTR) {
            "connect failed: errno=$failure"
        }
        usleep(100000u)
    }
    error("AppLoad socket was not ready after 5 seconds")
}

fun main(args: Array<String>) {
    if (args.contentEquals(arrayOf("--self-test"))) {
        val probe = ByteArray(8)
        probe.putInt(0, -1)
        probe.putInt(4, "Kotlin ✓".encodeToByteArray().size)
        check(probe.intAt(0) == -1 && probe.intAt(4) == 10)
        println("Ink Example: Kotlin/Native executable OK; pid=${getpid()}; pointerBytes=${sizeOf<COpaquePointerVar>()}")
        return
    }
    require(args.size == 1) { "Usage: entry SOCKET_PATH | --self-test" }
    val fd = connectTo(args[0])
    val connection = Connection(fd)
    var counter = 0
    println("Ink Example: backend connected; pid=${getpid()}")
    try {
        while (true) {
            val message = connection.receive() ?: break
            when (message.type) {
                -1 -> break // Host-requested shutdown.
                -2, 1 -> {
                    connection.send(101, "Kotlin/Native backend • pid=${getpid()} • ${message.text}")
                    connection.send(102, counter.toString())
                }
                2 -> connection.send(102, (++counter).toString())
                3 -> { counter = 0; connection.send(102, "0") }
                9 -> { connection.send(103, "stopping"); break }
                else -> println("Ink Example: ignored message type=${message.type}")
            }
        }
    } finally {
        close(fd)
        println("Ink Example: backend stopped")
    }
}
