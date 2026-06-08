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

1. Go to **https://eu-data-act.drivesomethinggreater.com**, log in with your
   Volkswagen ID, accept the consent screen, and link your vehicle.
2. Enable a **continuous data request**: *Data clusters → Vehicle overview →
   Get customised data → **All data**, frequency **15 minutes***.
   - Pick **All data** so slots aren't empty while the car is idle (event-only
     clusters like *Charging* / *Driving Behaviour* report nothing when parked).
   - The car must **report** before content appears — open the VW app or drive
     once to trigger the first sync.

Without an active data request the integration shows
`Data status: No data request configured`.

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

1. **EU Data Act portal** — 15-min "continuous data" (only when the car reports;
   can be empty while the car is idle). No 2FA.
2. **volkswagen.de portal (`authproxy`)** — *optional, more reliable*: odometer,
   inspection/oil-service due, and vehicle info, always available once
   authenticated. Uses the website login, which sends an **email OTP during
   setup** (and occasionally on re-auth). Skipping the OTP leaves source #1 only.

## Entities

One device per vehicle:
- **Data status** — `ok` / `no_data` / `not_configured`, with attributes (VIN,
  nickname, plate, enrollment status, data-request id, latest dataset,
  created-on timestamp). Always present.
- **Odometer**, **Inspection due**, **Oil service due**, **Last vehicle report** —
  from the volkswagen.de portal source (when enabled).
- **Live battery / charging** (volkswagen.de portal): Battery (SoC %), Electric range,
  Charging state, Charge power/rate, Charge time remaining, Target battery, Battery
  temperature, Plug / Plug lock / External power.
- **Value sensors** — created dynamically from the latest EU Data Act dataset
  (keys depend on which clusters you enabled). New keys appear as delivered.

## Limitations

- **Read-only.** No remote control (lock/climate/charge) — that needs the
  attestation-gated app API and is not possible.
- **15-minute cadence**, and only when the car actually reports data.
- Available fields depend entirely on the clusters enabled on the portal.

## Supported brands

Volkswagen (Passenger Cars & Commercial Vehicles), Audi, Škoda, SEAT, CUPRA,
Bentley — each via its EU Data Act portal OAuth client.

## Credits

Auth/data flow reverse-engineered with reference to TA2k's
[`ioBroker.vw-connect`](https://github.com/TA2k/ioBroker.vw-connect)
(`lib/euDataAct.js`).

## License

MIT — see [LICENSE](LICENSE).
