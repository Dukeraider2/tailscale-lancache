import contextlib
import io
import json
from unittest import mock
import unittest
from server import stage_truenas as stage


class StageTests(unittest.TestCase):
    def args(self):
        return stage.parser().parse_args(['--parent-dataset','POOL/lancache',
            '--tailnet-suffix','example-tailnet.ts.net'])

    def test_small_isolated_config(self):
        dataset, compose, plan = stage.make_config('POOL/lancache', 'example-tailnet.ts.net',
            '172.28.80.10', '172.28.80.0/24', '172.28.80.1')
        self.assertEqual(dataset, 'POOL/lancache/stage-epic')
        self.assertEqual(compose['services']['cache']['environment']['CACHE_DISK_SIZE'], '4g')
        self.assertEqual(compose['services']['cache']['mem_limit'], '768m')
        self.assertEqual(compose['networks']['cache_lan']['driver'], 'bridge')
        self.assertEqual(plan['Services'], ['epic', 'steam'])

    def test_dataset_path_validation(self):
        for parent in ('POOL', '../POOL', 'POOL/../other', '/mnt/POOL/cache', 'POOL/cache;bad'):
            with self.subTest(parent=parent), self.assertRaises(ValueError):
                stage.make_config(parent, 'example-tailnet.ts.net', '172.28.80.10', '172.28.80.0/24', '172.28.80.1')

    def test_overlap_in_docker_and_host_routes(self):
        stage.check_overlap('172.28.80.0/24', [], [{'dst':'default'}, {'dst':'192.168.50.0/24'}])
        with self.assertRaises(ValueError):
            stage.check_overlap('172.28.80.0/24', [{'IPAM':{'Config':[{'Subnet':'172.28.0.0/16'}]}}], [])
        with self.assertRaises(ValueError):
            stage.check_overlap('172.28.80.0/24', [], [{'dst':'172.28.80.10/32'}])

    def test_size_properties_fail_closed(self):
        self.assertEqual(stage.size_property({'rawvalue':'16000000000'}), stage.QUOTA)
        self.assertEqual(stage.size_property({'parsed':stage.QUOTA}), stage.QUOTA)
        with self.assertRaises(ValueError):
            stage.size_property({'value':'unknown'})

    def test_default_check_does_not_mutate(self):
        args = self.args()
        calls = []
        def api(method, *values, **kwargs):
            calls.append(method)
            if method == 'pool.dataset.query' and values[0][0][2] == 'POOL/lancache':
                return [{'mountpoint':'/mnt/POOL/lancache', 'quota':{'rawvalue':'549755813888'},
                    'available':{'rawvalue':'500000000000'}}]
            if method in ('pool.dataset.query','app.query'):
                return []
            raise AssertionError('Unexpected mutation: ' + method)
        def command(command):
            if command == ['docker','network','ls','-q']:
                return ''
            if command == ['ip','-j','-4','route','show','table','all']:
                return '[]'
            raise AssertionError('Unexpected command: ' + str(command))
        with mock.patch.object(stage, 'midclt', side_effect=api), mock.patch.object(stage, 'run', side_effect=command), \
             mock.patch.object(stage.Path, 'exists', lambda self: self.as_posix() == '/dev/net/tun'), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            stage.install(args)
        self.assertEqual(json.loads(output.getvalue())['mode'], 'CHECK ONLY')
        self.assertNotIn('pool.dataset.create', calls)
        self.assertNotIn('app.create', calls)

    def test_existing_staging_dataset_is_not_reused(self):
        parent = {'mountpoint':'/mnt/POOL/lancache','quota':{'rawvalue':'549755813888'},
            'available':{'rawvalue':'500000000000'}}
        with mock.patch.object(stage, 'midclt', side_effect=[[parent],[{'id':'POOL/lancache/stage-epic'}]]) as api, \
             self.assertRaises(ValueError):
            stage.install(self.args())
        self.assertEqual(api.call_count, 2)


if __name__ == '__main__':
    unittest.main()
