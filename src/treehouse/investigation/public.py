"""Small public projection for report/plugin text; sealed records remain unchanged."""

import re

PRIVATE = {"keypath", "keys", "keylabels", "labels", "rawprompt", "prompt", "systemprompt",
           "sourceprompt", "messages", "pixels", "imagebase64", "bytes", "bytes_", "blob",
           "authorization", "apikey", "accesstoken", "sessiontoken", "awssecretaccesskey",
           "awssessiontoken", "secretaccesskey", "password", "privatekey", "credential"}


def public_value(value):
    if isinstance(value, dict):
        return {public_value(str(k)): ("[REDACTED]" if re.sub(r"[^a-z0-9]", "", str(k).lower()) in PRIVATE
                                       else public_value(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [public_value(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b", "[REDACTED ACCESS KEY]", value)
        value = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "[REDACTED BEARER]", value)
        value = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", "[REDACTED PRIVATE KEY]", value, flags=re.S)
        value = re.sub(r"(?i)\b(aws_secret_access_key|aws_session_token|access_token|api_key|password|authorization)\b[\"']?\s*[:=]\s*[\"']?[^\s,;\"']+", r"\1=[REDACTED]", value)
        value = re.sub(r"(?<!\w)(?:/(?:Users|home|private|tmp|var|etc|opt|mnt)/[^\s<>\"']+|keys[/\\][^\s<>\"']+)", "[REDACTED PATH]", value)
    return value
