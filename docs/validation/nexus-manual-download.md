# Nexus Mods manual-download pilot

Test date: 2026-11-21. Result: **Tailscale HTTPS transport passed in both settled Mullvad states; transparent caching failed acceptance.** Nexus remains research-only in the service catalog.

## Test item and method

The user selected [Gunslinger Protocol (One Handed Pistols), Helldivers 2 mod 18669, file 74397](https://www.nexusmods.com/helldivers2/mods/18669?tab=files&file_id=74397). The archive was 5,475,016 bytes. The normal signed-in manual download provided a temporary HTTPS link on `supporter-files.nexus-cdn.com`.

The browser download was retained as the integrity reference. A direct command-line control download and four staged downloads used the same authorized link. Each staged request connected only that request to the existing isolated cache's approved Tailscale host route, preserving the original HTTPS hostname, SNI and certificate validation. No system-wide Nexus DNS rules or new server domain profile were installed. This tests the existing SNI forwarding path, not browser/Vortex integration with a Nexus DNS profile.

| Request | Mullvad | Result | Archive bytes | Matches browser SHA-256 |
| --- | --- | --- | ---: | --- |
| Direct control | Connected | HTTP 200; valid origin TLS | 5,475,016 | Yes |
| Staged first | Connected | HTTP 200; valid origin TLS | 5,475,016 | Yes |
| Staged repeat | Connected | HTTP 200; valid origin TLS | 5,475,016 | Yes |
| Staged first | Disconnected | HTTP 200; valid origin TLS | 5,475,016 | Yes |
| Staged repeat | Disconnected | HTTP 200; valid origin TLS | 5,475,016 | Yes |

All five copies matched SHA-256 `8b463ec43b0da40d1d8cf0490215449e1b414594bb055eafee4dbced1878d1de`. The ZIP directory contained six entries totaling 26,289,484 uncompressed bytes. The mod was not extracted, installed or executed.

## Cache evidence

Temporary metadata-only staging logs recorded four completed TCP 443 connections for `supporter-files.nexus-cdn.com`, totaling 21,964,840 bytes sent to the client. They identified the actual upstream address; the rotating edge address and private route were retained outside Git. The transport total includes TLS overhead and is distinct from the four archives' 21,900,064 payload bytes.

Before the run, Nexus HTTP and TLS counters were empty. Afterward, there were no Nexus HTTP payload requests or HITs; cache allocation remained 6 KiB. Repeating the download transferred another complete encrypted response through the server. No transparent cache benefit was demonstrated. LANCache's [HTTPS behavior](https://lancache.net/docs/faq/#but-what-about-https-can-i-cache-https) explains this passthrough limitation.

The [upstream Nexus list](https://raw.githubusercontent.com/uklans/cache-domains/master/nexusmods.txt) contained `filedelivery.nexusmods.com` when reviewed. It did not contain this observed delivery host. That is hostname evidence only: adding the newer hostname would not make its HTTPS payload cacheable.

## Cleanup and limits

Mullvad was restored to its initial connected state, original staging logging was restored, and Steam DNS, ordinary DNS and cache heartbeat checks passed. No router policies, persistent Nexus rules, credentials or game installations were changed. Signed URLs, authorization queries, account identifiers and raw logs are excluded from this report. The downloaded archives remain private and are not distributed by this repository.

This is one selected manual download, with a command-line repeat using the browser-issued authorization. It does not establish support for every Nexus mirror, Premium downloads, Vortex/MO2, link renewal, resume, updates, remote-client performance or interruption-free VPN transitions. The practical next pilot is authorized local archive storage and hash-verified mod-manager import, with stable game/mod/file identity and per-user access. That would be archive reuse rather than transparent HTTPS caching.

