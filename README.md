# C/C++ use-after-free CFG mapper

Generate a real, per-function control-flow graph using GCC, highlight allocation
and deallocation blocks, and report path-sensitive memory diagnostics, including
uses after `free`/`delete`, aliases, conditional frees, and double frees when GCC
can detect them. Python uses only the standard library.

Requires Python 3.8+ and GCC/G++ with `-fanalyzer` and JSON diagnostic support
(tested with GCC 13). Graphviz is optional for SVG rendering.

```bash
python3 uaf_mapper.py examples/use_after_free.cpp -o uaf-report
python3 uaf_mapper.py test.cpp -o uaf-report -- -std=c++20 -Iinclude
python3 uaf_mapper.py examples/use_after_free.cpp -o uaf-report --svg
python3 uaf_mapper.py examples/use_after_free.cpp --fail-on-bug
```

Mapper options go before `--`; compiler options go after it. Analyze one
translation unit at a time, supplying its usual include paths, defines, and
language flags. Run from the directory relative include paths are based on.
Use `--compiler /path/to/g++` to choose a GCC installation. Compilation never
links or runs the input program.

Outputs:

- `cfg.dot`: compiler CFG, clustered by function, retaining branches and loops.
  Green blocks allocate, red blocks deallocate, yellow blocks do both. Labels
  contain GCC's intermediate representation, including pointer assignments,
  dereferences and call arguments. `new[]`/`delete[]` lower to operator calls.
- `report.json`: source, compiler version, annotated memory block inventory,
  and GCC diagnostics with source positions and ordered diagnostic path events.
  Paths identify allocation, branch decisions, freeing, and invalid use where
  GCC supplies those events. Other analyzer findings are preserved too.
- `cfg.svg` with `--svg`: viewable graph rendered by Graphviz.

Diagnostics and their path events are also printed in the terminal. Exit codes
are 0 on successful analysis, 1 for detected UAF/double-free when `--fail-on-bug`
is enabled, and 2 for compilation/tool errors. An empty diagnostics list is not
proof of memory safety.

The graph represents basic-block control flow, not an explicit allocation-to-free
edge for every object. Object lifetime and alias reasoning come from GCC's
analyzer, and the diagnostic paths are recorded separately. Analysis is bounded
and depends on GCC's version, library models, and available function bodies;
custom allocators, complex C++, indirect calls, concurrency, and cross-translation
unit behavior can be missed. This tool does not implement whole-project analysis.
Only analyze trusted build inputs and compiler flags.

Run the integration tests:

```bash
python3 -m unittest discover -s tests -v
```
