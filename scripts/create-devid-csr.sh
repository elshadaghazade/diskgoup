#!/usr/bin/env bash
# Ask Apple for a Developer ID Application certificate.
#
#   scripts/create-devid-csr.sh <where-to-put-the-files>
#
# Xcode does this on its own — Settings → Accounts → the team → Manage
# Certificates → + → Developer ID Application. Use this script only when
# the certificate is requested from developer.apple.com instead:
#
#   1. run this script, which writes a request and its private key
#   2. developer.apple.com → Certificates → + → Developer ID Application
#      → upload the .csr → download the .cer
#   3. the .cer and the .key are the two halves of one certificate:
#
#        openssl x509 -inform der -in Developer_ID_Application.cer \
#          -out cert.pem -signkey key.pem -outform pem
#
#   4. put the two halves into one .p12, which is what the build wants:
#
#        openssl pkcs12 -export -inkey key.pem -in cert.pem \
#          -out Developer_ID_Application.p12 -passout pass:…
#
#   5. and put that .p12 into the repository environment:
#
#        scripts/upload-macos-cert.sh Developer_ID_Application.p12
#
# The private key never leaves the machine it was made on, and the .p12
# never goes into the repository — only into the environment secrets.

set -euo pipefail

out="${1:?usage: create-devid-csr.sh <directory for the files>}"

if [ ! -d "$out" ]; then
  echo "✗ $out is not a directory" >&2
  exit 1
fi

csr="$out/diskgoup-developer-id.csr"
key="$out/diskgoup-developer-id.key"

openssl req -new -newkey rsa:4096 -nodes \
  -keyout "$key" -out "$csr" \
  -subj "/CN=Developer ID Application/O=DiskGOup/C=EE"

chmod 600 "$key"

echo "✓ the request is here: $csr"
echo "  the private key is here: $key — keep it, the certificate needs it"
echo
echo "Upload the .csr at developer.apple.com → Certificates → + →"
echo "Developer ID Application, then follow the steps in the header of"
echo "this script."
