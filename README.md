# Volkswagen EU Data Act — Home Assistant integration

A **read-only** Home Assistant integration that pulls your Volkswagen vehicle
data from the **EU Data Act portal** (`eu-data-act.drivesomethinggreater.com`)
on a 15-minute cadence.

> Install via **HACS → ⋮ → Custom repositories →**
> `https://github.com/rafaelhutter/hass-vw-eu-data-act` (category *Integration*),
> then add the **Volkswagen EU Data Act** integration.

## Why this exists

In May–June 2026 Volkswagen retired the WeConnect app OAuth client and put the
CARIAD BFF token exchange behind **app attestation** (Play Integrity / "client
assertion"), which open-source clients cannot satisfy — breaking
`volkswagencarnet`, `evcc`, `openWB`, and others. The **EU Data Act portal** is
the only remaining **attestation-free** channel: it logs in via the classic VW
Identity `signin-service` flow with a portal OAuth client and delivers the
vehicle's "continuous data" per the EU Data Act.

## Prerequisites (one-time, in a browser)

### A. Activate connected services on volkswagen.de  *(required for live data)*

The reliable live data (battery/charging, odometer, service-due, vehicle-health
warning lights, lock history, vehicle image) comes from your **volkswagen.de**
account, which must be **activated** for the vehicle once:

1. Go to **https://www.volkswagen.de** → log in with your Volkswagen ID →
   **myVolkswagen**, and open your vehicle.
2. Under *Ihre mobilen Online-Dienste* complete **„Identität bestätigen"**
   (confirm identity) so you become the **Hauptnutzer / primary user**. The
   portal walks you through the *Vehicle Activation Service* and finishes with
   *„Super! Sie sind jetzt startklar."* (all steps **Fertig**).
   - Normal account step — **no S-PIN or in-car confirmation** needed; it reuses
     your existing login. If you already use the VW app or portal, it's usually
     done already.

### B. EU Data Act portal  *(optional — adds 15-min "continuous data")*

1. Go to **https://eu-data-act.drivesomethinggreater.com**, log in with your
   Volkswagen ID, accept the consent screen, and link your vehicle.
2. Enable a **continuous data request**: *Data clusters → Vehicle overview →
   Get customised data → **All data**, frequency **15 minutes***.
   - Pick **All data** so slots aren't empty while the car is idle (event-only
     clusters like *Charging* / *Driving Behaviour* report nothing when parked).
   - The car must **report** before content appears — open the VW app or drive
     once to trigger the first sync.

Without an active data request the **Data status** sensor shows
`not_configured` — that only affects source B; the live data from source A
(above) still works.

## Install

**HACS (recommended)**
1. HACS → ⋮ (top right) → **Custom repositories**.
2. Repository: `https://github.com/rafaelhutter/hass-vw-eu-data-act`, category **Integration** → Add.
3. Install **Volkswagen EU Data Act**, then restart Home Assistant.
4. Settings → Devices & Services → **Add Integration** → "Volkswagen EU Data Act".
5. Enter your Volkswagen ID email/password and select your brand.

**Manual**
Copy `custom_components/vw_eu_data_act/` into your HA `config/custom_components/`,
restart, then add the integration.

## Data sources

1. **volkswagen.de portal (`authproxy`)** — the *reliable* source: live
   battery/charging, odometer, inspection/oil-service due, vehicle-health warning
   lights, lock history, vehicle image, always available once authenticated. Uses
   the website login, which sends an **email OTP during setup** (and occasionally
   on re-auth).
2. **EU Data Act portal** — *optional*: 15-min "continuous data" (only when the
   car reports; can be empty while the car is idle). No 2FA. Skipping its setup
   (or the OTP for source 1) just narrows the entity list.

## Entities

One device per vehicle:
- **Data status** — `ok` / `no_data` / `not_configured`, with attributes (VIN,
  nickname, plate, enrollment status, data-request id, latest dataset,
  created-on timestamp). Always present.
- **Live battery / charging** (volkswagen.de portal): Battery (SoC %), Electric range,
  Charging state, Charge power/rate, Charge time remaining, Target battery, Battery
  temperature, Plug / Plug lock / External power.
- **Odometer**, **Inspection due**, **Oil service due**, **Last vehicle report** —
  from the volkswagen.de portal source.
- **Warning lights** — number of active dashboard warning lights (`0` = all OK).
- **Last lock command** / **Last lock command time** — most recent *confirmed*
  remote lock/unlock from the transaction log (command history, **not** a live
  lock sensor — see Limitations).
- **Image** — the vehicle's exterior side-view photo.
- **Value sensors** — created dynamically from the latest EU Data Act dataset
  (keys depend on which clusters you enabled). New keys appear as delivered.

## Limitations

- **Read-only.** No remote control (lock/climate/charge) — that needs the
  attestation-gated app API and is not possible.
- **No live lock / window / door / climate / parking-position status.** These sit
  behind VW's *secured-operations* tier that only the attestation-backed mobile
  app can read (the endpoints return `401` even for a fully-activated primary
  user). The *Last lock command* sensor surfaces the lock/unlock **history**
  instead — treat it as "the last confirmed lock/unlock", not the current state.
- The **EU Data Act source** is 15-minute cadence and only when the car reports;
  its available fields depend on the clusters you enable on the portal.

## Supported brands

Volkswagen (Passenger Cars & Commercial Vehicles), Audi, Škoda, SEAT, CUPRA,
Bentley — each via its EU Data Act portal OAuth client.

## Credits

Stands on the shoulders of robinostlund's
[`volkswagencarnet`](https://github.com/robinostlund/volkswagencarnet), which did
the heavy lifting over many years as *the* Home Assistant VW integration. When
VW's 2026 app-attestation lock broke the underlying API, this project picks up
where it left off — extending and fixing access through the remaining
attestation-free channels.

Auth/data flow reverse-engineered with reference to TA2k's
[`ioBroker.vw-connect`](https://github.com/TA2k/ioBroker.vw-connect)
(`lib/euDataAct.js`).

## License

MIT — see [LICENSE](LICENSE).
