#!/usr/bin/env python3
"""
Read in schema for webform fields and save to python object.
"""

import argparse
import json


def load_schema(self):
    if self.schema_path.startswith("http://") or self.schema_path.startswith(
        "https://"
    ):
        import urllib.request

        with urllib.request.urlopen(self.schema_path) as f:
            self.schema = json.load(f)
    else:
        with open(self.schema_path) as f:
            self.schema = json.load(f)
    return self.schema


# -----------------------------
# Main class
# -----------------------------


class SchemaPopulator:
    def __init__(self, schema_path=None):
        self.schema_path = schema_path

    def load_schema(self):
        with open(self.schema_path) as f:
            self.schema = json.load(f)
            return self.schema


# -----------------------------
# Entry point
# -----------------------------


def parse_args():
    parser = argparse.ArgumentParser(description="Read in webform schema")

    # Required arguments
    parser.add_argument("schema", help="Path to schema JSON file")

    # Optional file arguments
    parser.add_argument("--output", "-o", help="Output file path")

    return parser.parse_args()


def main():
    args = parse_args()

    populator = SchemaPopulator(
        schema_path=args.schema,
    )

    result = populator.load_schema()

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
