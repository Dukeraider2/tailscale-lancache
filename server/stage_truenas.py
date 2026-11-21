"""Create a separate Epic staging app locally on TrueNAS; inspect by default."""
import argparse
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
try:
    from . import generate
    from .profiles import build_plan
except ImportError:
    import generate
    from profiles import build_plan

APP = 'epic-lancache-stage'
QUOTA = 16_000_000_000


def run(command):
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=600)
    return result.stdout.strip()


def midclt(method, *values, job=False):
    return json.loads(run(['midclt', 'call'] + (['-job'] if job else []) +
        [method] + [json.dumps(value) for value in values]))


def size_property(value):
    if isinstance(value, dict):
        for key in ('rawvalue', 'parsed', 'value'):
            try:
                return int(value[key])
            except (KeyError, TypeError, ValueError):
                pass
    raise ValueError('Cannot determine the dataset byte limit; no changes made.')


def check_overlap(subnet, networks, routes):
    candidate = ipaddress.IPv4Network(subnet)
    occupied = []
    for network in networks:
        # Docker host/none networks legitimately report null IPAM or Config.
        ipam = network.get('IPAM')
        if ipam is None:
            ipam = {}
        if not isinstance(ipam, dict):
            raise ValueError('Unexpected Docker IPAM data; stopped before making changes.')
        entries = ipam.get('Config')
        if entries is None:
            entries = []
        if not isinstance(entries, list):
            raise ValueError('Unexpected Docker subnet configuration; stopped before making changes.')
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError('Unexpected Docker subnet entry; stopped before making changes.')
            if entry.get('Subnet'):
                occupied.append(entry['Subnet'])
    occupied.extend(route['dst'] for route in routes if route.get('dst') not in (None, 'default', '0.0.0.0/0'))
    for prefix in occupied:
        existing = ipaddress.ip_network(prefix, strict=False)
        if existing.version == 4 and candidate.overlaps(existing):
            raise ValueError('The staging subnet overlaps an existing Docker network or host route. Choose another subnet.')


def make_config(parent, suffix, cache_ip, subnet, gateway):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+', parent) or any(p in ('.', '..') for p in parent.split('/')):
        raise ValueError('Name an existing dedicated cache dataset, such as POOL/lancache.')
    dataset = parent + '/stage-epic'
    args = generate.parser().parse_args(['--cache-ip', cache_ip, '--subnet', subnet,
        '--gateway', gateway, '--network-driver', 'bridge', '--hostname', APP,
        '--dataset', '/mnt/' + dataset, '--tailnet-suffix', suffix,
        '--cache-gib', '4', '--quota-gb', '16', '--services', 'steam,epic', '--allow-experimental'])
    compose = generate.build(args)
    # Small test cache on a NAS that may already run several applications.
    compose['services']['cache']['mem_limit'] = '768m'
    compose['services']['cache']['cpus'] = 1
    compose['services']['cache']['environment']['CACHE_INDEX_SIZE'] = '32m'
    compose['services']['dns']['mem_limit'] = '256m'
    plan = build_plan(cache_ip, ['steam', 'epic'], True)
    return dataset, compose, plan


def install(args):
    dataset, compose, plan = make_config(args.parent_dataset, args.tailnet_suffix,
        args.cache_ip, args.subnet, args.gateway)
    parent_rows = midclt('pool.dataset.query', [['id', '=', args.parent_dataset]])
    if len(parent_rows) != 1:
        raise ValueError('Parent dataset does not exist; no changes made.')
    parent = parent_rows[0]
    expected_parent_path = PurePosixPath('/mnt') / args.parent_dataset
    if parent.get('mountpoint') != str(expected_parent_path):
        raise ValueError('Parent mountpoint differs from the expected dataset path; no changes made.')
    if size_property(parent.get('quota')) <= 0 or size_property(parent.get('available')) < QUOTA:
        raise ValueError('The parent needs a hard quota and at least 16 GB available; no changes made.')
    if midclt('pool.dataset.query', [['id', '=', dataset]]):
        raise ValueError('Staging dataset already exists. Inspect it; this script never overwrites existing data.')
    if midclt('app.query', [['id', '=', APP]]):
        raise ValueError('Staging app already exists. Inspect it; this script never updates an existing app.')
    identifiers = run(['docker', 'network', 'ls', '-q']).split()
    networks = json.loads(run(['docker', 'network', 'inspect'] + identifiers)) if identifiers else []
    routes = json.loads(run(['ip', '-j', '-4', 'route', 'show', 'table', 'all']))
    check_overlap(args.subnet, networks, routes)
    if not Path('/dev/net/tun').exists():
        raise ValueError('/dev/net/tun is unavailable; no changes made.')
    target = Path('/mnt') / dataset
    if target.exists():
        raise ValueError('The proposed staging path already exists without a matching dataset; refusing to use it.')
    print(json.dumps({'mode': 'APPLY' if args.apply else 'CHECK ONLY', 'new_app': APP,
        'new_dataset': dataset, 'child_quota_bytes': QUOTA, 'content_cache_gib': 4,
        'cache_ip': args.cache_ip, 'parent_quota_unchanged': True, 'existing_apps_unchanged': True}, indent=2))
    if not args.apply:
        return
    if os.geteuid() != 0:
        raise PermissionError('Run with sudo to apply. No changes made.')
    os.umask(0o077)
    image = compose['services']['cache']['image']
    run(['docker', 'pull', image])
    metadata = json.loads(run(['docker', 'image', 'inspect', image]))[0]
    digest = next((value for value in metadata.get('RepoDigests', [])
        if value.startswith('lancachenet/monolithic@sha256:')), None)
    if not digest:
        raise ValueError('Could not pin the pulled cache image; stopped before dataset creation.')
    ids = run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', '/bin/sh',
        digest, '-c', 'id -u www-data; id -g www-data']).splitlines()
    if len(ids) != 2 or not all(value.isdecimal() for value in ids):
        raise ValueError('Could not determine cache worker ownership; stopped before dataset creation.')
    uid, gid = map(int, ids)
    compose['services']['cache']['image'] = digest
    midclt('pool.dataset.create', {'name': dataset, 'quota': QUOTA})
    # A failed app deployment leaves this new dataset for inspection. Never
    # destroy it automatically or touch a live app during error recovery.
    if target.resolve() != target or not target.is_dir():
        raise ValueError('Created dataset mountpoint is not the expected directory; stopped before app creation.')
    os.chmod(target, 0o700)
    for name in ('cache', 'logs', 'tailscale', 'deployment'):
        (target / name).mkdir(mode=0o700)
        if name in ('cache', 'logs'):
            os.chown(target / name, uid, gid)
    (target / 'deployment/compose.yaml').write_text(json.dumps(compose, indent=2) + '\n', encoding='utf-8')
    (target / 'deployment/client-plan.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    midclt('app.create', {'app_name': APP, 'custom_app': True, 'custom_compose_config': compose}, job=True)
    state = midclt('app.query', [['id', '=', APP]])
    print(json.dumps({'app': APP, 'state': state[0].get('state') if state else 'not returned',
        'next': 'Open the staging app Tailscale logs, authenticate the node, then approve only its cache /32 route.'}))


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent-dataset', required=True)
    p.add_argument('--tailnet-suffix', required=True)
    p.add_argument('--cache-ip', default='172.28.80.10')
    p.add_argument('--subnet', default='172.28.80.0/24')
    p.add_argument('--gateway', default='172.28.80.1')
    p.add_argument('--apply', action='store_true', help='Create only the named staging dataset and app after checks.')
    return p


if __name__ == '__main__':
    p = parser()
    try:
        install(p.parse_args())
    except (ValueError, PermissionError, OSError, subprocess.SubprocessError) as error:
        p.exit(1, f'{error}\n')
