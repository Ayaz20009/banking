"""Run a .sql file statement by statement on the SQL warehouse (splits on ';' at line end).
Usage: python3 -I tools/run_sql_file.py <file.sql> [--profile <p>]"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sql  # noqa: E402

path = sys.argv[1]
if "--profile" in sys.argv:
    sql.PROFILE = sys.argv[sys.argv.index("--profile") + 1]
text = "\n".join(l for l in open(path).read().splitlines() if not l.strip().startswith("--"))
stmts = [s.strip() for s in re.split(r";\s*\n", text + "\n") if s.strip()]
for i, s in enumerate(stmts, 1):
    head = " ".join(s.split())[:90]
    try:
        cols, rows = sql.run(s)
        print(f"[{i}/{len(stmts)}] OK   {head}")
    except SystemExit as e:
        print(f"[{i}/{len(stmts)}] FAIL {head}\n{str(e)[:600]}")
        sys.exit(1)
