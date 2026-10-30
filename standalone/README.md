# Standalone interaction benchmark

The current firmware-specific display-policy experiment is documented in
[DISPLAY.md](DISPLAY.md). It adds checked mode selection and idle ghost cleanup;
its physical display behaviour still requires device validation.

An independent Qt Quick application for comparing the Paper Pro's epaper path
against the existing AppLoad example. It uses no AppLoad extensions, framebuffer
shim or Kotlin IPC. It does not establish that standalone rendering is faster.

- **Scroll:** 200 reusable list delegates, continuous scrolling, clamped bounds.
- **Drag:** a locally positioned rectangle with no animation or IPC.
- **Pen / canvas:** native C++ raster surface, pressure-dependent width, incremental
  line updates and dirty-region repaint requests. Qt tablet events are counted;
  enable finger/mouse fallback explicitly for desktop testing.
- **Exit:** closes the process. The tablet's temporary service then starts Xochitl.

This is a benchmark, not a production handwriting engine. It does not implement
raw evdev pen input, specialised low-latency ink APIs, erasing, full palm rejection,
stroke storage, or custom refresh waveforms. If the platform supplies no Qt tablet
events, the event count stays at zero: finger fallback does not prove marker input.
The C++ surface uses QQuickPaintedItem with a persistent raster image so previously
drawn lines are not regenerated per sample. Requested dirty regions do not prove
that the device backend physically updates only those pixels; measure on hardware.

## Preview on this Mac

The installed Homebrew Qt and Xcode command-line compiler are sufficient. The
helper invokes Qt's moc/rcc and clang directly; CMake is not needed for this preview.

```sh
cd ~/repos/ink/rm-library
python3 tools/standalone.py preview
```

Native raster test and headless QML startup check:

```sh
python3 tools/standalone.py test
python3 tools/standalone.py preview --smoke-test
python3 tools/test_standalone_runner.py
```

These have been run locally. They verify compilation, QML loading, stroke pixels,
untouched background and clearing, not e-ink performance or real stylus delivery.
The runner tests use mock system commands to check preflight refusal and service
properties; they do not prove recovery on the actual tablet.
The desktop executable is Mach-O and is deliberately rejected by tablet packaging.

## Build for Paper Pro

With Docker Desktop running and the tablet connected over USB, the combined setup
command builds and installs the benchmark without opening it:

```sh
python3 tools/standalone.py doctor
python3 tools/standalone.py setup
```

This uses the SDK candidate recorded in `standalone/sdk.json`, selecting the build
host architecture automatically. The current candidate is the newest listed
official ferrari SDK, **3.28.0.172**. Using it on the recorded **3.29.0.153** target
is a compatibility experiment. Setup prints this mismatch, records the SDK URL in
the bundle metadata, and probes the executable on-device before activating it.
It does not bypass failures or replace device system libraries. Override the
candidate with `--sdk-url` when a more suitable official SDK becomes available.

After installing, save tablet work and start the session explicitly:

```sh
python3 tools/standalone.py run
```

`setup --launch` combines installation and launch when that is explicitly wanted.
Docker socket access may be unavailable inside an agent sandbox even when it works
in a normal terminal. Do not change Docker socket permissions to work around that.

Use an official **ferrari** SDK in Linux. Homebrew's Mac Qt libraries cannot be
copied to the tablet. The configured tablet target is software **3.29.0.153** /
Codex Linux **6.0.106**, but the official SDK list checked during setup currently
ends at **3.28.0.172**. There is no verified matching SDK in this repository.
Check [official downloads](https://developer.remarkable.com/links) before choosing
an SDK. An earlier SDK is a compatibility experiment, not a supported match.

Two build paths are provided:

1. **Linux computer/VM:** install the appropriate SDK using its installer, then:

   ```sh
   bash tools/build-standalone.sh /absolute/path/to/SDK/environment-setup-...
   ```

   The machine needs Python 3, CMake and Make. The SDK supplies target Qt, its
   cross-compiler and the CMake toolchain configuration.

2. **Docker on the Mac:** install and start Docker Desktop, then use the official
   ferrari SDK installer URL for the build host architecture:

   ```sh
   python3 tools/standalone.py build-tablet --sdk-url 'OFFICIAL_FERRARI_SDK_URL'
   ```

   On Apple Silicon, use the **aarch64-host** installer; on an Intel Mac, use the
   **x86_64-host** installer. The container uses the corresponding Linux platform.
   `--sdk-url` overrides the recorded candidate. The official links page now offers aarch64-host SDKs, although the older
   SDK guide still describes x86_64-only hosts. The first build downloads the SDK
   and creates a local build image. No privileged container or USB access is used.

Output: `dist/ink-standalone-benchmark.tar.gz`. Deployment runs `--probe` before
activating the new binary; this checks loading the executable's Qt/system library
dependencies without taking over the screen. It does not fully validate Qt plugin
or input compatibility. Application/platform startup still needs a device test.

## Deploy, run and recover

```sh
python3 tools/standalone.py inspect
python3 tools/standalone.py deploy
# Save open tablet work before running the next command.
python3 tools/standalone.py run
python3 tools/standalone.py logs
```

The application is installed separately at `/home/root/ink-benchmark/current`.
Nothing is added to AppLoad's application directory or the root filesystem.
Previous installations are retained in `/home/root/ink-benchmark/previous.*`.

The runner checks the binary and epaper plugin files, requires Xochitl to be
running, then creates a **transient** `ink-benchmark.service`. Its pre-start command
stops Xochitl; its post-stop command starts it. Process exit, failure and stopping
the service all use this cleanup path. The process is independent of the SSH
connection, and a ten-minute runtime limit bounds a hung session. These properties
are configured, but their actual behaviour has not been verified on this tablet.
No installed systemd service files or XOVI boot configuration are edited.

Stop from the computer:

```sh
python3 tools/standalone.py stop
```

Recovery from a second terminal if needed:

```sh
ssh rm 'systemctl stop ink-benchmark.service; systemctl start xochitl'
```

That returns to the native interface using the tablet's existing Xochitl service
configuration. It does not uninstall XOVI or promise an unmodified stock setup.

## Access without AppLoad

Currently the Mac starts the standalone bundle over SSH through the runner, and
all benchmark interaction then happens on the tablet. Its Exit button returns to
the native interface. There is no new Apps icon in the stock interface yet, and
opening an archive on the tablet does not launch an executable bundle.

An eventual tablet-only workflow needs a separately implemented entry point:
for example, a small XOVI Apps control that invokes the same supervisor, followed
by an on-device app picker. That entry point can launch independent processes;
it need not host or render their interfaces. This is future launcher work, not
part of the interaction benchmark. No undocumented native home-screen integration
has been installed by these scripts.

## Device acceptance checks

### Follow-up from the first device run

The initial device test reported a quarter-screen portrait window, no pen events,
drag trails and scrolling that blanked until release. These are failed acceptance
checks, not a successful standalone-performance result.

The window now explicitly uses the display geometry instead of relying on the
embedded platform honouring a fullscreen state request. A Rotate control provides
manual orientation; automatic sensor rotation is not implemented. Startup logs
record screen/window geometry, device pixel ratio and registered input devices.

Collect read-only diagnostics before changing rendering/refresh policy:

```sh
python3 tools/standalone.py diagnose
```

The report is saved to `build/standalone-device-diagnostics.txt` and includes the
input device inventory, installed epaper/tablet plugins and benchmark journal.
After rebuilding/deploying the updated bundle, test the standard Qt pen plugin:

```sh
python3 tools/standalone.py run --pen-input evdevtablet
```

The runner checks that this plugin exists before stopping Xochitl. It enables
Qt's generic evdevtablet handler, and the application permits mouse synthesis for
unhandled tablet events so pen interaction outside the native canvas can be
tested. Whether device discovery, coordinates and actual marker delivery work
must be verified on hardware. A missing plugin is reported rather than silently
treated as working stylus support; no system Qt libraries are replaced.

Sizing and pen-input changes do not claim to fix ghosting or scrolling. Those
remain display/scenegraph integration issues to investigate using device evidence.
Do not select arbitrary refresh waveforms to compensate for the observed trails.
See [Qt pen-input setup](https://doc.qt.io/qt-6/inputs-linux-device.html#pen-based-tablets)
and the [public epaper integration](https://github.com/reMarkable/epaper-qpa/blob/new_devices/epaperintegration.cpp).

### Follow-up: smooth pen strokes, broken navigation and display clearing

The next device report confirmed smooth marker drawing, but pen taps did not
activate the ordinary controls. Photos showed persistent square copies, coloured
trails and missing/scarred list content. Those remain failed rendering checks.
The saved diagnostic inventory identifies Elan marker input on event2, Elan touch
input on event3 and an installed evdevtablet plugin; device numbers should still
be discovered rather than hardcoded.

Pen contacts outside the canvas now have an explicit mouse press/move/release
route into Qt Quick. Contacts beginning inside the canvas remain tablet events,
preserving pressure and avoiding duplicate strokes. A native synthetic-event test
checks both routing paths, including drags crossing the canvas boundary. Real
button/list behaviour still needs a device check.

To inspect the installed display-control interface without invoking private APIs:

```sh
python3 tools/standalone.py diagnose --display-library
```

This also copies the installed `libqsgepaper.so` to ignored local `build/` storage,
records its SHA-256 and appends relevant exported symbols and configuration strings
to the text report. It never loads this AArch64 library on the Mac, replaces device
libraries or changes refresh settings. This evidence is needed to identify the
current firmware's region-update, content-mode and cleanup-refresh interfaces.
Smooth additive drawing does not establish correct erasure of moving UI content.
Do not treat a repeated Qt repaint as a verified physical cleanup refresh.

- Binary probe succeeds; log records the Qt platform and backend.
- Exit restores the native interface.
- Stopping the transient service restores the native interface.
- A process failure and the ten-minute timeout each restore the native interface.
- Disconnecting SSH does not prevent later cleanup.
- Scrolling and dragging are compared with native reMarkable and fullscreen
  AppLoad on the same device/firmware and similar content.
- Pen event count increases with the actual marker, and strokes appear.
- Record input-to-visible latency using video, plus flicker, ghosting and any
  latency growth during sustained use. Desktop frame rate is not the result.

The standalone list and AppLoad diagnostic are not pixel-identical workloads;
this is an initial isolation test, not a controlled performance claim. Match
scenes and collect measurements before attributing a difference solely to AppLoad.
If pen events remain zero or latency is unacceptable, investigate the device's
input/display integration before building the wider launcher platform.

Sources: [official Qt Quick epaper workflow](https://developer.remarkable.com/documentation/qt_epaper),
[SDK guide](https://developer.remarkable.com/documentation/sdk),
[SDK downloads](https://developer.remarkable.com/links),
[Qt painted item behaviour](https://doc.qt.io/qt-6/qquickpainteditem.html).
