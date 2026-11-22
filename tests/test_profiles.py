import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from server.profiles import build_plan, select_services


class ProfileTests(unittest.TestCase):
    def test_steam_default_does_not_redirect_other_services(self):
        plan = build_plan('192.168.50.10', ['steam'])
        self.assertFalse(plan['Experimental'])
        self.assertFalse(plan['RequiresTlsPassthrough'])
        self.assertEqual(len(plan['Namespaces']), 2)
        self.assertEqual(set(plan['DNSEnvironment']), {'STEAMCACHE_IP'})

    def test_opt_in_and_research_gates(self):
        for service in ('epic', 'ea', 'microsoft-xbox', 'microsoft-updates'):
            with self.subTest(service=service), self.assertRaises(ValueError):
                select_services('steam,' + service)
        for service in ('ea', 'gog', 'amazon', 'nexusmods', 'loverslab', 'moddb', 'itchio', 'unknown'):
            with self.subTest(service=service), self.assertRaises(ValueError):
                select_services('steam,' + service, True)
        for empty in ('', 'epic', ',,,'):
            with self.assertRaises(ValueError):
                select_services(empty, True)

    def test_deduplicated_selection(self):
        self.assertEqual(select_services('Steam, epic,steam,EPIC', True), ['epic', 'steam'])

    def test_epic_contains_only_content_hosts(self):
        plan = build_plan('192.168.50.10', ['steam', 'epic'], True)
        self.assertIn('download.epicgames.com', plan['Namespaces'])
        self.assertNotIn('.epicgames.com', plan['Namespaces'])
        self.assertNotIn('accounts.epicgames.com', plan['Namespaces'])
        self.assertNotIn('WSUSCACHE_IP', plan['DNSEnvironment'])
        self.assertEqual(len(plan['DomainRevision']), 40)

    def test_microsoft_update_wildcards_are_separate_opt_in(self):
        xbox = build_plan('192.168.50.10', ['steam', 'microsoft-xbox'], True)
        updates = build_plan('192.168.50.10', ['steam', 'microsoft-updates'], True)
        self.assertNotIn('.windowsupdate.com', xbox['Namespaces'])
        self.assertIn('.windowsupdate.com', updates['Namespaces'])
        self.assertNotIn('.microsoft.com', updates['Namespaces'])
        self.assertIn('WSUSCACHE_IP', updates['DNSEnvironment'])

    def test_invalid_cache_address_rejected(self):
        with self.assertRaises(ValueError):
            build_plan('100.64.0.1', ['steam'])

    def test_cli_writes_matching_server_and_client_plan(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / 'compose.yaml'
            result = subprocess.run([sys.executable, str(root / 'server/generate.py'),
                '--cache-ip', '192.168.50.10', '--subnet', '192.168.50.0/24',
                '--gateway', '192.168.50.1', '--interface', 'eth0', '--dataset', '/mnt/POOL/lancache',
                '--tailnet-suffix', 'example-tailnet.ts.net', '--services', 'steam,epic',
                '--allow-experimental', '--output', str(destination)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            compose = json.loads(destination.read_text())
            plan = json.loads(destination.with_name('client-plan.json').read_text())
            self.assertEqual(plan['CacheIP'], compose['services']['dns']['environment']['EPICGAMESCACHE_IP'])
            self.assertEqual(plan['Services'], ['epic', 'steam'])


if __name__ == '__main__':
    unittest.main()

