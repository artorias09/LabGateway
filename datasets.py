import csv
import io
import json
from pathlib import Path

MAX_DATA_BYTES = 5 * 1024 * 1024
PREVIEW_ROWS = 20


class InvalidDataset(ValueError):
    pass


def _decode(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InvalidDataset("Arquivo deve estar em UTF-8.") from None


def analyze_dataset(raw: bytes, filename: str) -> dict:
    if not raw or len(raw) > MAX_DATA_BYTES:
        raise InvalidDataset("Arquivo vazio ou maior que 5 MiB.")

    suffix = Path(filename or "").suffix.lower()
    if suffix == ".csv":
        text = _decode(raw)
        try:
            reader = csv.DictReader(io.StringIO(text))
            columns = reader.fieldnames or []
            if not columns or any(not str(c).strip() for c in columns):
                raise InvalidDataset("CSV precisa ter cabeçalho.")
            if len(set(columns)) != len(columns):
                raise InvalidDataset("CSV possui colunas duplicadas.")
            preview = []
            count = 0
            for row in reader:
                count += 1
                if len(preview) < PREVIEW_ROWS:
                    preview.append({key: row.get(key, "") for key in columns})
        except csv.Error as exc:
            raise InvalidDataset(f"CSV inválido: {exc}") from None
        return {
            "file_type": "csv",
            "row_count": count,
            "columns": columns,
            "preview": preview,
        }

    if suffix == ".json":
        text = _decode(raw)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InvalidDataset(f"JSON inválido na linha {exc.lineno}.") from None

        if isinstance(data, dict) and isinstance(data.get("records"), list):
            records = data["records"]
        elif isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = [data]
        else:
            raise InvalidDataset("JSON deve conter objetos ou uma lista de objetos.")

        if any(not isinstance(row, dict) for row in records):
            raise InvalidDataset("Cada registro JSON deve ser um objeto.")

        columns = []
        seen = set()
        for row in records:
            for key in row:
                key = str(key)
                if key not in seen:
                    seen.add(key)
                    columns.append(key)

        preview = []
        for row in records[:PREVIEW_ROWS]:
            preview.append({
                column: _display_json_value(row.get(column))
                for column in columns
            })

        return {
            "file_type": "json",
            "row_count": len(records),
            "columns": columns,
            "preview": preview,
        }

    raise InvalidDataset("Envie um arquivo .csv ou .json.")


def _display_json_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if value is None:
        return ""
    return str(value)


def analyze_dataset_file(path: Path) -> dict:
    return analyze_dataset(path.read_bytes(), path.name)
