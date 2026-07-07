#!/usr/bin/env bash
# Renew the LillyCam Tailscale TLS certificate and reload the service.
#
# Tailscale certs are Let's Encrypt certs (90-day validity) and are NOT
# auto-renewed, so run this on a timer (see lillycam-cert-renew.timer). It is
# safe to run often: `tailscale cert` only re-issues when the cert is close to
# expiry, and this script restarts LillyCam only when the certificate actually
# changed.
#
# Requires root (tailscale cert needs root without an operator set, and the
# restart needs systemctl). Configure the domain via TS_CERT_DOMAIN.
set -euo pipefail

DOMAIN="${TS_CERT_DOMAIN:?set TS_CERT_DOMAIN to your Tailscale MagicDNS name, e.g. lillycam.tailXXXXX.ts.net}"
CERT="${TAILSCALE_CERT:-/home/admin/lillycam/${DOMAIN}.crt}"
KEY="${TAILSCALE_KEY:-/home/admin/lillycam/${DOMAIN}.key}"
SERVICE="${LILLYCAM_SERVICE:-lillycam}"
OWNER="${CERT_OWNER:-admin}"

fingerprint() { [ -f "$1" ] && openssl x509 -noout -fingerprint -sha256 -in "$1" 2>/dev/null || true; }

before="$(fingerprint "$CERT")"
tailscale cert --cert-file "$CERT" --key-file "$KEY" "$DOMAIN"
chown "$OWNER:$OWNER" "$CERT" "$KEY"
chmod 600 "$KEY"
after="$(fingerprint "$CERT")"

if [ "$before" != "$after" ]; then
  echo "Certificate renewed; restarting $SERVICE"
  systemctl restart "$SERVICE"
else
  echo "Certificate still current; no restart needed"
fi
