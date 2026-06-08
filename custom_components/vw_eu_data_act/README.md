# Volkswagen EU Data Act (Home Assistant)

A **read-only** Home Assistant integration that pulls your Volkswagen vehicle
data from the **EU Data Act portal** (`eu-data-act.drivesomethinggreater.com`)
on a 15-minute cadence.

## Why this exists

In May–June 2026 VW retired the WeConnect app OAuth client and put the CARIAD
BFF token exchange behind **app attestation** (Play Integrity / "client
assertion"), which open-source clients cannot satisfy — this broke
`volkswagencarnet`, `evcc`, `openWB`, etc. The EU Data Act portal is the only
remaining **attestation-free** channel: it logs in via the classic VW Identity
`signin-service` flow with a portal OAuth client and delivers the vehicle's
"continuous data" per the EU Data Act. (Investigation details: see
`HANDOVER-vw-auth-fix.md` in the repo root.)

## Prerequisites (one-time, in a browser)

1. Go to **https://eu-data-act.drivesomethinggreater.com**, log in with your
   Volkswagen ID, accept the consent screen, and link your vehicle.
2. Enable a **continuous data request**: *Data clusters → Vehicle overview →
   Get customised data → **All data**, frequency **15 minutes***.
   - Select **All data** (not just Charging / Driving Behaviour) so slots aren't
     empty while the car is idle — event-only clusters report nothing when
     parked/not charging.
   - The car must **report** before content appears; open the VW app or drive
     once to trigger the first sync.

Without an active data request the integration shows `Data status: No data
request configured`.

## Install

1. Copy `custom_components/vw_eu_data_act/` into your HA `config/custom_components/`.
2. Restart Home Assistant.
3. Settings → Devices & Services → **Add Integration** → "Volkswagen EU Data Act".
4. Enter your Volkswagen ID email/password and pick your brand.

## Entities

One device per vehicle, with:
- **Data status** sensor — `ok` / `no_data` / `not_configured`, plus attributes
  (VIN, nickname, plate, enrollment status, data-request id, latest dataset,
  created-on timestamp). Always present.
- **Value sensors** — created dynamically from the latest delivered dataset
  (keys depend on which EU Data Act clusters you enabled). New keys appear as
  they are first delivered.

## Limitations

- **Read-only.** No remote control (lock/climate/charge) — that requires the
  attestation-gated app API and is not possible here.
- **15-minute cadence**, and only when the car actually reports data.
- The available fields depend entirely on the clusters you enable on the portal.

## Credits

Flow reverse-engineered with reference to TA2k's `ioBroker.vw-connect`
(`lib/euDataAct.js`).
