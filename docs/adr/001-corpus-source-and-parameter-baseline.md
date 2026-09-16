# ADR 001: Corpus source and parameter baseline

- Status: Accepted for the initial corpus
- Date: 2026-09-16
- Scope: Handoff phase Week 0

## Context

The first corpus must be reproducible without redistributing uploaded ULog files. It also needs a homogeneous firmware baseline whose requirement parameters are documented. The public index and upstream implementation are mutable external dependencies, so this record distinguishes observations made on the access date from project assumptions.

## Verified source behavior

On 2026-09-16, `https://review.px4.io/dbinfo` returned a JSON array with 464,212 entries. A sampled entry included both `duration_s` and `ver_sw_release`; therefore the initial selector may apply duration and firmware-minor filters before downloading. The selector must still validate these values from the ULog header after download because index metadata is not the validation authority.

The current upstream `PX4/flight_review` `app/download_logs.py` confirms:

- the index endpoint is `https://review.px4.io/dbinfo`;
- the compatibility download endpoint is `https://review.px4.io/download?log=<log_id>`;
- the default inter-request delay is 6 seconds;
- `--max-num` defaults to 10 and values above 100 require confirmation;
- filters include MAV type, flight modes, error labels, rating, vehicle UUID/name, airframe, source, and firmware Git hash;
- HTTP 404 is treated as a missing/deleted public log rather than a fatal run error.

The index currently also provides a per-entry `download_url`. The project deliberately uses the compatibility endpoint above because it is the interface documented by the upstream downloader; this choice is isolated behind the corpus client.

## Initial selection decision

Use PX4 v1.15 as the first firmware-minor series. On the access-date snapshot, 6,649 entries met all index-level filters: v1.15 release, Mission mode present (`flight_modes` contains `3`), duration 60 through 1,200 seconds, and a multicopter MAV type.

The accepted multicopter MAVLink enum values are:

| Integer | MAVLink name | Index label |
|---:|---|---|
| 2 | `MAV_TYPE_QUADROTOR` | `Quadrotor` |
| 13 | `MAV_TYPE_HEXAROTOR` | `Hexarotor` |
| 14 | `MAV_TYPE_OCTOROTOR` | `Octorotor` |

The first manifest will select 20 logs deterministically, preferring the latest eligible log per non-empty `vehicle_uuid` before admitting another log for the same vehicle. A missing UUID makes that log its own group and is counted explicitly.

## Parameter name and unit baseline

The v1.15 PX4 parameter reference was checked on 2026-09-16. The initial resolver uses the following logical names and refuses unit mismatches:

| Logical name | v1.15 parameter candidates, in order | Unit | Special handling |
|---|---|---|---|
| `bat_low_thr` | `BAT_LOW_THR` | fraction (`norm`) | none |
| `bat_n_cells` | `BAT1_N_CELLS`, `BAT_N_CELLS` | cell count | zero means unknown/disabled |
| `bat_v_empty` | `BAT1_V_EMPTY`, `BAT_V_EMPTY` | volts per cell | none |
| `gf_max_hor_dist` | `GF_MAX_HOR_DIST` | m | zero disables the geofence |
| `mpc_land_speed` | `MPC_LAND_SPEED` | m/s | none |
| `mpc_land_alt2` | `MPC_LAND_ALT2` | m | none |
| `com_disarm_land` | `COM_DISARM_LAND` | s | zero or negative disables auto-disarm-after-land |

`BAT_N_CELLS` and `BAT_V_EMPTY` are retained only as aliases for older logs. Thresholds resolve from initial parameters. A required parameter changed in flight makes the result `not_evaluable` with cause `param_changed_in_flight`.

## Licensing and publication decision

The `PX4/flight_review` source repository carries a BSD 3-Clause license for its code. No license grant for user-uploaded public log contents was found in the upstream repository, downloader, or public index on 2026-09-16. Public visibility is not treated as permission to redistribute.

Consequences:

- raw `.ulg` files remain git-ignored and are never redistributed;
- the repository publishes only log IDs, checksums, source metadata, derived aggregates, and expected outputs;
- reproduction is described as best effort against a mutable public service;
- deleted logs are recorded in `corpus/missing.json` and do not abort the run.

## Sources

Accessed 2026-09-16:

- PX4 Flight Review public index: <https://review.px4.io/dbinfo>
- PX4 Flight Review downloader: <https://github.com/PX4/flight_review/blob/main/app/download_logs.py>
- PX4 Flight Review source license: <https://github.com/PX4/flight_review/blob/main/LICENSE.md>
- MAVLink `MAV_TYPE` enum: <https://mavlink.io/en/messages/minimal.html#MAV_TYPE>
- PX4 v1.15 parameter reference: <https://docs.px4.io/v1.15/en/advanced_config/parameter_reference>

## Environment limitation

This verification was performed on an Ubuntu 26.04 execution host using a workspace-managed CPython 3.12.11 runtime. It was not performed inside the required WSL2 Ubuntu 24.04 environment. The findings are suitable for implementation, but the final clean-environment reproduction and all timing measurements must be repeated in the mandated environment before publication.
