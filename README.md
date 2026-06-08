# Volkswagen Connect — Home Assistant integration

A **read-only** Home Assistant integration that pulls your Volkswagen vehicle
data from your **volkswagen.de** account — battery/charging, odometer,
service/inspection due, vehicle-health warning lights, lock history, and the
vehicle image.

> Install via **HACS → ⋮ → Custom repositories →**
> `https://github.com/rafaelhutter/ha-volkswagen-connect` (category *Integration*),
> then add the **Volkswagen Connect** integration.

> Data comes from the **volkswagen.de website session** (the attestation-free
> channel). The EU Data Act portal is supported too, but only as a *future /
> best-effort* source — see [EU Data Act — the future](#eu-data-act--the-future).

## Why this exists

In May–June 2026 Volkswagen retired the WeConnect app OAuth client and put the
CARIAD BFF token exchange behind **app attestation** (Play Integrity / "client
assertion"), which open-source clients cannot satisfy — breaking
`volkswagencarnet`, `evcc`, `openWB`, and others. The **volkswagen.de** website
logs in through a server-side confidential client (`authproxy`) that does **not**
require attestation, so its data is reachable once you authenticate. This
integration reuses that website session.

## Prerequisites (one-time, in a browser)

The data comes from your **volkswagen.de** account, which must be **activated**
for the vehicle once:

1. Go to **https://www.volkswagen.de** → log in with your Volkswagen ID →
   **myVolkswagen**, and open your vehicle.
2. Under *Ihre mobilen Online-Dienste* complete **„Identität bestätigen"**
   (confirm identity) so you become the **Hauptnutzer / primary user**. The
   portal walks you through the *Vehicle Activation Service* and finishes with
   *„Super! Sie sind jetzt startklar."* (all steps **Fertig**).
   - Normal account step — **no S-PIN or in-car confirmation** needed; it reuses
     your existing login. If you already use the VW app or portal, it's usually
     done already.

During integration setup you log in with the same Volkswagen ID and approve an
**email OTP**; the integration then reuses that website session.

## Install

**HACS (recommended)**
1. HACS → ⋮ (top right) → **Custom repositories**.
2. Repository: `https://github.com/rafaelhutter/ha-volkswagen-connect`, category **Integration** → Add.
3. Install **Volkswagen Connect**, then restart Home Assistant.
4. Settings → Devices & Services → **Add Integration** → "Volkswagen Connect".
5. Enter your Volkswagen ID email/password, select your brand, and approve the
   **email OTP** when prompted.

**Manual**
Copy `custom_components/volkswagen_connect/` into your HA `config/custom_components/`,
restart, then add the integration.

## Entities

One device per vehicle:
- **Live battery / charging** (volkswagen.de portal): Battery (SoC %), Electric range,
  Charging state, Charge power/rate, Charge time remaining, Target battery, Battery
  temperature, Plug / Plug lock / External power.
- **Odometer**, **Inspection due**, **Oil service due**, **Last vehicle report**.
- **Warning lights** — number of active dashboard warning lights (`0` = all OK).
- **Last lock command** / **Last lock command time** — most recent *confirmed*
  remote lock/unlock from the transaction log (command history, **not** a live
  lock sensor — see Limitations).
- **Image** — the vehicle's exterior side-view photo.
- **Data status** — `ok` / `no_data` / `not_configured`. Reflects the optional
  EU Data Act source (below); reads `not_configured` until/unless that channel
  delivers and does **not** affect the live data above.

## Limitations

- **Read-only.** No remote control (lock/climate/charge) — that needs the
  attestation-gated app API and is not possible.
- **No live lock / window / door / climate / parking-position status.** These sit
  behind VW's *secured-operations* tier that only the attestation-backed mobile
  app can read (the endpoints return `401` even for a fully-activated primary
  user). The *Last lock command* sensor surfaces the lock/unlock **history**
  instead — treat it as "the last confirmed lock/unlock", not the current state.

## EU Data Act — the future

The EU Data Act obliges carmakers to expose vehicle data through a standardized
portal (`eu-data-act.drivesomethinggreater.com`). In principle that's a cleaner,
officially-sanctioned channel than reusing the website session — so the
integration *also* supports it and will surface any delivered fields as dynamic
**value sensors** (with the **Data status** sensor showing the request state).

**In practice it does not reliably work today:** the portal's delivery is flaky,
frequently returns nothing, and depends on the car reporting into a 15-minute
slot. So it's kept as a **future / best-effort** option, not the primary source.
To experiment with it:

1. Go to **https://eu-data-act.drivesomethinggreater.com**, log in with your
   Volkswagen ID, accept the consent screen, and link your vehicle.
2. Enable a **continuous data request**: *Data clusters → Vehicle overview →
   Get customised data → **All data**, frequency **15 minutes***.

If/when VW's portal becomes dependable, this is the channel to lean on — until
then, rely on the volkswagen.de data above.

## Supported brands

The working **volkswagen.de** source is **Volkswagen** only. The brand selector
feeds the (future) EU Data Act client, which also targets Audi, Škoda, SEAT,
CUPRA and Bentley via their portal OAuth clients — subject to the same
reliability caveat above.

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
