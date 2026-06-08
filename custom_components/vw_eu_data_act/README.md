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

### A. Activate connected services on volkswagen.de  *(required for live data)*

The reliable live data (battery/charging, odometer, service-due, vehicle-health
warning lights, lock history, vehicle image) comes from your **volkswagen.de**
account. That account must be **activated** for the vehicle once:

1. Go to **https://www.volkswagen.de** → log in with your Volkswagen ID →
   **myVolkswagen**, and open your vehicle.
2. Under *Ihre mobilen Online-Dienste* complete **„Identität bestätigen"**
   (confirm identity) so you become the **Hauptnutzer / primary user**. The
   portal walks you through the *Vehicle Activation Service* and finishes with
   *„Super! Sie sind jetzt startklar."* (all steps **Fertig**).
   - This is a normal account step — **no S-PIN or in-car confirmation** is
     needed; it reuses your existing login. If you already use the VW app or the
     portal, it is usually done already.
3. That's it — during integration setup you log in with the same Volkswagen ID
   and approve the email **OTP**; the integration then reuses that website
   session for live data.

### B. EU Data Act portal  *(optional — adds 15-min "continuous data")*

1. Go to **https://eu-data-act.drivesomethinggreater.com**, log in with your
   Volkswagen ID, accept the consent screen, and link your vehicle.
2. Enable a **continuous data request**: *Data clusters → Vehicle overview →
   Get customised data → **All data**, frequency **15 minutes***.
   - Select **All data** (not just Charging / Driving Behaviour) so slots aren't
     empty while the car is idle — event-only clusters report nothing when
     parked/not charging.
   - The car must **report** before content appears; open the VW app or drive
     once to trigger the first sync.

Without an active data request the **Data status** sensor shows
`not_configured` — that only affects source B; the live data from source A still
works.

## Install

1. Copy `custom_components/vw_eu_data_act/` into your HA `config/custom_components/`.
2. Restart Home Assistant.
3. Settings → Devices & Services → **Add Integration** → "Volkswagen EU Data Act".
4. Enter your Volkswagen ID email/password and pick your brand.

## Data sources

1. **EU Data Act portal** — 15-min "continuous data" (only when the car reports;
   can be empty while idle). No 2FA.
2. **volkswagen.de portal (`authproxy`)** — *optional, more reliable*: odometer,
   service/inspection due, and vehicle info, always available once authenticated.
   This source uses the website login, which sends an **email OTP** during setup
   (and occasionally on re-auth). If you skip the OTP, the integration still works
   with source #1 only.

## Entities

One device per vehicle, with:
- **Data status** sensor — `ok` / `no_data` / `not_configured`, plus attributes
  (VIN, nickname, plate, enrollment status, data-request id, latest dataset,
  created-on timestamp). Always present.
- **Live battery / charging** (from the volkswagen.de portal): **Battery (SoC %)**,
  **Electric range**, **Charging state**, **Charge power/rate**, **Charge time
  remaining**, **Target battery**, **Battery temperature**, **Plug** / **Plug
  lock** / **External power**. Available whenever the car has reported (not gated
  on the 15-min EU Data Act slot).
- **Odometer**, **Inspection due**, **Oil service due**, **Last vehicle report** —
  also from the portal source.
- **Warning lights** — number of active dashboard warning lights (`0` = all OK).
- **Last lock command** / **Last lock command time** — the most recent *confirmed*
  remote lock/unlock from the vehicle's transaction log (see Limitations: this is
  the command history, **not** a live lock sensor).
- **Image** — the vehicle's exterior side-view photo.
- **Value sensors** — created dynamically from the latest EU Data Act dataset
  (keys depend on which clusters you enabled). New keys appear as delivered.

## Limitations

- **Read-only.** No remote control (lock/climate/charge) — that requires the
  attestation-gated app API and is not possible here.
- **No live lock / window / door / climate / parking-position status.** These sit
  behind VW's *secured-operations* tier, which only the attestation-backed mobile
  app can read (`access/status` etc. return `401` even for a fully-activated
  primary user). The website itself never reads them live — it shows the
  **lock/unlock command history**, which is what the *Last lock command* sensor
  surfaces. Treat it as "the last confirmed lock/unlock", not the current state.
- The **EU Data Act source** is 15-minute cadence and only when the car reports;
  its available fields depend on the clusters you enable on the portal.

## Credits

Flow reverse-engineered with reference to TA2k's `ioBroker.vw-connect`
(`lib/euDataAct.js`).
