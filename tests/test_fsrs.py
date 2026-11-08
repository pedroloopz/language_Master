"""O FSRS-6 do app (app/index.html) bate com o ts-fsrs (open-spaced-repetition). Precisa de `npm i ts-fsrs`."""
import pathlib
import shutil
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not shutil.which("node") or not (RAIZ / "node_modules" / "ts-fsrs").exists(),
                    reason="sem node ou sem ts-fsrs (npm i ts-fsrs)")
def test_fsrs_igual_ao_ts_fsrs():
    r = subprocess.run(["node", "tests/fsrs_ts.js", "app/index.html"], cwd=RAIZ, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
