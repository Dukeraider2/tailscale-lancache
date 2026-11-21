import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('generate', Path(__file__).resolve().parents[1] / 'server/generate.py')
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)


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


if __name__ == '__main__':
    unittest.main()
