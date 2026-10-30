# Display-control experiment for the captured Paper Pro library

The local device report now includes the installed `libqsgepaper.so`, SHA-256
`07aa9327f725288a5df5aebc33ea4b151c27d97d3b850279947ddddf3dd8ddec`.
Recorded firmware: 3.29.0.153. Screen and window geometry both report 1620×2160,
DPR 1. Pen drawing and pen navigation have been reported working on-device.
The first display-control device test was reported to work extremely well for
scrolling and dragging. The same test regressed canvas delay/smoothness relative
to the earlier default-policy canvas. The default-policy canvas was also reported insufficient. The sustained Pen
experiment below needs device validation.

## Verified interface facts

The captured ELF exports `EPFramebuffer::instance()` and its QObject metadata
contains the following slots:

- `pushGlobalScreenMode(EPScreenMode)`
- `popGlobalScreenMode()`
- `clearGhosting()`
- `scheduleGhostRemoval()`

The captured `EPScreenModeItem` Qt metadata provides these named enum values:
Pen=0, Mono=1, Animation=2, UI=3, Content=4, Sleep=5, Overlay=6.
These are vendor screen modes, not guessed panel waveform IDs. The current
[upstream reverse-engineering header](https://github.com/asivery/epfb-re/blob/master/epframebuffer.h)
also names Pen, Animation and UI with matching values, but this experiment is
bound to the actually captured binary, not that repository's ABI assumptions.

## Implemented experiment

`EpaperDisplayControl` verifies the loaded library's hash, mode metadata, QObject
methods and owning thread before enabling controls. It obtains the existing
framebuffer singleton and invokes its Qt slots. It does not allocate a private
framebuffer object, use private field offsets, replace Qt libraries or alter the
waveform file. A changed library or different thread/interface disables the bridge.

- Idle/interface mode: **UI**.
- List movement and dragging: **Animation** until movement ends.
- Canvas page: hold **Pen** mode for the whole session by default. The canvas
  comparison button releases this override to compare the default backend policy.
  Neither choice changes modes per stroke or automatically cleans between strokes.
  The button refuses policy changes while a stroke is active.
- After scrolling/dragging or leaving the canvas, wait 700 ms after interaction
  stops, then request **clearGhosting()**.
- **Clean display**: manually request the same cleanup while idle.
- Tap the display-policy control to return to the backend's default policy for
  an A/B comparison. Disabling restores the mode stack and stops cleanup requests.

Every policy change pops the mode owned by the bridge before pushing its
replacement. Shutdown also restores that stack entry. The timer restarts at the
end of non-canvas input. Manual Clean display remains available when no stroke or
drag is active; this is the explicit way to clear artifacts while staying in the
canvas. No automatic cleanup is scheduled between strokes.

## Evidence and limits

Local tests exercise the actual Qt invocation path against a test QObject, mode
stack balance, cleanup after idle, disabling/restoring, and rejecting an unsupported
backend. A canvas regression check runs repeated stroke start/end notifications
and an idle interval while asserting zero mode-stack changes, cleanup calls or
status-change signals. It then checks that Animation/UI behaviour resumes outside
the canvas. The Mac cannot validate the epaper implementation, physical
screen updates or the version-gated singleton accessor. Native control availability
and performance must still be checked on the tablet.

The captured binary has a different `swapBuffers` signature from some older online
examples. We deliberately do not call it or assume an older library layout.
Even these verified method names do not prove that the proposed policy removes
trails, avoids blank scrolling, or meets the required latency.

## Device test

Stop any running benchmark, then rebuild and deploy:

```sh
python3 tools/standalone.py setup
python3 tools/standalone.py run --pen-input evdevtablet
```

Check that the display-policy control changes between UI and Animation outside
the canvas and reads Pen throughout drawing sessions (or default canvas for the comparison). After releasing a drag or finishing a flick,
wait for the idle cleanup. Compare managed/default policies and the Clean display
button. Record whether the old square position is erased, content remains visible
during scrolling and cleanup removes existing trails. Preserve the smooth pen
behaviour as an acceptance requirement; stop using the new policy if it regresses.

If the status says controls are unavailable or unverified, collect diagnostics:

```sh
python3 tools/standalone.py diagnose --display-library
```

Automatic device orientation remains separate work. The benchmark still uses the
manual Rotate button; no accelerometer library or native rotation integration is
claimed to be present.

## Handwriting benchmark and remaining work

The canvas records samples handled, stroke raster CPU time, paint count and the
mean/max wait from the first pending append to entry into paint(). Counters use a
steady clock; render-thread counters are atomic. A 300 ms writing pause produces
one summary on screen and in `standalone.py logs`; no per-point logging or timer
redraws occur during drawing. Closely spaced strokes accumulate into one burst.
These numbers do **not** measure kernel-to-Qt delivery, paint completion, driver
submission or physical panel latency. Paint count is not the panel refresh rate.
Timing overhead is present in both comparison policies. The image copy respects
Qt's supplied paint clip; this alone is not proof of a performance improvement.

Compare the same short words, tight circles, fast diagonals and pressure changes
in sustained Pen and default modes, then in native Notes. Use the same orientation
and pen. Record a high-frame-rate camera view containing both pen tip and ink;
software timing cannot establish tip-to-visible-ink latency. Collect the journal:

```sh
python3 tools/standalone.py logs
```

If paint waits are high, investigate scene scheduling and a dedicated active-ink
surface. If waits are small but visible lag remains high, investigate submission
and the panel path. The captured library exports
`EPFramebufferAcep2::sendPenUpdate(QRegion const&, QFlags<UpdateFlag>)`, but export
presence does not establish its buffer ownership, synchronization or suitability
for direct invocation. Do not call it with guessed flags or guessed object state.
The existing QImage canvas is still the renderer: a separate live-ink layer,
input timestamp correlation, pressure-curve interpolation and proximity-aware
palm rejection are not yet implemented. This benchmark is the measurement step,
not a claim to reproduce native Notes or a verified low-latency driver bypass.
