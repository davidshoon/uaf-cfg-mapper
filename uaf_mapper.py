#!/usr/bin/env python3
"""Generate GCC CFGs and path-sensitive memory diagnostics for C/C++."""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ALLOC = re.compile(r'\b(?:malloc|calloc|realloc|aligned_alloc|strdup|strndup)\s*\(|operator new\b|\b_Zna?[wm]\b')
FREE = re.compile(r'\b(?:free)\s*\(|operator delete\b|\b_Zd[al]\b')


def decorate(dot):
    """Color actual basic-block labels, retaining GCC's edges and clusters."""
    inventory = []
    pattern = re.compile(r'(?P<id>\b\w+)\s*\[(?P<attrs>[^\]]*label="(?P<label>(?:\\.|[^"\\])*)"[^\]]*)\];', re.S)

    def block(match):
        label = match['label'].replace('\\ ', ' ').replace('\\\n', '')
        kinds = []
        if ALLOC.search(label):
            kinds.append('allocation')
        if FREE.search(label):
            kinds.append('deallocation')
        if not kinds:
            return match.group(0)
        inventory.append({'node': match['id'], 'kinds': kinds, 'gcc_label': label})
        color = '#fef3c7' if len(kinds) == 2 else ('#dcfce7' if kinds == ['allocation'] else '#fee2e2')
        attrs = re.sub(r'fillcolor=(?:"[^"]*"|[^,\s]+)', 'fillcolor="' + color + '"', match['attrs'])
        if 'fillcolor=' not in attrs:
            attrs += ', fillcolor="' + color + '"'
        if 'style=' not in attrs:
            attrs += ', style="filled"'
        return match['id'] + ' [' + attrs + '];'

    return pattern.sub(block, dot), inventory


def run(args):
    source = Path(args.source).resolve()
    if not source.is_file():
        raise ValueError('Source file does not exist: ' + str(source))
    cpp = source.suffix.lower() not in ('.c', '.i')
    compiler = args.compiler or ('g++' if cpp else 'gcc')
    if not shutil.which(compiler):
        raise ValueError('Compiler not found: ' + compiler)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='uaf-mapper-') as tmp:
        command = [compiler, '-O0', '-g', '-fanalyzer', '-Wanalyzer-use-after-free',
                   '-Wanalyzer-double-free', '-fdiagnostics-format=json',
                   '-fdump-tree-cfg-graph', '-c', str(source), '-o', str(Path(tmp) / 'analysis.o')]
        command += args.compiler_args
        result = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout)
        try:
            diagnostics = json.loads(result.stderr or '[]')
        except json.JSONDecodeError:
            raise ValueError('GCC did not return JSON diagnostics:\n' + result.stderr)
        graphs = []
        blocks = []
        for index, dump in enumerate(sorted(Path(tmp).glob('*.dot'))):
            dot, inventory = decorate(dump.read_text())
            name = 'cfg.dot' if index == 0 else f'cfg-{index}.dot'
            (out / name).write_text(dot)
            graphs.append(name)
            blocks.extend(dict(block, graph=name) for block in inventory)
            if args.svg:
                if not shutil.which('dot'):
                    raise ValueError('SVG rendering requires Graphviz (the dot executable). Omit --svg to produce DOT only.')
                subprocess.run(['dot', '-Tsvg', str(out / name), '-o', str(out / name.replace('.dot', '.svg'))], check=True)
        report = {'source': str(source), 'compiler': compiler,
                  'compiler_version': subprocess.run([compiler, '--version'], capture_output=True, text=True).stdout.splitlines()[0],
                  'compiler_exit_code': result.returncode, 'graphs': graphs,
                  'memory_blocks': blocks, 'diagnostics': diagnostics}
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        for diagnostic in diagnostics:
            location = (diagnostic.get('locations') or [{}])[0].get('caret', {})
            where = f"{location.get('file', source)}:{location.get('line', '?')}:{location.get('column', '?')}"
            print(f"{where}: {diagnostic.get('kind', 'warning')}: {diagnostic['message']}")
            for event in diagnostic.get('path', []):
                loc = event.get('location', {})
                print(f"  {loc.get('file', source)}:{loc.get('line', '?')}: {event.get('description', '')}")
        print(f'Report: {out / "report.json"}')
        for graph in graphs:
            print(f'CFG: {out / graph}')
        if result.returncode:
            return 2
        if not graphs:
            raise ValueError('Compiler produced no CFG. Use GCC/G++ with CFG dump and analyzer support.')
        issues = any(d.get('option') in ('-Wanalyzer-use-after-free', '-Wuse-after-free', '-Wanalyzer-double-free') for d in diagnostics)
        return 1 if args.fail_on_bug and issues else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', help='C or C++ translation unit')
    parser.add_argument('-o', '--output', default='uaf-report', help='Output directory')
    parser.add_argument('--compiler', help='GCC-compatible compiler (default: gcc or g++)')
    parser.add_argument('--svg', action='store_true', help='Also render SVG with Graphviz')
    parser.add_argument('--fail-on-bug', action='store_true', help='Exit 1 for UAF or double-free diagnostics')
    parser.add_argument('--timeout', type=int, default=120, help='Compiler timeout in seconds')
    # Separate compiler arguments so mapper options can occur after the source.
    argv = sys.argv[1:]
    extra = []
    if '--' in argv:
        split = argv.index('--')
        argv, extra = argv[:split], argv[split + 1:]
    args = parser.parse_args(argv)
    args.compiler_args = extra
    try:
        return run(args)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
