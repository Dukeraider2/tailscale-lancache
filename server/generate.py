"""Render a Docker Compose document without dependencies or stored credentials."""
import argparse
import ipaddress
import json
from pathlib import Path
import re
try:
    from .profiles import build_plan, select_services
except ImportError:
    from profiles import build_plan, select_services


def build(args):
    selected = select_services(args.services, args.allow_experimental)
    address = ipaddress.IPv4Address(args.cache_ip)
    network = ipaddress.IPv4Network(args.subnet, strict=True)
    gateway = ipaddress.IPv4Address(args.gateway)
    private = [ipaddress.IPv4Network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
    if not any(address in n and network.subnet_of(n) for n in private):
        raise ValueError('Cache and subnet must use RFC1918 addresses; Tailscale 100.x addresses cannot be used.')
    if address not in network or gateway not in network or address == gateway:
        raise ValueError('Cache and gateway must be distinct addresses in the subnet.')
    if address in (network.network_address, network.broadcast_address) or gateway in (network.network_address, network.broadcast_address):
        raise ValueError('Network and broadcast addresses are not usable hosts.')
    if not re.fullmatch(r'[a-zA-Z0-9_.:-]+', args.interface):
        raise ValueError('Invalid parent interface.')
    if not re.fullmatch(r'[a-z0-9-]+\.ts\.net', args.tailnet_suffix):
        raise ValueError('Enter the actual tailnet MagicDNS suffix, ending in .ts.net.')
    if not re.fullmatch(r'/[a-zA-Z0-9_./-]+', args.dataset) or '..' in args.dataset.split('/'):
        raise ValueError('Dataset must be an absolute path without traversal or whitespace.')
    # nginx g units are binary; reserve room for logs, state, and indexes.
    if args.cache_gib < 1 or args.quota_gb * 10**9 < (args.cache_gib + 10) * 2**30:
        raise ValueError('Quota must exceed cache plus at least 10 GiB; set the dataset quota separately.')
    ip = str(address)
    logging = {'driver': 'json-file', 'options': {'max-size': '10m', 'max-file': '3'}}
    def service(image, memory, **extra):
        return dict(image=image, restart='unless-stopped', mem_limit=memory, logging=logging, **extra)
    shared = {'network_mode': 'service:cache', 'depends_on': ['cache']}
    services = {
        'cache': service('lancachenet/monolithic:latest', '2g', cpus=2,
            environment={'UPSTREAM_DNS': '1.1.1.1 1.0.0.1', 'CACHE_DISK_SIZE': f'{args.cache_gib}g',
                'MIN_FREE_DISK': '10g', 'CACHE_INDEX_SIZE': '128m', 'CACHE_MAX_AGE': '3650d',
                'LOGFILE_RETENTION': '7', 'TZ': 'UTC'},
            volumes=[f'{args.dataset}/cache:/data/cache', f'{args.dataset}/logs:/data/logs'],
            networks={'cache_lan': {'ipv4_address': ip}}),
        'tailscale': service('tailscale/tailscale:stable', '256m', **shared,
            cap_add=['NET_ADMIN'], devices=['/dev/net/tun:/dev/net/tun'],
            environment={'TS_HOSTNAME': 'steam-lancache', 'TS_STATE_DIR': '/var/lib/tailscale',
                'TS_AUTH_ONCE': 'false', 'TS_BOOT_TIMEOUT': '30m', 'TS_USERSPACE': 'false',
                'TS_ACCEPT_DNS': 'false', 'TS_EXTRA_ARGS': f'--accept-dns=false --accept-routes=false --advertise-routes={ip}/32 --netfilter-mode=off'},
            volumes=[f'{args.dataset}/tailscale:/var/lib/tailscale']),
        'dns': service('lancachenet/lancache-dns:latest', '512m', **shared,
            environment={'USE_GENERIC_CACHE': 'false', 'STEAMCACHE_IP': ip,
                'UPSTREAM_DNS': '1.1.1.1 1.0.0.1', 'TZ': 'UTC'}),
        'dns-transport': service('adguard/dnsproxy:v0.86.0', '128m',
            network_mode='service:cache', depends_on=['dns', 'tailscale'],
            command=['--listen=0.0.0.0', '--port=8053', '--upstream=tcp://127.0.0.1:53',
                f'--upstream=[/{args.tailnet_suffix}/]100.100.100.100:53', '--timeout=5s'])}
    plan = build_plan(ip, selected, args.allow_experimental)
    services['dns']['environment'].update(plan['DNSEnvironment'])
    return {'services': services, 'networks': {'cache_lan': {'driver': 'ipvlan',
        'driver_opts': {'parent': args.interface, 'ipvlan_mode': 'l2'},
        'ipam': {'config': [{'subnet': str(network), 'gateway': str(gateway), 'ip_range': f'{ip}/32'}]}}}}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('cache-ip', 'subnet', 'gateway', 'interface', 'dataset', 'tailnet-suffix'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--cache-gib', type=int, default=450)
    p.add_argument('--quota-gb', type=int, default=512)
    p.add_argument('--services', default='steam', help='Comma-separated service IDs; default: steam only.')
    p.add_argument('--allow-experimental', action='store_true', help='Explicitly opt in to unverified service profiles.')
    p.add_argument('--output', type=Path, default=Path('generated/compose.yaml'))
    return p


if __name__ == '__main__':
    p = parser()
    args = p.parse_args()
    try:
        document = build(args)
    except ValueError as error:
        p.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # JSON is valid YAML 1.2 and is accepted by Docker Compose.
    args.output.write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8')
    plan = build_plan(args.cache_ip, select_services(args.services, args.allow_experimental), args.allow_experimental)
    args.output.with_name('client-plan.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {args.output}. Dataset creation, quota, login and route approval are separate steps.')
