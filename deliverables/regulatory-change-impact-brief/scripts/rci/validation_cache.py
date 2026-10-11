"""Bounded memoization of successful pure validation on an exact disk inventory.

Every call rereads all package files. No mtime, completion flag, source retrieval,
failed check or prior-run state is used as proof. A changed byte, file set or link
invalidates the result. Cached records are copied to protect them from callers.
"""
from collections import OrderedDict
from copy import deepcopy
from functools import wraps
import hashlib


def _inventory(root):
    digest=hashlib.sha256()
    for path in sorted(root.rglob('*')):
        relative=path.relative_to(root).as_posix()
        digest.update(relative.encode()+b'\0')
        if path.is_symlink():
            # Let the validator enforce path safety; never follow a link for caching.
            return None
        elif path.is_file():
            digest.update(b'file\0'+hashlib.sha256(path.read_bytes()).digest())
        else: digest.update(b'directory\0')
    return digest.digest()


def disk_verified(function):
    successful=OrderedDict()
    @wraps(function)
    def validate(store):
        inventory=_inventory(store.root)
        if inventory is None: return function(store)
        key=(str(store.root.resolve()),store.run_id,inventory)
        if key in successful:
            successful.move_to_end(key)
            return deepcopy(successful[key])
        value=function(store)
        # Validators are read-only. Unexpected writes are never memoized.
        if _inventory(store.root)==key[-1]:
            successful[key]=deepcopy(value)
            if len(successful)>8:successful.popitem(last=False)
        return value
    validate.clear_cache=successful.clear
    return validate
