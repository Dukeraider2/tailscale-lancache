# Steam cache verification: 140

Test date: 2026-11-21. Result: **real Steam game-content cache HITs verified on a completed reinstall with Mullvad connected.**

## Method

The user selected the initially uninstalled game **140**, Steam app `242820`. Steam downloaded it to the selected games library using the existing NAS cache configuration. The installed build was `4183311`, Windows depot `242822`, manifest `7957190820807887385`.

The first install completed and Steam displayed Play. Its 58 files, totaling 87,429,644 bytes, were copied to a separate backup and SHA-256 verified. With the user's confirmation, the fresh test copy was uninstalled; the user completed Steam's uninstall confirmation. The install manifest and game folder were verified absent while the backup remained. Steam's CLI protocol then opened a new installation of the same game to the same library. No files were restored from the backup before that second download.

Mullvad remained connected throughout both downloads. Existing Steam discovery DNS, cache settings, storage quota and VPN settings were retained. No cache purge or unrelated game removal was performed, and the game was not launched.

## Evidence

Counters were filtered to the selected depot rather than treating historical aggregate Steam hits as this test's result. The repeat window began after a separate pre-reinstall snapshot. Cache HTTP response bytes are compressed delivery bytes and differ from installed file sizes.

| Observation | Requests | HTTP response bytes |
| --- | ---: | ---: |
| Depot counters after first install: MISS | 127 | 50,611,350 |
| Depot counters after first install: HIT | 1 | 1,035,152 |
| Repeat download only: game chunks, HIT / HTTP 200 | 126 | 51,333,920 |
| Repeat download only: manifest, MISS / HTTP 200 | 1 | 11,883 |
| Repeat download only: game chunks, MISS | 0 | 0 |

All recorded game-chunk requests during the repeat were served from the NAS cache. The small manifest was fetched again. This establishes content reuse and avoids fetching those chunk responses again through the cache's origin path. It is not a measurement of all PC/router WAN traffic, TCP overhead, advertisements, account traffic or unrelated applications. No download-speed improvement percentage is claimed.

Steam displayed Play and all downloads complete after the reinstall. All 58 files matched the first installation's SHA-256 hashes, with zero missing or different files; build identity was unchanged. The reinstalled game and verified backup were retained. Mullvad was still connected, and Steam DNS, ordinary DNS and cache heartbeat checks passed afterward.

## Scope

This validates the existing configuration for this game's tested Windows build with Mullvad connected. A full game download with Mullvad disconnected, another remote Tailscale client/network, reboot persistence, cache-outage recovery, updates and other titles remain separate acceptance cases. Earlier endpoint checks are not substitutes for those content tests. Private addresses, account identifiers, client-session values and raw traffic logs are excluded from this report.

