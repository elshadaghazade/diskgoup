#!/usr/bin/env bash
# Put a Developer ID Application certificate into the repository environment.
#
#   scripts/upload-macos-cert.sh <certificate.p12>
#   scripts/upload-macos-cert.sh <certificate.p12> <password>
#
# Without the password on the command line the script asks for it, without
# echoing it: a password that sits in the shell history, or in the process
# list, is a password that leaks.
#
# The certificate is what makes macOS open the app without calling it
# damaged: it is signed with it, notarized by Apple and stapled to the
# bundle. It lives in the environment "MACOS_CERTIFICATE" of the repository,
# next to the Apple credentials that do the notarization.
#
# The certificate is exported from the keychain with the private key:
#
#   Keychain Access → My Certificates → the "Developer ID Application"
#   certificate *and* its private key → right-click → Export… →
#   Personal Information Exchange (.p12)
#
# The script refuses a certificate that is not a Developer ID Application one:
# the Apple Distribution certificate — the one the App Store uses — cannot be
# notarized outside the App Store, and an app signed with it is refused by
# Gatekeeper all the same.

set -euo pipefail

p12="${1:?usage: upload-macos-cert.sh <certificate.p12> [password]}"
password="${2:-}"

if [ ! -f "$p12" ]; then
  echo "✗ $p12 is not a file" >&2
  exit 1
fi

if [ -z "$password" ]; then
  read -r -s -p "the password of $p12: " password
  echo
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

if ! openssl pkcs12 -in "$p12" -nokeys -passin "pass:$password" \
     -out "$work/certificates.pem" 2>"$work/log"; then
  # A file exported from Keychain Access or from the Apple portal is often
  # encrypted with RC2, which OpenSSL 3 only reads with its legacy provider.
  cp "$work/log" "$work/log-plain"
  if ! openssl pkcs12 -legacy -in "$p12" -nokeys -passin "pass:$password" \
       -out "$work/certificates.pem" 2>"$work/log"; then
    echo "✗ the certificate could not be read — is the password right?" >&2
    tr '\n' ' ' < "$work/log-plain" >&2
    echo >&2
    exit 1
  fi
fi

subjects="$(openssl crl2pkcs7 -nocrl -certfile "$work/certificates.pem" 2>/dev/null \
  | openssl pkcs7 -print_certs -noout 2>/dev/null || true)"

case "$subjects" in
  *"Developer ID Application"*) ;;
  *)
    echo "✗ this is not a Developer ID Application certificate:" >&2
    printf '%s\n' "$subjects" | sed 's/^/  /' >&2
    echo "  The Apple Distribution certificate — the one the App Store uses —" >&2
    echo "  cannot be notarized outside the App Store, and an app signed with" >&2
    echo "  it is blocked by Gatekeeper all the same." >&2
    echo "  Create the right one in Xcode: Settings → Accounts → the team →" >&2
    echo "  Manage Certificates → + → Developer ID Application." >&2
    exit 1
    ;;
esac

echo "→ $subjects"

# The secret is the .p12 as base64 — one line, without the line breaks the
# encoder adds by default.
gh secret set MACOS_CERTIFICATE --env MACOS_CERTIFICATE \
  --body "$(openssl base64 -A -in "$p12")"
gh secret set MACOS_CERTIFICATE_PASSWORD --env MACOS_CERTIFICATE \
  --body "$password"

echo "✓ the certificate is in the environment MACOS_CERTIFICATE"
echo "  The next release of the app is signed with it and notarized by Apple."
