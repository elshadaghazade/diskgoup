#!/usr/bin/env bash
# Attach the built artifacts to the GitHub Release of the pushed tag.
#
#   scripts/publish-release.sh <tag> <artifact-dir>
#
# The CLI workflow and the desktop workflow both call this, and they race for
# the release: the first one to arrive creates it, the other one waits for it
# and attaches its files. The upload is retried, because a release that is
# being created at that very moment is not yet visible.

set -euo pipefail

tag="${1:?usage: publish-release.sh <tag> <artifact-dir>}"
dir="${2:?usage: publish-release.sh <tag> <artifact-dir>}"

if [ -z "${GH_TOKEN:-}" ]; then
    echo "✗ GH_TOKEN is not set" >&2
    exit 1
fi

if [ ! -d "$dir" ]; then
    echo "✗ $dir is not a directory" >&2
    exit 1
fi

# Wait for the release to exist — creating it if nobody else has yet.
if ! gh release view "$tag" >/dev/null 2>&1; then
    echo "→ creating the release $tag"
    for _ in $(seq 1 12); do
        gh release create "$tag" --verify-tag --title "DiskGOup $tag" \
            --generate-notes >/dev/null 2>&1 || true
        if gh release view "$tag" >/dev/null 2>&1; then
            break
        fi
        sleep 5
    done
fi

if ! gh release view "$tag" >/dev/null 2>&1; then
    echo "✗ the release $tag could not be created" >&2
    exit 1
fi

echo "→ attaching $(find "$dir" -maxdepth 1 -type f | wc -l | tr -d ' ') files"
for attempt in 1 2 3; do
    if gh release upload "$tag" "$dir"/* --clobber; then
        exit 0
    fi
    echo "→ the upload failed, retrying (attempt $attempt)"
    sleep 5
done

echo "✗ the upload failed" >&2
exit 1
