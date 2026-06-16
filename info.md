## Volkswagen Connect

Read-only Home Assistant integration that pulls Volkswagen vehicle data from two
attestation-free channels left after VW locked the WeConnect app API behind Play
Integrity in 2026: your **volkswagen.de** account (battery/charging, odometer,
service due, warning lights, lock history, vehicle image) and the **EU Data Act
portal** (a rich set of extra telemetry once you enable a continuous data
request).

**Before adding:** at <https://www.volkswagen.de> → myVolkswagen, confirm your
identity / become the vehicle's primary user (one-time, no S-PIN). Then add this
integration, sign in with your Volkswagen ID, and approve the email OTP. For the
extra EU Data Act sensors, also enable a continuous data request at
<https://eu-data-act.drivesomethinggreater.com>.

Read-only (no remote control, no live lock/window status). EU Data Act enum codes
are shown human-readable, with the raw code kept on each sensor's `raw_value`
attribute.
