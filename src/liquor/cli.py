import argparse
import json
import sys
from pathlib import Path

from .db import get_engine
from .generate import generate
from .pipeline import ingest
from .schema import initialize


def main():
    parser = argparse.ArgumentParser(description="Synthetic liquor-store batch pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--output", default="data/raw/base")
    gen.add_argument("--days", type=int, default=183)
    gen.add_argument("--seed", type=int, default=42)
    for name in ["init", "load", "export-rejects"]:
        p = sub.add_parser(name)
        p.add_argument("--demo", action="store_true", help="Use local SQLite; ignore MySQL config")
        if name == "load":
            p.add_argument("--input", default="data/raw/base")
        if name == "export-rejects":
            p.add_argument("--output", default="data/rejected/records.csv")
    args = parser.parse_args()
    try:
        if args.command == "generate":
            print(json.dumps(generate(args.output, args.days, args.seed), indent=2))
            return
        engine = get_engine(args.demo)
        if args.command == "init":
            initialize(engine)
            print("Schema ready.")
        elif args.command == "load":
            print(json.dumps(ingest(engine, args.input), indent=2))
        else:
            from .analytics import read_frame

            df = read_frame(engine, "SELECT * FROM raw_records WHERE disposition='rejected'")
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(target, index=False)
            print(f"Exported {len(df)} rejected rows to {target}")
    except Exception as exc:
        print(
            f"{type(exc).__name__}: command failed. Check configuration, CSV contract and pipeline_runs.",
            file=sys.stderr,
        )
        if isinstance(exc, (ValueError, FileNotFoundError)):
            print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
