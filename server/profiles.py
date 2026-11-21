"""Explicit service selection; upstream lists are evidence, not cache-HIT proof."""
import argparse
import ipaddress
import json
from pathlib import Path
import re

CATALOG = {
    'steam': {'state': 'baseline', 'environment': 'STEAMCACHE_IP', 'file': None},
    'epic': {'state': 'experimental', 'environment': 'EPICGAMESCACHE_IP', 'file': 'epicgames.txt'},
    'ea': {'state': 'experimental', 'environment': 'ORIGINCACHE_IP', 'file': 'origin.txt'},
    'microsoft-xbox': {'state': 'experimental', 'environment': 'XBOXLIVECACHE_IP', 'file': 'xboxlive.txt'},
    'microsoft-updates': {'state': 'experimental', 'environment': 'WSUSCACHE_IP', 'file': 'windowsupdates.txt'},
    'gog': {'state': 'research', 'reason': 'No profile verified; retain direct downloads.'},
    'amazon': {'state': 'research', 'reason': 'No profile verified; retain direct downloads.'},
    'nexusmods': {'state': 'research', 'reason': 'Upstream hostname exists; cacheable HTTP and authenticated downloads need validation.'},
    'loverslab': {'state': 'research', 'reason': 'Authenticated downloads and cacheability need validation.'},
}
DOMAIN = re.compile(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}')


def select_services(value, allow_experimental=False):
    selected = sorted(set(item.strip().lower() for item in value.split(',') if item.strip()))
    if 'steam' not in selected:
        raise ValueError('The initial v2 milestone requires the Steam baseline.')
    for name in selected:
        if name not in CATALOG:
            raise ValueError(f'Unknown service: {name}')
        profile = CATALOG[name]
        if profile['state'] == 'research':
            raise ValueError(f'{name} is research-only: {profile["reason"]}')
        if profile['state'] == 'experimental' and not allow_experimental:
            raise ValueError(f'{name} requires --allow-experimental and staged VPN-on/off testing.')
    return selected


def build_plan(cache_ip, selected, allow_experimental=False):
    address = ipaddress.IPv4Address(cache_ip)
    if not any(address in ipaddress.IPv4Network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
        raise ValueError('The cache address must use RFC1918 IPv4.')
    selected = select_services(','.join(selected), allow_experimental)
    snapshot = json.loads(Path(__file__).with_name('domains.lock.json').read_text(encoding='utf-8'))
    names = {'lancache.steamcontent.com', 'steam.cache.lancache.net'}
    for name in selected:
        filename = CATALOG[name]['file']
        for domain in snapshot['domains'].get(filename, []) if filename else []:
            wildcard = domain.startswith('*.')
            bare = domain[2:] if wildcard else domain
            if not DOMAIN.fullmatch(bare) or (len(bare.split('.')) < 3 and bare != 'windowsupdate.com'):
                raise ValueError(f'Invalid or overly broad upstream domain in {filename}.')
            # NRPT suffix rules include the apex. Server DNS still applies its own
            # upstream wildcard semantics and resolves an unmatched apex normally.
            names.add('.' + bare if wildcard else bare)
    return {'SchemaVersion': 2, 'CacheIP': str(address), 'Services': selected,
        'Experimental': any(CATALOG[n]['state'] == 'experimental' for n in selected),
        'Namespaces': sorted(names), 'RequiresTlsPassthrough': len(selected) > 1,
        'DomainSource': snapshot['repository'], 'DomainRevision': snapshot['revision'],
        'DNSEnvironment': {CATALOG[n]['environment']: str(address) for n in selected}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Show v2 service states without changing any system.')
    parser.add_argument('--list', action='store_true', required=True)
    parser.parse_args()
    print(json.dumps(CATALOG, indent=2))
