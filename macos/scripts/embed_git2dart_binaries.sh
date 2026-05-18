#!/bin/sh
set -e

FRAMEWORKS_DIR="${TARGET_BUILD_DIR}/${FRAMEWORKS_FOLDER_PATH}"
if [ ! -d "${FRAMEWORKS_DIR}" ]; then
  exit 0
fi

if [ -f "${FRAMEWORKS_DIR}/libgit2.dylib" ]; then
  ln -sf libgit2.dylib "${FRAMEWORKS_DIR}/libgit2-experimental.1.9.dylib"
fi

GIT2DART_MACOS="${PODS_ROOT}/../Flutter/ephemeral/.symlinks/plugins/git2dart_binaries/macos"
if [ -f "${GIT2DART_MACOS}/libssh2.1.dylib" ] && [ ! -f "${FRAMEWORKS_DIR}/libssh2.1.dylib" ]; then
  cp "${GIT2DART_MACOS}/libssh2.1.dylib" "${FRAMEWORKS_DIR}/"
fi
