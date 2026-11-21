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

The observations above establish connectivity and a caching limitation. No second full game download was performed because the first populated no game cache payload; a repeat-download speedup is unproven. PC reboot, remote-network, server-outage and production migration acceptance remain outstanding.

## Why HTTPS matters

LANCache's [HTTPS documentation](https://lancache.net/docs/faq/#but-what-about-https-can-i-cache-https) states that encrypted traffic is forwarded without being cached. The upstream [Epic HTTPS issue](https://github.com/lancachenet/monolithic/issues/226) also contains reports of launcher behavior changing from HTTP to HTTPS. This lab's TLS stream and disk counters are the evidence for the tested preview build; hostname-list membership alone does not prove cacheability.

No certificate interception, certificate exceptions, HTTPS blocking or forced protocol downgrade was used. Credentials, signed download URLs, tailnet identifiers, private addresses, SSH material and raw logs are excluded from this report.

## Next work

Investigate a publisher-supported caching path or a local downloaded-game library workflow before promoting Epic support. Keep Steam active and Epic direct. Test EA and Microsoft independently; this Epic result says nothing about their current delivery behavior. Implement and test health-based bypass/recovery separately before claiming automatic failover.
