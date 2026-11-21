import json
import unittest
from server import generate


class ComposeTests(unittest.TestCase):
    def args(self, **changes):
        args = generate.parser().parse_args(['--cache-ip', '192.168.50.10', '--subnet', '192.168.50.0/24',
            '--gateway', '192.168.50.1', '--interface', 'eth0', '--dataset', '/mnt/POOL/lancache',
            '--tailnet-suffix', 'example-tailnet.ts.net'])
        for name, value in changes.items():
            setattr(args, name, value)
        return args

    def test_transport_and_least_route(self):
        doc = generate.build(self.args())
        services = doc['services']
        self.assertEqual(len(services), 4)
        self.assertIn('--advertise-routes=192.168.50.10/32', services['tailscale']['environment']['TS_EXTRA_ARGS'])
        self.assertIn('--upstream=[/example-tailnet.ts.net/]100.100.100.100:53', services['dns-transport']['command'])
        self.assertEqual(services['dns']['environment']['USE_GENERIC_CACHE'], 'false')
        self.assertNotIn('TS_AUTHKEY', json.dumps(doc))
        self.assertNotIn('ports', services['cache'])
        self.assertEqual(json.loads(json.dumps(doc)), doc)

    def test_rejects_unsafe_inputs(self):
        cases = [dict(cache_ip='100.64.0.1'), dict(cache_ip='8.8.8.8'), dict(cache_ip='127.0.0.1'),
            dict(cache_ip='192.168.51.10'), dict(cache_ip='192.168.50.1'), dict(cache_ip='192.168.50.0'),
            dict(gateway='192.168.50.255'), dict(quota_gb=480), dict(cache_gib=0),
            dict(tailnet_suffix='bad/\nvalue'), dict(dataset='/mnt/../etc'), dict(interface='eth0\ninvalid')]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValueError):
                generate.build(self.args(**change))

    def test_all_rfc1918_ranges(self):
        for ip, subnet, gateway in [('10.20.0.10', '10.20.0.0/24', '10.20.0.1'),
                                   ('172.20.0.10', '172.20.0.0/24', '172.20.0.1')]:
            self.assertTrue(generate.build(self.args(cache_ip=ip, subnet=subnet, gateway=gateway)))

    def test_experimental_services_are_explicit_and_scoped(self):
        with self.assertRaises(ValueError):
            generate.build(self.args(services='steam,epic'))
        doc = generate.build(self.args(services='steam,epic,ea,microsoft-xbox', allow_experimental=True))
        env = doc['services']['dns']['environment']
        self.assertEqual(env['EPICGAMESCACHE_IP'], '192.168.50.10')
        self.assertEqual(env['ORIGINCACHE_IP'], '192.168.50.10')
        self.assertEqual(env['XBOXLIVECACHE_IP'], '192.168.50.10')
        self.assertNotIn('WSUSCACHE_IP', env)
        self.assertNotIn('LANCACHE_IP', env)
        self.assertEqual(doc['services']['cache']['environment']['CACHE_DISK_SIZE'], '450g')

    def test_isolated_bridge_staging(self):
        doc = generate.build(self.args(cache_ip='172.28.80.10', subnet='172.28.80.0/24',
            gateway='172.28.80.1', network_driver='bridge', interface=None,
            hostname='epic-lancache-stage', cache_gib=4, quota_gb=16,
            services='steam,epic', allow_experimental=True))
        self.assertEqual(doc['networks']['cache_lan']['driver'], 'bridge')
        self.assertNotIn('driver_opts', doc['networks']['cache_lan'])
        self.assertNotIn('ports', doc['services']['cache'])
        self.assertEqual(doc['services']['tailscale']['environment']['TS_HOSTNAME'], 'epic-lancache-stage')
        self.assertIn('--advertise-routes=172.28.80.10/32', doc['services']['tailscale']['environment']['TS_EXTRA_ARGS'])

    def test_ipvlan_requires_interface_and_hostname_is_validated(self):
        for changes in (dict(interface=None), dict(hostname='bad name'), dict(hostname='x' * 64)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                generate.build(self.args(**changes))


if __name__ == '__main__':
    unittest.main()
