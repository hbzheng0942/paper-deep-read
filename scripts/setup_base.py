#!/usr/bin/env python3
"""根据 base_schema.json 创建/校验论文阅读记录 Base。"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
   import tomllib
except ModuleNotFoundError:
   import tomli as tomllib


def load_config(path: Path) -> dict[str, Any]:
   with open(path, "rb") as f:
       return tomllib.load(f)


def run_lark_cli(*args: str) -> dict[str, Any]:
   cmd = ["lark-cli", *args]
   print(f"$ {' '.join(cmd)}", file=sys.stderr)
   result = subprocess.run(cmd, capture_output=True, text=True)
   if result.returncode != 0:
       print(f"lark-cli error: {result.stderr}", file=sys.stderr)
       raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
   try:
       return json.loads(result.stdout)
   except json.JSONDecodeError:
       print(f"Non-JSON output: {result.stdout}", file=sys.stderr)
       return {"raw": result.stdout}


def create_base(schema: dict[str, Any]) -> dict[str, Any]:
   fields_json = json.dumps(schema["fields"], ensure_ascii=False)
   return run_lark_cli(
       "base", "+base-create",
       "--name", schema["name"],
       "--table-name", schema["table_name"],
       "--fields", fields_json,
       "--as", "user",
       "--format", "json",
   )


def list_tables(base_token: str) -> dict[str, Any]:
   return run_lark_cli(
       "base", "+table-list",
       "--base-token", base_token,
       "--as", "user",
       "--format", "json",
   )


def list_fields(base_token: str, table_id: str) -> dict[str, Any]:
   return run_lark_cli(
       "base", "+field-list",
       "--base-token", base_token,
       "--table-id", table_id,
       "--as", "user",
       "--format", "json",
   )


def main():
   parser = argparse.ArgumentParser(description="Set up or validate the paper-reading Base.")
   parser.add_argument("--config", required=True, type=Path, help="Path to config.toml.")
   parser.add_argument(
       "--schema",
       type=Path,
       default=Path(__file__).parent.parent / "templates" / "base_schema.json",
       help="Path to base_schema.json.",
   )
   parser.add_argument("--create", action="store_true", help="Create the Base if base_token is not set.")
   args = parser.parse_args()

   config = load_config(args.config)
   feishu_cfg = config.get("feishu", {})
   base_token = feishu_cfg.get("base_token", "")
   table_id = feishu_cfg.get("table_id", "")

   with open(args.schema, "r", encoding="utf-8") as f:
       schema = json.load(f)

   if not base_token and args.create:
       print("Creating new Base from schema...", file=sys.stderr)
       result = create_base(schema)
       print(json.dumps(result, ensure_ascii=False, indent=2))
       print("\nPlease copy base_token and table_id into your config.toml.", file=sys.stderr)
       return

   if not base_token:
       print("ERROR: base_token not set. Run with --create to create a new Base.", file=sys.stderr)
       sys.exit(1)

   print(f"Base token: {base_token}")
   if not table_id:
       tables = list_tables(base_token)
       print("Available tables:")
       print(json.dumps(tables, ensure_ascii=False, indent=2))
       print("\nPlease set table_id in config.toml.", file=sys.stderr)
       return

   fields = list_fields(base_token, table_id)
   print(f"Fields in table {table_id}:")
   print(json.dumps(fields, ensure_ascii=False, indent=2))

   existing_names = {f.get("name") for f in fields.get("fields", [])}
   required_names = {f["name"] for f in schema["fields"]}
   missing = required_names - existing_names
   if missing:
       print(f"\nWARNING: Missing fields in Base: {', '.join(missing)}", file=sys.stderr)
   else:
       print("\nAll required fields are present.", file=sys.stderr)


if __name__ == "__main__":
   main()
