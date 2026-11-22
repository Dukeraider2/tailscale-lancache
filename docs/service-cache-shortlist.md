# Transparent-cache shortlist after encryption review

Reviewed 2026-11-21. Scope: the existing LANCache HTTP cache, preserving end-to-end HTTPS and the current Tailscale/Mullvad design. This is a shortlist decision, not a claim that a publisher can never be supported.

**Keep Steam and investigate Microsoft PC content/updates next. Remove default Epic, modern EA App, GOG Galaxy and Amazon Games from the normal transparent-cache pilot queue; Nexus's tested manual path also belongs outside that queue. Hold LoversLab, Mod DB and itch.io for archive/native-integration work because evidence does not establish a general transparent cache path.**

HTTPS transport prevents this cache from seeing reusable HTTP responses. Encryption/compression of game files themselves does not necessarily prevent caching when those opaque bytes are delivered over cacheable HTTP. An HTTPS login/catalog alongside HTTP game chunks is compatible with a content cache. A website's padlock, CDN ownership, a DNS list entry or a prefill tool alone is not proof about the launcher's game-payload protocol.

## Decisions for the existing list

| Service | Decision | Evidence and confidence |
| --- | --- | --- |
| Steam | **Keep: locally verified** | The [140 reinstall](validation/steam-140.md) served all 126 repeated game-chunk requests as HITs, 51,333,920 bytes. High confidence for that build with Mullvad connected; broader acceptance remains. |
| Microsoft PC Game Pass / Store | **Keep: next pilot** | Microsoft's [endpoint matrix](https://learn.microsoft.com/en-us/windows/deployment/do/delivery-optimization-endpoints) lists PC Game Pass payloads over HTTP/80. This establishes a plausible path, not local LANCache compatibility. Evaluate Delivery Optimization counters and native mechanisms as well. |
| Windows / Microsoft updates | **Keep: separate pilot** | The same matrix lists HTTP delivery for Windows Update/Store and some other products. HTTPS control services are separate. Keep `*.do.dsp.mp.microsoft.com` direct: Microsoft identifies certificate pinning there. Audit the current wildcard profile before activation. |
| Epic, default launcher behavior | **Remove from normal queue; retain workaround research** | Local Preview 0.120.0 [failed cache acceptance](validation/epic-preview-0.120.md). In [upstream issue 226](https://github.com/lancachenet/monolithic/issues/226), August/September 2026 participants report HTTP HITs on traditional launcher builds 20.2.4/20.2.9 using an EMS configuration change. That is a different, version-dependent path, untested on our preview. The reported configuration can be overwritten on launch. The experimental profile remains available for explicit transport/workaround research, not advertised cache support. No downgrade or certificate interception was applied. |
| EA App | **Remove; disable profile generation** | [Maintainer tracking issue 221](https://github.com/uklans/cache-domains/issues/221), opened February 2023 and still open when reviewed, carries `https-cantfix`. A maintainer explains that Origin's integration was not ported to EA Desktop. Strong upstream evidence, but no current local EA trace. Legacy Origin hostnames do not establish EA App support. |
| GOG Galaxy | **Remove; retain offline-installer library** | [Tracking issue 31](https://github.com/uklans/cache-domains/issues/31) reports TLS payload flows and remains marked `https-cantfix`. Its original observations are from 2018, so this is historical upstream evidence rather than a fresh client test. GOG's [official offline installers](https://docs.gog.com/offline-installers/) offer a separate reusable-library path. |
| Amazon Games app | **Remove provisionally; retain archive research** | In [issue 246](https://github.com/uklans/cache-domains/issues/246), an August 2025 participant reports forced HTTPS and HTTP redirects to HTTPS. Medium confidence: firsthand community report, no local validation; the issue is still open and testing-labelled. Games redeemed into other launchers follow those launchers' behavior. |
| Nexus Mods | **Remove the tested manual path; retain archive reuse** | The [local selected-file test](validation/nexus-manual-download.md) recorded four full HTTPS responses and zero HITs, with identical hashes. High confidence for that path; not a universal claim about every mirror or future client. Old `filedelivery.nexusmods.com` lists are insufficient. |
| LoversLab | **Hold transparent work; manual archive import first** | Current [Wabbajack documentation](https://wiki.wabbajack.org/modlist_author_documentation/Meta%20Files.html#manualurl) recommends manual downloads and disables its former LoversLab automated adapter. Its [issue reports](https://github.com/wabbajack-tools/wabbajack/issues/1397) show HTTPS requests. These do not prove every final attachment/mirror is HTTPS-only. No trustworthy current transparent HIT report was established; do not label it conclusively encryption-blocked. |
| Mod DB | **Hold: mirror-specific protocol unknown** | An [August 2026 forum report](https://www.moddb.com/forum/thread/cli-installer-hitting-cloudflare-challenge) shows HTTPS mirror discovery blocked by Cloudflare. That is not the final archive's protocol. Wabbajack documents direct-file acquisition, not transparent caching. Preserve archive import and test an individual final mirror before deciding further. |
| itch.io | **Hold: native/local-storage research** | An [official project discussion](https://github.com/itchio/itch/issues/3393) describes Cloudflare R2 game-archive range requests. A [December 2025 forum thread](https://itch.io/t/5658832/download-links-keep-expiring-during-download) reports expiring links. Neither establishes a reusable LANCache payload path or universal HTTPS-only behavior. Official [butler integration](https://itch.io/docs/butler/launcher-integration.html) and the app's [local-download linking](https://github.com/itchio/itch/blob/master/CHANGELOG.md) are better research directions. External creator hosts need individual assessment. |

## Forum findings that change the interpretation

The Epic workaround reports mean our earlier HTTPS result must be scoped to the tested preview and configuration; it does not justify declaring Epic permanently impossible. Conversely, a prefill success does not prove an unchanged launcher will consume its cache. Investigate any client-side protocol change separately before considering deployment.

The EA maintainer discussion distinguishes the modern app from old Origin support. Amazon's report is less conclusive than that maintainer tracking decision. GOG's label is persistent but based on old traces. These differences matter when choosing what to eliminate versus what merely needs a fresh test.

No reproducible current LANCache HIT report was established for LoversLab, Mod DB or itch.io in the searches reviewed. They are deferred for insufficient evidence, not presented as proven HTTPS-only. Mod DB's discovery-page TLS and anti-bot failures cannot be used to infer final mirror encryption. Likewise, generic references to browser “cache” or an itch CDN's own cache do not demonstrate NAS caching.

## Pruned order

1. Preserve verified Steam operation; finish VPN-off content, remote-client, reboot and recovery acceptance.
2. Pilot a small entitled Microsoft PC game, then a distinct update/Store payload. Inspect DO/cache/peer/origin counters, exact content hosts and file identity. Do not route pinned HTTPS control endpoints or assume Xbox console support from the PC matrix.
3. Build the separate archive foundation for GOG offline installers and mod archives; then evaluate itch's supported local-install workflow. Preserve authorization, identity, quotas and hashes.
4. Keep Epic HTTP-workaround research separate and explicit. Revisit removed services only after changed client behavior or new HIT evidence.

Outside the original list, [Battle.net Prefill](https://github.com/tpill90/battlenet-lancache-prefill) documents a cache-oriented workflow and is a reasonable future pilot candidate, not yet supported by this project. [Riot issue 123](https://github.com/uklans/cache-domains/issues/123) reports a publisher-side fix and successful HTTP caching for Legends of Runeterra in 2022; it illustrates why an old HTTPS failure is not a permanent publisher-wide verdict. Neither service is enabled or added to the installation catalog by this review.

No live DNS, VPN, launcher, router or NAS configuration was changed. Only research/catalog documentation and the EA generation gate were updated.

