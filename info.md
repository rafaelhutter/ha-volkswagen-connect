## Volkswagen Connect

Read-only Home Assistant integration that pulls Volkswagen vehicle data from your
**volkswagen.de** account — the attestation-free channel left after VW locked the
WeConnect app API behind Play Integrity in 2026. Battery/charging, odometer,
service due, warning lights, lock history, and the vehicle image.

**Before adding:** at <https://www.volkswagen.de> → myVolkswagen, confirm your
identity / become the vehicle's primary user (one-time, no S-PIN). Then add this
integration, sign in with your Volkswagen ID, and approve the email OTP.

Read-only (no remote control, no live lock/window status). The EU Data Act portal
is supported as a future/best-effort source but is currently unreliable.
