"""U05 route declarations. No source facts or normalization mappings."""
from dataclasses import dataclass
import json
from pathlib import Path
from urllib.parse import urlsplit

from .contracts import require
from .runtime import REPO, validate_config


@dataclass(frozen=True)
class Source:
    id: str
    route: str
    adapter: str
    credential_ref: str | None

    @property
    def document_id(self):
        if self.adapter == 'google-sheets-read':
            parts = urlsplit(self.route).path.split('/')
            require(len(parts) == 4 and parts[1:3] == ['spreadsheets', 'd']
                    and parts[3], 'unsupported spreadsheet route')
            return parts[3]
        return None


def manifest(config):
    validate_config(config)
    result = tuple(Source(**source) for source in config['sources'])
    for source in result:
        require(source.adapter in {'http-read', 'google-sheets-read'}, 'unsupported read adapter')
        if source.adapter == 'google-sheets-read':
            require(urlsplit(source.route).hostname == 'docs.google.com', 'unsupported sheet host')
            source.document_id
    return result


def disclosed_manifest():
    # The reviewed config holds the ten exact interview locators, not live facts.
    return manifest(json.loads((REPO/'config/review.example.json').read_bytes()))


def credential_inventory(path):
    """External nonsecret inventory; token values stay in the operator environment."""
    if path is None:
        return {}
    path = Path(path).resolve()
    require(not path.is_relative_to(REPO.resolve()), 'credential inventory must be external')
    inventory = json.loads(path.read_bytes())
    require(isinstance(inventory, dict), 'invalid credential inventory')
    for ref, entry in inventory.items():
        require(isinstance(ref, str) and ref.strip() and isinstance(entry, dict)
                and set(entry) == {'owner', 'principal', 'scopes', 'token_env'}, 'invalid credential reference')
        require(all(isinstance(entry[k], str) and entry[k].strip()
                    for k in ('owner', 'principal', 'token_env')), 'credential owner/reference required')
        require(entry['scopes'] == ['https://www.googleapis.com/auth/spreadsheets.readonly'],
                'read-only Sheets scope required')
        import re
        require(re.fullmatch(r'RCI_[A-Z0-9_]+', entry['token_env']), 'invalid token environment reference')
    return inventory
