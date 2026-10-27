"""Exact nonsecret CloudShell route proof; no credential fetch or import action.

The authorization token is only type/presence checked and copied in memory.
This module never hashes, formats, saves, logs, or independently fetches it.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from datetime import datetime, timezone
from urllib.parse import urlsplit

BASE = Path('/home/cloudshell-user/ecoguard-c-personal-20261023')
PROOF_PATH = BASE/'cloudshell-existing-container-route-metadata-20261025-7.json'
BOOT_ID = 'ef7bbcb6-4608-4850-96b1-c4c002135397'
FULL_URI_SHA256 = '99462476951da2ecf1af43b97df026b14e2591a7c2937479a0a00ac0afc812df'
PATH_SHA256 = 'a560d726b1605b942fda857778b836f10e0fea103fbb77f5836f9799340bb876'
SELECTORS = ['AWS_CONTAINER_CREDENTIALS_FULL_URI', 'AWS_CONTAINER_AUTHORIZATION_TOKEN']
DIRECT = ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN')
PROOF_KEYS = {'recordType','observedAtUtc','provenance','accountId','region','bootId','uid','home',
 'selectorNames','fullURI_SHA256','pathSHA256','scheme','hostname','port','queryPresent','userInfoPresent',
 'fragmentPresent','directCredentialVariablesPresent','authorizationTokenPresent','authorizationTokenFilePresent'}


def require(ok, message):
    if not ok: raise ValueError(message)


def validate_observation(proof, *, boot_id, uid, home, now):
    require(type(proof) is dict and set(proof)==PROOF_KEYS, 'Exact nonsecret route observation schema required')
    require(proof['recordType']=='ui-observed-cloudshell-container-route-metadata-v1'
      and type(proof['provenance']) is str and proof['provenance']=='Native non-secret environment metadata saved once and observed through the official AWS CloudShell UI; accountId is from the refreshed official console header, not a fresh STS assertion.',
      'Route observation provenance differs')
    require(proof['accountId']=='011154879765' and proof['region']=='us-east-1'
      and proof['bootId']==boot_id==BOOT_ID and type(uid) is int and proof['uid']==uid==1000
      and type(proof['uid']) is int and proof['home']==home=='/home/cloudshell-user', 'Current route VM/user/scope differs')
    require(type(proof['observedAtUtc']) is str, 'Route observation UTC missing')
    try: observed=datetime.fromisoformat(proof['observedAtUtc'].replace('Z','+00:00'))
    except (ValueError,TypeError): raise ValueError('Route observation UTC malformed') from None
    require(observed.tzinfo is not None and observed.utcoffset().total_seconds()==0 and observed<=now, 'Route observation UTC future/non-UTC')
    require(proof['selectorNames']==SELECTORS and proof['fullURI_SHA256']==FULL_URI_SHA256
      and proof['pathSHA256']==PATH_SHA256 and proof['scheme']=='http' and proof['hostname']=='localhost'
      and type(proof['port']) is int and proof['port']==1338, 'Actual exact route fingerprint differs')
    require(all(proof[k] is False for k in ('queryPresent','userInfoPresent','fragmentPresent','authorizationTokenFilePresent'))
      and proof['authorizationTokenPresent'] is True, 'Unreviewed route/auth metadata')
    require(type(proof['directCredentialVariablesPresent']) is dict
      and set(proof['directCredentialVariablesPresent'])==set(DIRECT)
      and all(value is False for value in proof['directCredentialVariablesPresent'].values()), 'Direct credentials may shadow container route')
    return proof


def load_observation(reference):
    require(type(reference) is dict and set(reference)=={'path','sha256'}
      and reference['path']==str(PROOF_PATH) and type(reference['sha256']) is str
      and re.fullmatch('[0-9a-f]{64}',reference['sha256']), 'Actual pinned route observation pending')
    path=Path(reference['path'])
    require(not any(p.is_symlink() for p in (path,*path.parents)), 'Route observation path/link differs')
    info=path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid()==1000
      and stat.S_IMODE(info.st_mode)==0o600 and info.st_nlink==1, 'Route observation private file differs')
    raw=path.read_bytes()
    require(hashlib.sha256(raw).hexdigest()==reference['sha256'], 'Route observation raw SHA differs')
    proof=json.loads(raw)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    return validate_observation(proof,boot_id=boot,uid=os.getuid(),home='/home/cloudshell-user',now=datetime.now(timezone.utc))


def reviewed_credentials(ambient, reference=None):
    require(type(ambient) is dict and all(type(k) is str and type(v) is str for k,v in ambient.items()), 'Explicit string environment required')
    container={k for k in ambient if k.startswith('AWS_CONTAINER_')}
    if reference is None:
        require(not container, 'Container route observation pending; no fallback')
        require(bool(ambient.get('AWS_ACCESS_KEY_ID')) and bool(ambient.get('AWS_SECRET_ACCESS_KEY')), 'Ambient CloudShell credential pair unavailable')
        return {k:ambient[k] for k in DIRECT if k in ambient}
    load_observation(reference)
    require(container==set(SELECTORS) and all(k not in ambient for k in DIRECT), 'Container selector/direct credential mix differs')
    uri=ambient['AWS_CONTAINER_CREDENTIALS_FULL_URI']
    require(bool(uri) and hashlib.sha256(uri.encode('utf-8')).hexdigest()==FULL_URI_SHA256, 'Exact container selector SHA differs')
    try:
        parsed=urlsplit(uri)
        valid=(parsed.scheme=='http' and parsed.hostname=='localhost' and parsed.port==1338
          and parsed.username is None and parsed.password is None and not parsed.query and not parsed.fragment
          and hashlib.sha256(parsed.path.encode('utf-8')).hexdigest()==PATH_SHA256)
    except ValueError: valid=False
    require(valid, 'Exact container selector metadata differs')
    require(bool(ambient['AWS_CONTAINER_AUTHORIZATION_TOKEN']), 'Required memory-only authorization token unavailable')
    return {k:ambient[k] for k in SELECTORS}
