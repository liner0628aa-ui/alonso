"""Small shared I/O helpers, not an adapter class hierarchy."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.request


def namespace(source, kind, native_id):
    if native_id is None:
        return None
    if isinstance(native_id, bool) or not str(native_id).strip():
        raise ValueError('Invalid source ID')
    return f'{source}:{kind}:{native_id}'


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class JSONCache:
    def __init__(self, root, base_url, offline=False):
        self.root, self.base_url, self.offline = Path(root), base_url.rstrip('/'), offline
        self.receipts = {}

    def load(self, relative, refresh=False):
        if not re.fullmatch(r'[A-Za-z0-9_./-]+', relative) or '..' in Path(relative).parts:
            raise ValueError('Unsafe cache path')
        path = self.root / relative
        receipt_path = path.with_suffix(path.suffix+'.metadata.json')
        if path.exists() and (self.offline or not refresh):
            data = path.read_bytes()
            receipt = json.loads(receipt_path.read_text())
            if receipt['sha256'] != sha256(data):
                raise ValueError('Raw cache checksum mismatch')
        else:
            if self.offline:
                raise FileNotFoundError(f'Offline cache missing: {relative}')
            url = self.base_url+'/'+relative
            request = urllib.request.Request(url, headers={'User-Agent':'football-role-analysis-research/0.3'})
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read()
            json.loads(data)  # Never cache a partial/error response.
            receipt = {'url':url, 'retrieved_at':utc_now(), 'sha256':sha256(data), 'bytes':len(data)}
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix('.download')
            temp.write_bytes(data); temp.replace(path)
            receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')
        self.receipts[relative] = receipt
        return json.loads(data)
