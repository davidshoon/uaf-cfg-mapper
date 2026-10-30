import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('gcc') and shutil.which('g++'), 'requires GCC and G++')
class MapperTests(unittest.TestCase):
    def analyze(self, code, suffix, flags=()):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / ('sample' + suffix)
            source.write_text(code)
            output = Path(directory) / 'report'
            result = subprocess.run([sys.executable, str(ROOT / 'uaf_mapper.py'),
                                     str(source), '-o', str(output), '--fail-on-bug', *flags],
                                    capture_output=True, text=True)
            report = json.loads((output / 'report.json').read_text())
            dot = (output / 'cfg.dot').read_text() if report['graphs'] else ''
            return result, report, dot

    def test_branch_alias_and_cpp_delete(self):
        result, report, dot = self.analyze((ROOT / 'examples/use_after_free.cpp').read_text(), '.cpp', ('--', '-std=c++17'))
        self.assertEqual(result.returncode, 1, result.stderr)
        bugs = [d for d in report['diagnostics'] if d.get('option') == '-Wanalyzer-use-after-free']
        self.assertGreaterEqual(len(bugs), 2)
        self.assertTrue(all(d.get('path') for d in bugs))
        self.assertIn('#dcfce7', dot)
        self.assertIn('#fee2e2', dot)
        self.assertTrue(any('allocation' in b['kinds'] for b in report['memory_blocks']))
        self.assertIn(' -> ', dot)

    def test_safe_c(self):
        result, report, _ = self.analyze('#include <stdlib.h>\nint f(void) { int *p=malloc(sizeof *p); if(!p)return 0; *p=7; int n=*p; free(p); return n; }', '.c')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(report['diagnostics'])

    def test_double_free(self):
        result, report, _ = self.analyze('#include <stdlib.h>\nvoid f(void) { void *p=malloc(4); free(p); free(p); }', '.c')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue(any(d.get('option') == '-Wanalyzer-double-free' for d in report['diagnostics']))

    def test_invalid_source(self):
        result, report, _ = self.analyze('this is invalid C!', '.c')
        self.assertEqual(result.returncode, 2)
        self.assertNotEqual(report['compiler_exit_code'], 0)


if __name__ == '__main__':
    unittest.main()
