"""Export the tables of the EA's "Consented Discharges to Controlled Waters with Conditions" (.accdb) to parquet.

    python export_consents.py "<...>.accdb" <out dir>

The file is under the Environment Agency Conditional Licence: internal use only, never published. Keep it and
the exported tables outside the repo (a scratch folder), and pass their folder to make_variants.py. Needs the
access-parser package, which the project does not depend on: run it from a separate environment, e.g.
`uv venv <scratch>/accvenv && uv pip install --python <scratch>/accvenv/bin/python access-parser pandas pyarrow`.
Every column is written as text. Prints table names and shapes only.
"""
import sys
from pathlib import Path

import pandas as pd
from access_parser import AccessParser

TABLES = ("consents_active", "Effluents", "Determinands")

db = AccessParser(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
for n in TABLES:
    t = db.parse_table(n)
    df = pd.DataFrame({k: pd.Series(v, dtype="object").astype("string") for k, v in t.items()})
    df.to_parquet(out / f"{n}.parquet", index=False)
    print(n, df.shape)
