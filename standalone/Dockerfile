FROM ubuntu:22.04
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl xz-utils zstd bzip2 unzip cpio file python3 cmake make g++ locales \
    libegl1 libgl1 libxkbcommon0 libxcb1 \
    && locale-gen en_US.UTF-8 && rm -rf /var/lib/apt/lists/*
ENV LANG=en_US.UTF-8
ARG SDK_URL
ARG SDK_HOST_ARCH=aarch64
RUN case "$SDK_URL" in \
    https://storage.googleapis.com/remarkable-codex-toolchain/*/remarkable-*-ferrari-public-${SDK_HOST_ARCH}-toolchain.sh) ;; \
    *) echo 'Supply an official ferrari SDK URL matching the container host architecture.' >&2; exit 1 ;; esac \
    && curl --fail --location --retry 2 "$SDK_URL" -o /tmp/sdk.sh \
    && chmod +x /tmp/sdk.sh && /tmp/sdk.sh -y -d /opt/rm-sdk && rm /tmp/sdk.sh
ENV INK_BUILD_SDK_URL=${SDK_URL}
WORKDIR /workspace
CMD ["bash", "standalone/container-build.sh"]
