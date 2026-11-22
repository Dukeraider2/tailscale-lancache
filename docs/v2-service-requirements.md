# v2 service requirements and route verification

Research date: 2026-11-21. This is an implementation plan, not a compatibility announcement. Mod DB (`moddb.com`, catalog ID `moddb`) and itch.io (`itchio`) are now research targets. They cannot be enabled as DNS profiles yet.

The project needs three delivery paths: transparent caching for demonstrated HTTP payloads, vendor-native delivery where available, and a local library of legitimately downloaded archives/installers for other services. A successful HTTPS download through LANCache is passthrough, not a cache HIT. Gameplay, cloud gaming streams, account login, payments and multiplayer servers are outside the content-cache scope.

## What the router investigation establishes

An authenticated OPNsense session and existing Insight/NetFlow collection were available. A filtered NAS flow query showed large HTTPS destination flows around the prior 20XX download. Those support the earlier staging SNI log observations; daily NAS totals also include unrelated applications and cannot all be attributed to Epic.

Five hostnames observed in that download were resolved again from the NAS and actively probed using valid-origin-TLS HEAD requests: `download.epicgames.com`, `egdownload.fastly-edge.com`, `egs-cloudfront-chunks.epicgamescdn.com`, `cdn1.epicgames.com`, and `epicgames-download1.akamaized.net`. All were in the reviewed Epic domain list. DNS aliases and edge addresses changed; several answer TTLs were only seconds. The exact private flow records and time-stamped IP answers are retained outside Git.

A bounded PC observation also collected Epic process-tree TCP sockets and Epic-related DNS cache metadata. It observed existing TLS connections but started no new game download. Therefore this investigation does **not** yet provide a synchronized router/PC/cache capture of a second bulk game download, nor does it establish that every possible Epic content endpoint is covered. Historical flow correlation and current endpoint probes are useful evidence, with different limits.

OPNsense provides [flow history and export](https://docs.opnsense.org/manual/how-tos/insight.html) and [filtered packet diagnostics](https://docs.opnsense.org/manual/diagnostics_interfaces.html). Its [NetFlow documentation](https://docs.opnsense.org/manual/netflow.html) warns that collecting ingress and egress can count translated traffic twice. Compare a consistent observation interface rather than summing LAN and WAN totals.

## Required route-discovery workflow

1. Give each run an ID. Record launcher/version, selected title/build, local time and UTC, test device, VPN state, route/interface and whether the service uses direct DNS or the staging profile. Capture a short idle baseline first.
2. Start a bounded observation before the controlled download. On Windows, attribute TCP connections to the launcher and its download-service children. Collect destination IP/port, timestamp and bytes where the collector supports them. The current prototype observes TCP sockets and DNS only; it cannot measure per-flow bytes or identify remote UDP peers. Add an appropriate flow collector for QUIC/UDP 443.
3. On OPNsense, filter to the test PC and NAS, use the appropriate LAN/VLAN and correlate WAN translation. A same-subnet PC-to-NAS transfer may never cross the router. When Mullvad or Tailscale encapsulates traffic, the physical router may show VPN/relay endpoints rather than Epic's inner destination. Observe the client virtual interface or cache egress too. Do not label a VPN exit or DERP relay as a game CDN.
4. Record DNS CNAME chains, A/AAAA answers, resolver and TTL at the time of the transfer. A DNS cache snapshot is incomplete when an app uses its own resolver or encrypted DNS. Add an optional metadata-only staging stream format containing SNI, upstream address/port, connection times and byte counters; the current stream log does not contain the selected upstream IP.
5. Correlate process, timestamp, DNS, SNI where visible, origin TLS validation, and byte volume. Missing SNI under ECH/QUIC is an observation limit, not permission to guess a hostname. Router reverse DNS and address ownership alone do not prove an endpoint's purpose.
6. Classify each endpoint as content, metadata, login, telemetry, launcher update or external host. Review only demonstrated content hostnames for routing. Never redirect a whole shared CDN suffix, cloud provider address range or publisher's account domain. Do not hard-code observed edge IPs into permanent support rules.
7. Repeat the same content request and measure actual cached payload bytes/HITs, origin bytes avoided and file integrity. A heartbeat, HEAD response, TLS stream byte count or successful install is insufficient. Test updates and range/resume separately. Keep URLs with credentials/query tokens and raw packet data outside public reports.

Deliverable for each run: a redacted endpoint map with observation time/TTL, process, hostname, IP/port/protocol, role, confidence, transferred bytes, caching mechanism and acceptance result. Mark unresolved mappings explicitly. The next Epic run must close the synchronized bulk-capture gap above.

## Shared implementation requirements

| Area | Requirement |
| --- | --- |
| Storage | Keep the existing parent hard quota. Give each staging cache/archive area a bounded child quota. Reserve space for partial downloads, logs and manifests. Do not allocate every service the full parent capacity. |
| Identity | Record service, title/mod ID, file/build ID, OS, architecture, language, DLC/variant and SHA-256. Do not use an expiring signed URL as permanent content identity. |
| Authorization | Keep account/session secrets in a local protected credential store. Obtain fresh provider download authorization when needed. Separate restricted archives by authorized user and validate access before reuse. No credentials or signed URLs in Git or diagnostic summaries. |
| Networking | Preserve the working Tailscale host route and service-specific DNS transport. Retain the current Mullvad configuration while measuring. Test separate Mullvad desktop-app on/off states; do not assume Tailscale's Mullvad exit-node product is the same setup. |
| DNS | Exact content rules only; preserve ordinary DNS, MagicDNS and unselected services. Match client domain snapshot to the staged server configuration. Test A, AAAA, aliases, TTL expiry and negative-answer recovery. |
| Health/recovery | Evaluate route, service DNS, heartbeat and origin TLS. Implement owned-rule bypass and recovery with hysteresis, state persistence and atomic updates. Bypass must preserve Mullvad's DNS and kill-switch policy, not leak traffic outside it. Cache/peer offline and VPN transitions must not strand service DNS. |
| Updates | Pin and verify runtime downloads/images, keep schema migrations and rollback, and retest a launcher release when its delivery behavior changes. |
| Evidence | Report HTTP HIT bytes separately from TLS passthrough. For archive reuse, verify identical file hashes and reduced WAN bytes. Account isolation, update correctness and uninstall restoration are release gates. |

## Requirements by service

### Steam — retain the baseline

- The [140 reinstall test](validation/steam-140.md) verified all 126 repeated game-chunk requests as cache HITs with Mullvad connected, with matching installed-file hashes. Scope this result to the tested build; VPN-off content, remote-network and outage acceptance remain separate.
- Keep the current narrow Steam discovery rules, cache route and existing parent quota; no new service changes the live Steam baseline.
- Record a cold and repeated same-build download with cache log HIT bytes, file validation and WAN reduction. Test updates, resume and Steam Deck as separate client cases.
- Keep native Steam local transfers distinct from LANCache. Valve requires online clients with allowed transfer settings and direct LAN connectivity; native discovery/transfer uses UDP 27031–27036 and TCP 27040. It excludes Workshop, cloud-save and shader data. Tailscale connectivity alone does not establish that native discovery works. See [Valve's transfer requirements](https://help.steampowered.com/en/faqs/view/46BD-6BA8-B012-CE43).
- Remaining gates: remote-network throughput, reboot persistence, cache outage and automated recovery.

### Epic — verify routes, then choose a workable delivery method

- Use the [five observed hosts and measured preview result](validation/epic-preview-0.120.md) as the initial evidence set; compare against the [upstream content list](https://raw.githubusercontent.com/uklans/cache-domains/master/epicgames.txt). Capture additional hosts reached by the controlled download rather than expanding to all Epic/CloudFront/Akamai traffic.
- Run synchronized PC/router/cache observation for the same 20XX build, first direct and then staged, with Mullvad on and off. Do not overwrite the existing install or saves to create a test.
- Record which connections carry bulk chunks, including TCP/UDP, aliases, signed-link refresh, range/resume and integrity. Test a materially different game/update before claiming publisher-wide support.
- Preview 0.120.0 completed a download but populated zero HTTP game payload in the existing lab. [LANCache cannot cache its encrypted passthrough](https://lancache.net/docs/faq/#but-what-about-https-can-i-cache-https); [upstream issue 226](https://github.com/lancachenet/monolithic/issues/226) reports HTTPS behavior changes. Different IPs alone cannot make encrypted payloads cacheable.
- Requirement before promotion: an observed cacheable payload path, a supported publisher mechanism, or a separately validated local-library workflow. Do not make certificate interception or forced downgrade part of the base implementation. Until then, Epic stays direct outside bounded trials.

### EA app — new observation, not inherited Origin support

- Obtain a current signed-in EA client and a small owned test title; include its download/background service in process attribution.
- Treat the existing [three-host Origin list](https://raw.githubusercontent.com/uklans/cache-domains/master/origin.txt) as candidates. Its existence does not verify modern EA app or every EA title.
- Discover payload hosts/protocol, distinguish login/entitlement and game traffic, and test full install, update, pause/resume and repair. EA documents its [installation/recovery flows](https://help.ea.com/en/articles/orders-and-rewards/ea-app-game-download-installation-loading-not-working/), not a universal NAS cache interface.
- Promote transparent caching only after repeated same-build HIT evidence. If payloads are HTTPS, evaluate a supported local-file restore/repair workflow and document per-title limits.

### Microsoft Store / PC Game Pass — evaluate Delivery Optimization first

- Separate Windows PC content from Xbox console downloads and from a game's own updater. Start with a licensed, installed Xbox/Store client and a small entitled title.
- Inspect Delivery Optimization policy and per-download peer/cache/CDN counters before adding DNS rules. Record Gaming Services/download-worker attribution as well as the Xbox UI process.
- Microsoft currently lists PC Game Pass content over HTTP under Xbox endpoints, with console support separately described as future work in its [current endpoint matrix](https://learn.microsoft.com/en-us/windows/deployment/do/delivery-optimization-endpoints). Verify the chosen product and client instead of relying on older FAQ claims.
- For Microsoft Connected Cache Enterprise/Education, check eligibility first: Azure subscription, qualifying client licensing, supported host OS, at least 4 GB free RAM and 100 GB free disk, and required ports. A supported Linux VM is a separate design; do not assume a TrueNAS custom container is a supported MCC host. See [MCC prerequisites](https://learn.microsoft.com/en-us/windows/deployment/do/mcc-ent-prerequisites).
- On this small NAS, resources and storage budgeting must pass before adding a node. Native DO peering is an alternative to assess; automatic discovery/grouping over a VPN is not assumed. See [DO configuration](https://learn.microsoft.com/en-us/windows/deployment/do/delivery-optimization-configure).

### Windows / Microsoft updates — separate policy and control traffic

- Keep this opt-in independent of Game Pass. Test an update or Store package with known identity and compare DO cache/peer/CDN counters and downloaded bytes.
- Audit the bundled wildcard profile before any pilot. In particular, Microsoft lists `*.do.dsp.mp.microsoft.com` as HTTPS control/service traffic with certificate pinning. It should remain direct rather than being treated as a blanket content-cache namespace. Other shared CDN wildcards also need review.
- Prefer documented DO/MCC policy for supported content. Verify fallback, update signatures, reboot behavior, client edition and managed-policy precedence. See [Microsoft's endpoint distinctions](https://learn.microsoft.com/en-us/windows/deployment/do/delivery-optimization-endpoints) and [DO reference](https://learn.microsoft.com/en-us/windows/deployment/do/waas-delivery-optimization-reference).

### GOG — prioritize an offline-installer library

- GOG explicitly provides [offline installers](https://docs.gog.com/offline-installers/). Acquire them from the user's authorized library; keep all parts, patches and optional extras grouped by product/version/platform/language.
- Import once, hash and catalog locally, then prove an install from the NAS and a repeat with no payload redownload. Keep credentials and download-link renewal separate from the archive index.
- Test multipart integrity, interrupted transfer, patch chains and coexistence with Galaxy. Galaxy CDN caching is a separate unverified experiment; offline-installer reuse does not imply transparent Galaxy support.

### Amazon Games — identify the actual delivery platform

- Scope the Windows Amazon Games app and an owned/claimed title. Amazon's [current app instructions](https://digprjsurvey.amazon.co.uk/csad/help/node/TQ1wROUN7BTxoTBbAk) describe that client. A game redeemed into Epic/GOG/Steam must use that platform's connector; streaming is outside this project.
- Observe library/login versus game payload routes and manifests. No supported public download/cache API was established in this research, so do not promise an unattended connector.
- Requirements: entitlement-preserving download authorization, stable title/build identifiers, validated file import/restore and update handling. Keep direct downloads until one of these paths is proven on a real title.

### Nexus Mods — archive reuse with an authorized download adapter

- The [selected manual-download pilot](validation/nexus-manual-download.md) completed first/repeated HTTPS transfers through Tailscale with Mullvad connected and disconnected, with matching archive hashes. It produced no HTTP payload/HITs; transparent caching remains unvalidated and Nexus stays research-only. No system-wide Nexus DNS profile was enabled.
- Track game/mod/file IDs and version, checksum, dependencies and mod-manager metadata. Integrate with Vortex/MO2 download folders rather than treating authenticated web pages as cache payloads.
- Nexus's [official API client](https://github.com/Nexus-Mods/node-nexus-api/blob/master/docs/classes/_nexus_.nexus.md) distinguishes Premium-generated links from website-generated keys for other users. Preserve that distinction; obtain new links when they expire and obey returned limits/backoff. See [API rate-limit guidance](https://help.nexusmods.com/article/105-i-have-reached-a-daily-or-hourly-limit-api-requests-have-been-consumed-rate-limit-exceeded-what-does-this-mean).
- Use the stable API where suitable; [GraphQL v2 is still marked in development](https://graphql.nexusmods.com/). Do not assume an unrestricted production OAuth path.
- Test free/manual and Premium flows separately, plus interrupted download and fresh-link resume. Nexus documents [expiring-link recovery](https://help.nexusmods.com/article/170-resumable-downloads). Verify cached archives can be reused without mixing account-specific authorization.

### LoversLab — manual authorized import first

- Obtain a user-selected file through its normal signed-in flow; store site file/version identity, archive hash, dependencies and source-page reference. Treat external author mirrors as distinct origins.
- Do not promise a maintained official API: none was verified here. Wabbajack's own [integration documentation](https://wiki.wabbajack.org/modlist_author_documentation/Meta%20Files.html#manualurl) recommends a manual URL workflow for LoversLab and describes its automated integration limits.
- Start with local import/deduplication and mod-manager consumption. A future download adapter requires verified current authentication, redirects, link expiry, rate limits and reliable error handling. No broad DNS interception is enabled.

### Mod DB — new target; mirror-aware archive library

- Interpret the requested “mod.db” as Mod DB at `moddb.com`; it is distinct from mod.io.
- Begin with a user-selected public mod archive. Record mod/file identity, version, final mirror hostname, redirect chain, length, ETag/Last-Modified when supplied, and SHA-256.
- Resolve the current mirror at download time, support range/resume where the mirror permits it, and retry without confusing HTML/error pages with archives. Reuse by validated file identity/hash, not temporary mirror URL.
- Wabbajack documents [Mod DB direct-file support](https://wiki.wabbajack.org/modlist_author_documentation/Meta%20Files.html#reference-table). A current official general download API was not established; do not equate forum discussions or mod.io APIs with a supported Mod DB API.
- Verify one public file and one different mirror/update case before advertising support. Check each file's permissions/attribution metadata and the site's [published terms](https://www.moddb.com/terms-of-use) before designing any shared redistribution feature. Transparent HTTP caching remains unverified.

### itch.io — new target; supported butlerd integration

- Prefer the documented [butlerd launcher integration](https://itch.io/docs/butler/launcher-integration.html) for library/install operations. Pin a compatible butler version; bind its interface locally and protect its database because it contains login and installation state.
- Map game/upload/build IDs, channels, OS/architecture and install receipts. Maintain an explicit local storage layer; butlerd integration alone does not make official itch clients consume a NAS cache.
- Use authorized account/library access. The [server-side API](https://itch.io/docs/api/serverside) documents bearer authentication and scopes; personal API keys may be unscoped, so do not bake them into an installer. The signed-in browser remains the initial manual path when no adapter is ready.
- Test a freely downloadable archive, a purchased/owned title where available, build update/delta, interrupted resume and reinstall from the local store. Creator-hosted external links and browser games require separate origin-specific assessment. See [itch install locations](https://itch.io/docs/itch/using/install-locations.html).

## Development order and release gates

1. **Observability and recovery:** synchronized Epic bulk capture, metadata schema, TCP/UDP coverage, upstream-IP stream metadata, per-service DNS bypass/recovery and rollback. Preserve the current Steam baseline.
2. **Archive foundation:** versioned/hash-verified storage, quotas, partial-download handling, authorized local serving and user isolation. Pilot GOG offline installers and a public Mod DB archive; then itch.io's supported integration.
3. **Independent publisher pilots:** current EA app, PC Game Pass and updates/DO. Resource/license-gate MCC separately. Keep legacy candidate lists disabled until role/protocol review.
4. **Authenticated adapters:** Nexus's supported flows, LoversLab manual import, then Amazon/Epic local-library paths only where restore/update behavior is demonstrated.

Each pilot needs a chosen owned/public test item and current client version. Acceptance includes login/catalog remaining normal, correct content identity, warm reuse evidence appropriate to its mechanism, integrity, updates/resume, VPN-on/off, remote Tailscale, reboot, peer/server outage, no accidental VPN bypass, and clean uninstall. Scope an acceptance result to the tested client/title/build. No new profile is production-ready merely because it appears in the catalog or this plan.

