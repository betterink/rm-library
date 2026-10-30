# reMarkable application library

Independent application bundles for the Ink portal. The first application is a
[QML + Kotlin/Native AppLoad example](example/README.md) for validating Paper Pro
development. It lives entirely in this repository and does not modify AppLoad.

```sh
python3 tools/example.py doctor
python3 tools/example.py build
python3 tools/example.py deploy
python3 tools/example.py verify
```

The build creates `dist/ink-example-dev.tar.gz`, not a firmware or container image.
Generated binaries and tool downloads stay out of source control. No tablet
passwords or SSH private keys belong in this repository.

For investigating scrolling and pen performance independently of AppLoad, use the
[standalone Qt benchmark](standalone/README.md):

```sh
python3 tools/standalone.py preview
python3 tools/standalone.py setup
```

The Mac preview is buildable with the installed Qt tools. Building a tablet bundle
requires a Linux environment and a suitable Paper Pro SDK; see its README before
deploying or taking over the tablet display.
The setup command uses Docker and the recorded SDK candidate to build and install.
Launch separately with `python3 tools/standalone.py run`; an on-tablet Apps entry
is not yet implemented.
