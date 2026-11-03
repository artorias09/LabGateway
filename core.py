"""Pure validation helpers: no third-party dependencies."""
import io
import re
import zipfile
from pathlib import PurePosixPath

MAX_ZIP_BYTES = 2 * 1024 * 1024
MAX_UNCOMPRESSED = 5 * 1024 * 1024
MAX_FILES = 50
MAX_FILE_BYTES = 1024 * 1024
ALLOWED_EXTENSIONS = {'.py', '.txt', '.json', '.csv', '.md'}

class InvalidSubmission(ValueError):
    pass

def validate_submission(raw: bytes) -> dict[str, bytes]:
    if not raw or len(raw) > MAX_ZIP_BYTES:
        raise InvalidSubmission('ZIP vazio ou maior que 2 MiB')
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except (zipfile.BadZipFile, ValueError):
        raise InvalidSubmission('ZIP inválido') from None
    files = {}
    total = 0
    with z:
        entries = z.infolist()
        if len(entries) > MAX_FILES:
            raise InvalidSubmission('Muitos arquivos')
        for entry in entries:
            name = entry.filename
            if entry.is_dir():
                continue
            p = PurePosixPath(name)
            if (name.startswith('/') or '\\' in name or '\x00' in name or
                any(part in ('..', '.') for part in name.split('/')) or
                len(name) > 180 or len(p.parts) > 5 or
                p.suffix.lower() not in ALLOWED_EXTENSIONS or
                p.name.startswith('.') or
                (entry.external_attr >> 16) & 0o170000 == 0o120000):
                raise InvalidSubmission(f'Caminho/tipo não permitido: {name[:60]}')
            if entry.flag_bits & 1:
                raise InvalidSubmission('Arquivos criptografados não são aceitos')
            if entry.file_size > MAX_FILE_BYTES:
                raise InvalidSubmission('Arquivo grande demais')
            total += entry.file_size
            if total > MAX_UNCOMPRESSED:
                raise InvalidSubmission('Conteúdo descompactado grande demais')
            if name in files:
                raise InvalidSubmission('Arquivos duplicados')
            with z.open(entry) as fp:
                data = fp.read(MAX_FILE_BYTES + 1)
            if len(data) != entry.file_size:
                raise InvalidSubmission('Tamanho inconsistente')
            files[name] = data
    if 'main.py' not in files:
        raise InvalidSubmission('O ZIP deve conter main.py na raiz')
    return files

def safe_slug(value: str) -> bool:
    return bool(re.fullmatch(r'[a-z][a-z0-9_-]{2,31}', value))
