# Contributing

Issues and pull requests are welcome, especially:

* results for other models run with `ctb run-team` (please include the transcripts and `ctb audit` output);
* human grading of APEX criteria to calibrate the model judges;
* a container runner for `run.py` (`--network none`) to replace the socket-level block.

Before opening a pull request:

```bash
pip install -e ".[dev]"
make check          # ruff, mypy --strict, pytest
make reproduce      # needs `ctb fetch finbalance`; committed results must not change unless intended
```

Keep scoring changes backwards compatible: `tests/test_scoring.py` checks the scorer against the
one used in the experiments. If a change to the scorer is intended, say so in the pull request and
regenerate `results/`.
