# Epic Launcher Preview 0.120.0 staging

## Result

The staged endpoint works through Tailscale with Mullvad connected and disconnected. Epic Launcher Preview 0.120.0 on Windows downloads 20XX through TLS passthrough, but transparent caching has not passed acceptance. Keep this profile experimental and retain direct Epic downloads outside a bounded trial.

## What was checked

- A separate TrueNAS custom app and Docker bridge, with a 16 GB child dataset quota and a 4 GiB content cache. Existing Steam storage and application settings were preserved.
- The staging node advertises only the cache host route. Client probes require that approved Tailscale `/32` route.
- The HTTP cache heartbeat returns 204. Epic HTTP and HTTPS HEAD probes reach the origin; the origin returns 403 and its TLS certificate validates.
- The endpoint probes and existing Steam DNS, MagicDNS, ordinary DNS and heartbeat checks pass with Mullvad disconnected and connected.
- A separate loopback DNS proxy and exact Epic content rules were installed for a bounded, reversible client trial. Existing Steam rules remain unchanged. The trial has automatic cleanup after two hours; this machine-specific trial is not an installer feature shipped in this repository.
- A real 20XX download completed and the launcher showed a Launch action. The UI reported a 675 MB download and 1.5 GB space requirement. The installed files totaled approximately 1.66 GB.
- The staging stream logs recorded 718,807,293 bytes sent across the selected Epic CDN hosts, including probe/metadata traffic and TLS overhead. This is a transport total, not a cache-hit byte count. HTTP cache payload bytes were zero, no HIT was recorded, and the cache directory occupied only 6 KiB.
- VPN transitions briefly produced DNS lookup errors during some checks. After the connection settled, individual Epic, Steam, ordinary DNS and MagicDNS A lookups passed with the VPN off; connected-state checks also passed. This does not establish interruption-free transitions or automatic outage recovery.
- The scheduled two-hour cleanup ran, direct Epic resolution was restored, and existing Steam checks still passed with Mullvad connected. The installed game was retained.
- A subsequent staging-app redeploy recovered the existing Tailscale identity without an enrollment key or a new login. Route, heartbeat and valid-origin-TLS probes passed afterward. The staging router intentionally declines routes advertised by other peers.

The initial observations above establish connectivity and a caching limitation. A later controlled reinstall is documented below; a repeat-download cache speedup remains unproven. PC reboot, remote-network, server-outage and production migration acceptance remain outstanding.

## Controlled reinstall and route verification: 2026-11-21

20XX was backed up, uninstalled through the launcher, and reinstalled to the same game library. This was one download divided into paused/resumed phases, not four independent downloads or a cold/warm benchmark.

| Phase | Observed result |
| --- | --- |
| Direct, Mullvad connected | Download progressed from its start to approximately 37%; process-associated TCP connection metadata was collected. |
| Direct, Mullvad disconnected | Download resumed and progressed to approximately 64%. |
| Tailscale staging, Mullvad connected | Exact Epic content DNS rules were enabled; download resumed and progressed to approximately 67%. PC samples showed TCP 443 to the staging endpoint. |
| Tailscale staging, Mullvad disconnected | Download resumed, progressed through 89%, and subsequently completed. PC samples again showed TCP 443 to the staging endpoint. Mullvad was restored to connected afterward. |

Temporary staging stream logs recorded SNI, actual upstream address, connection timing and byte counters. `egdownload.fastly-edge.com` accounted for 285,731,477 bytes sent across 50 completed TCP 443 sessions and two upstream addresses. A separate `download.epicgames.com` HEAD probe accounted for 5,518 bytes and is excluded from that game-CDN total. These are TLS transport counters, including overhead, not decrypted payload or cache-hit totals.

OPNsense Insight, filtered to the NAS source on one LAN interface, showed approximately 256 MB and 29 MB for the same two upstream addresses, with last-seen times matching completed staging connections. Those router values corroborate the endpoint selection; they are rounded daily aggregates and must not be added to the staging totals. The IPs were retained only in private evidence because CDN addresses rotate. Other NAS flows and launcher API connections were not classified as game payload merely because they occurred during the test.

No HTTP game payload or HIT was recorded; cache allocation remained 6 KiB. The result confirms Tailscale transport in both settled VPN states, while this preview build still uses TLS passthrough. It does not demonstrate cache savings or uninterrupted VPN transitions. An initial staging DNS installation immediately after a VPN reconnect failed and automatically rolled back; route/heartbeat/origin-TLS checks then passed, and a settled-state retry succeeded. Health-based bypass/recovery remains required before production promotion.

The launcher showed Play after completion. SHA-256 checks matched all 3,743 non-launcher-metadata files (1,663,566,884 bytes) against the retained backup, with no missing or different files. Test DNS rules and tasks were removed, direct Epic DNS restored, temporary staging logging reverted, Mullvad restored to connected, and Steam DNS/ordinary DNS/heartbeat checks passed. Existing Steam rules were preserved. No router policy was changed, and no payload capture or certificate interception was used.

## Why HTTPS matters

LANCache's [HTTPS documentation](https://lancache.net/docs/faq/#but-what-about-https-can-i-cache-https) states that encrypted traffic is forwarded without being cached. The upstream [Epic HTTPS issue](https://github.com/lancachenet/monolithic/issues/226) also contains reports of launcher behavior changing from HTTP to HTTPS. This lab's TLS stream and disk counters are the evidence for the tested preview build; hostname-list membership alone does not prove cacheability.

No certificate interception, certificate exceptions, HTTPS blocking or forced protocol downgrade was used. Credentials, signed download URLs, tailnet identifiers, private addresses, SSH material and raw logs are excluded from this report.

## Next work

Investigate a publisher-supported caching path or a local downloaded-game library workflow before promoting Epic support. Keep Steam active and Epic direct. Test EA and Microsoft independently; this Epic result says nothing about their current delivery behavior. Implement and test health-based bypass/recovery separately before claiming automatic failover.

