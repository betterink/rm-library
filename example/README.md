# Ink Example (Dev)

A small AppLoad application to check that the existing launcher can load QML,
start a Kotlin/Native executable, exchange messages, and return to native usage.
The setup task records Paper Pro `aarch64`, software `3.29.0.153`, and Codex Linux
`6.0.106 (wrynose)`. These are the target environment, not a claim that this example
has already been tested on-device.

## Build prerequisites

On the Mac, install a JDK 21 and Qt 6 resource compiler, plus Python 3. For Homebrew:

```sh
brew install openjdk@21 qt
```

Java is needed on the build computer only. The tablet receives a native Linux
ARM64 binary with no JVM requirement. `tools/gradle.sh` detects Homebrew's Apple
Silicon JDK location; elsewhere set `JAVA_HOME` yourself. `RCC` may be set to the
full path of Qt's `rcc` executable.

From the repository root:

```sh
python3 tools/example.py doctor
python3 tools/example.py build
```

The Gradle launcher downloads Gradle **8.14.3** into `.tools/` and verifies its
published SHA-256. The build pins Kotlin **2.4.21**; Gradle/Kotlin's first run needs
internet to download the plugin, native compiler and cross-compilation toolchain.
There is no Gradle installation or manually assembled wrapper JAR required.

### IntelliJ IDEA

Open this `example` directory as a Gradle project, enable Kotlin support and select
JDK 21 as the Gradle JVM. Run `../tools/gradle.sh --version` once in the IDE terminal,
then select the repository's `.tools/gradle-8.14.3` as the local Gradle distribution
if IntelliJ requests one. The project uses a pinned launcher rather than a wrapper.
Use IntelliJ for Kotlin and Gradle; QML can be edited here or in Qt Creator.
Use the IDE terminal for the Python build/deploy commands. A macOS IDE cannot
directly run this Linux executable; use the Linux protocol test or physical tablet.

If QML inspections cannot import `QtQuick` and show a `/Users/runner/work/...`
path, configure the QML plugin to use the local language server
`/opt/homebrew/opt/qtdeclarative/bin/qmlls` and import directory
`/opt/homebrew/opt/qt/share/qt/qml`. Restart the language server or reopen the IDE
after changing its configuration. A local `.qmlls.ini` at the workspace root and/or
this Gradle project root can supply the import directory:

```ini
[General]
importPaths=/opt/homebrew/opt/qt/share/qt/qml
no-cmake-calls=true
```

These machine-specific files are ignored by Git. AppLoad's `net.asivery.AppLoad`
module is supplied by the tablet host and is not part of Homebrew Qt, so its IDE
type resolution requires AppLoad tooling separately; a QtQuick path fix does not
make this host module runnable on the Mac.

Output:

```text
dist/ink-example-dev.tar.gz
dist/ink-example-dev.tar.gz.sha256
dist/ink-example-dev/
  manifest.json
  icon.png
  resources.rcc
  backend/entry
```

Packaging rejects a backend unless it is a little-endian AArch64 ELF64 binary.
Qt resources use format version 2 without compression. The native executable can
still depend on the tablet's dynamic loader and system libraries: `--self-test`
on the physical tablet is the compatibility gate, not successful cross-compilation.

The build enables `--as-needed` to drop unused libraries from Kotlin's POSIX
bindings, including `libcrypt.so.1` which is absent on the target tablet.
Packaging prints ELF dependencies and rejects older backends still requiring
`libcrypt.so.1`. Rebuild existing bundles after linker changes; deploy does not
rebuild them automatically.

## Deploy and launch

1. Connect the tablet over USB and confirm `ssh rm` works.
2. If an older example is running, use **Stop backend and close** first. Close
   any leftover view before replacing resources.
3. Run:

   ```sh
   python3 tools/example.py deploy
   python3 tools/example.py verify
   ```

Deployment streams the archive over SSH, stages it outside the AppLoad directory,
runs the backend's `--self-test` on the tablet, then installs it at
`/home/root/xovi/exthome/appload/ink-example-dev`. Previous versions are retained
under `/home/root/.ink-example-backups/`. Existing app directories are preserved
until staging and the executable check succeed. This is development tooling, not
the future general-purpose package manager.

4. Open AppLoad, refresh its application list if available, and select
   **Ink Example (Dev)**. If the list does not update, save any work and explicitly
   restart the native interface:

   ```sh
   ssh rm 'systemctl restart xochitl'
   ```

   If XOVI has not been started since boot, use `ssh rm /home/root/xovi/start`
   instead. Neither command is run automatically by deployment.

5. Inspect host and forwarded backend output:

   ```sh
   python3 tools/example.py logs
   ```

No root filesystem remount, service-file edits, Wi-Fi SSH enablement, or automatic
XOVI boot changes are needed. Choose a different SSH alias with `--host ALIAS`.

## What to verify on the tablet

- [ ] `verify` prints `Kotlin/Native executable OK`, a PID and `pointerBytes=8`.
- [ ] AppLoad displays the icon and opens the QML frontend.
- [ ] The screen displays a Kotlin backend PID and a successful response.
- [ ] Ping returns the UTF-8 text; increment and reset update the counter.
- [ ] Close the view and reopen: the same backend PID and counter remain.
- [ ] Stop the backend: AppLoad closes the view; reopening starts a new PID and counter.
- [ ] Repeat launch/close, fullscreen dismissal, and long-press windowed launch.
- [ ] Suspend/wake with the app open and check focus and responsiveness.
- [ ] Return to native usage and confirm normal notebook interactions still work.

The counter is deliberately process-local. Reattachment persistence is distinct
from saving data to disk. All screen changes are request-driven; there is no
continuous animation or background polling after the initial connection.

## Interaction performance investigation

The example now clamps scroll bounds (no overshoot/bounce), aligns scrolling to
pixels, bounds flick inertia, avoids full-button gray press/disabled fills, and
reserves space for changing backend status. It retains continuous scrolling.
These reduce avoidable redraws; they do not select or guarantee a fast display
refresh waveform.

Use the black square's local drag test and the local tap counter before testing
backend actions. Those local interactions send no Kotlin/socket messages. Backend
round-trip time measures request-to-QML-response only, not input-to-visible-pixel
latency. No drawing/pen-latency claim is made by this diagnostic.

On the same device and firmware, compare:

1. Native reMarkable scrolling and handwriting as the baseline.
2. This example fullscreen: slow drag, fast flick, repeated edge scrolling,
   local square dragging, local taps, and backend taps.
3. Windowed mode as a separate measurement (scaling/compositing can differ).
4. If local interactions remain poor, a standalone Qt Quick application using
   the official epaper platform/scenegraph path, outside AppLoad, as an A/B test.

Record visible response with high-frame-rate video, flicker/ghosting, and whether
latency grows during sustained input. Log backend round trips separately. A good
round-trip value does not demonstrate good screen latency. Do not increase refresh
frequency or change display waveforms blindly to mask queued rendering work.

Continuous handwriting needs a separate pen-aware prototype: local stylus input,
incremental stroke rendering, appropriate display updates and palm handling. Keep
per-point rendering off the Kotlin socket round-trip path. QML can remain the UI
shell and Kotlin the application backend; a C++ Qt/native rendering component may
be needed for the live canvas. Compare its performance on real Paper Pro hardware
before committing to an AppLoad-hosted canvas or claiming native-equivalent input.
If AppLoad cannot meet the measured requirement, retain it as a launcher and
evaluate an independent renderer with a tested return-to-stock lifecycle.

See [Qt Flickable bounds](https://doc.qt.io/qt-6/qml-qtquick-flickable.html) and the
[official Qt Quick epaper example](https://developer.remarkable.com/documentation/qt_epaper).

## Lifecycle choice

`unloading()` stops frontend timers but leaves the backend running. This matches
AppLoad's background-backend model and makes reattachment observable. **Stop backend
and close** sends an application message; the backend exits, allowing AppLoad's
disconnect handler to close the frontend. We do not also call `endpoint.terminate()`
from `unloading()`, because concurrent shutdown has an upstream race report. This
does not establish that AppLoad itself is crash-free; record failures and logs.

## Protocol and automated checks

This example uses `AF_UNIX` / `SOCK_SEQPACKET`. Each message is an 8-byte header
(signed 32-bit type, 32-bit UTF-8 byte length, little-endian on these targets),
followed by a **separate** payload record. Application messages:

| Request | Response | Behaviour |
| --- | --- | --- |
| 1 | 101 + 102 | Backend description and current counter |
| 2 | 102 | Increment counter |
| 3 | 102 | Reset counter |
| 9 | 103, then EOF | Stop backend |
| -2 (AppLoad) | 101 + 102 | Frontend attached; send current state |
| -1 (AppLoad) | EOF | Host requested shutdown |

The implementation retries initial socket connection, validates record sizes,
handles UTF-8 byte lengths and interrupted syscalls, and avoids SIGPIPE on send.
`sendMessage` is the actual QML method; the upstream README currently contains a
`sendMesssage` typo.

On **Linux x86_64**, test the compiled backend against a mock AppLoad host:

```sh
tools/gradle.sh linkReleaseExecutableLinuxX64
python3 tools/test_backend.py example/build/bin/linuxX64/releaseExecutable/entry.kexe
```

The test covers actual native execution, framing, Unicode, empty payloads, counter
state, reattachment, explicit stop, host termination and EOF. macOS cannot run the
Linux binary or provide this Linux Unix-socket transport. The included GitHub
Actions workflow performs that test, cross-compiles ARM64, records ELF dependencies
and uploads the tablet bundle. It must run before claiming a verified native build.
This workflow does not push a release or deploy to a tablet.

## Recovery and troubleshooting

- Missing executable despite a present file usually needs an ELF interpreter /
  dependency check; inspect the journal and the CI `readelf` output.
- `GLIBC_* not found` or a missing shared library means toolchain/device ABI
  compatibility is unresolved; do not copy arbitrary libc files onto the tablet.
- No backend response: inspect `journalctl -u xochitl`, confirm `backend/entry` is
  executable, and run the standalone `--self-test`.
- Stale frontend after deployment: stop the app and explicitly restart Xochitl.
- To restore stock operation: `ssh rm /home/root/xovi/stock`, or reboot normally.
- Remove this example only after stopping it; its directory is the single
  `ink-example-dev` directory under AppLoad's application root.

## Sources

- [AppLoad application structure and lifecycle](https://github.com/asivery/rm-appload/blob/master/README.MD)
- [AppLoad socket host implementation](https://github.com/asivery/rm-appload/blob/master/src/management.cpp)
- [AppLoad QML API](https://github.com/asivery/rm-appload/blob/master/src/AppLoad.cpp)
- [AppLoad application resource loading](https://github.com/asivery/rm-appload/blob/master/src/library.cpp)
- [Reported shutdown race](https://github.com/asivery/rm-appload/issues/82)
- [Kotlin and Gradle compatibility](https://kotlinlang.org/docs/gradle-configure-project.html)

The scaffold uses the upstream interface; it does not vendor upstream code or
submit changes to the upstream project.
