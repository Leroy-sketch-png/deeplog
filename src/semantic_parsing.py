from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


_OBJECT_ID_CLAIM = "http://schemas.microsoft.com/identity/claims/objectidentifier"
_TENANT_ID_CLAIM = "http://schemas.microsoft.com/identity/claims/tenantid"
_IDP_CLAIM = "http://schemas.microsoft.com/identity/claims/identityprovider"


@dataclass
class ParseResult:
    data: Dict[str, Any]
    success: bool
    error: Optional[str]


def parse_json_maybe_double_encoded(raw: Optional[str]) -> ParseResult:
    if raw is None:
        return ParseResult(data={}, success=False, error="null")

    text = str(raw).strip()
    if text == "":
        return ParseResult(data={}, success=False, error="blank")

    def _loads(value: str) -> Any:
        return json.loads(value)

    try:
        obj = _loads(text)
        # Handle JSON payload encoded as a JSON string.
        if isinstance(obj, str):
            inner = obj.strip()
            if inner.startswith("{") or inner.startswith("["):
                obj = _loads(inner)
        if isinstance(obj, dict):
            return ParseResult(data=obj, success=True, error=None)
        return ParseResult(data={}, success=False, error=f"non_dict_json:{type(obj).__name__}")
    except Exception as exc1:
        # Best-effort unescape attempt for heavily escaped blobs.
        try:
            unescaped = text.replace('\\"', '"')
            obj2 = _loads(unescaped)
            if isinstance(obj2, str):
                inner2 = obj2.strip()
                if inner2.startswith("{") or inner2.startswith("["):
                    obj2 = _loads(inner2)
            if isinstance(obj2, dict):
                return ParseResult(data=obj2, success=True, error=None)
            return ParseResult(data={}, success=False, error=f"non_dict_json_after_unescape:{type(obj2).__name__}")
        except Exception as exc2:
            return ParseResult(data={}, success=False, error=f"json_error:{exc1};retry:{exc2}")


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def extract_properties_fields(properties_raw: Optional[str]) -> Tuple[Dict[str, str], bool, Optional[str]]:
    parsed = parse_json_maybe_double_encoded(properties_raw)
    obj = parsed.data

    http_req = obj.get("httpRequest")
    http_ip = ""
    if isinstance(http_req, dict):
        http_ip = _safe_text(http_req.get("clientIpAddress"))
    elif isinstance(http_req, str):
        nested = parse_json_maybe_double_encoded(http_req)
        if nested.success:
            http_ip = _safe_text(nested.data.get("clientIpAddress"))

    out = {
        "eventCategory": _safe_text(obj.get("eventCategory")),
        "entity": _safe_text(obj.get("entity")),
        "resource": _safe_text(obj.get("resource")),
        "message": _safe_text(obj.get("message")),
        "activityStatusValue": _safe_text(obj.get("activityStatusValue")),
        "activitySubstatusValue": _safe_text(obj.get("activitySubstatusValue")),
        "statusCode": _safe_text(obj.get("statusCode")),
        "statusMessage": _safe_text(obj.get("statusMessage")),
        "eventSubmissionTimestamp": _safe_text(obj.get("eventSubmissionTimestamp")),
        "serviceRequestId": _safe_text(obj.get("serviceRequestId")),
        "httpRequest.clientIpAddress": http_ip,
    }
    return out, parsed.success, parsed.error


def extract_claims_fields(claims_raw: Optional[str]) -> Tuple[Dict[str, str], bool, Optional[str]]:
    parsed = parse_json_maybe_double_encoded(claims_raw)
    obj = parsed.data
    out = {
        "appid": _safe_text(obj.get("appid")),
        "idtyp": _safe_text(obj.get("idtyp")),
        "object_id": _safe_text(obj.get(_OBJECT_ID_CLAIM)),
        "tenant_id": _safe_text(obj.get(_TENANT_ID_CLAIM)),
        "identity_provider": _safe_text(obj.get(_IDP_CLAIM)),
        "xms_mirid": _safe_text(obj.get("xms_mirid")),
        "xms_az_rid": _safe_text(obj.get("xms_az_rid")),
        "aud": _safe_text(obj.get("aud")),
        "appidacr": _safe_text(obj.get("appidacr")),
    }
    return out, parsed.success, parsed.error


def parse_timestamp(value: Optional[str]) -> Tuple[Optional[datetime], str]:
    text = _safe_text(value)
    if text == "":
        return None, ""

    candidate = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc), ""
    except Exception as exc:
        return None, f"timestamp_parse_error:{exc}"


def normalize_operation(raw_operation: str, raw_provider: str) -> Tuple[str, str, str, str, str]:
    operation = _safe_text(raw_operation).upper()
    provider_hint = _safe_text(raw_provider).upper()

    if operation == "":
        provider = provider_hint
        return operation, provider, "", "", ""

    parts = [p for p in operation.split("/") if p]
    provider = provider_hint
    if parts and provider == "":
        provider = parts[0].upper()

    action_verb = ""
    operation_family = ""
    resource_type = ""

    if len(parts) >= 2:
        action_verb = re.sub(r"[^A-Z0-9]", "", parts[-1].upper())
        family_parts = parts[1:-1]
        operation_family = "/".join(p.lower() for p in family_parts)
        if operation_family:
            resource_type = f"{provider}/{operation_family}" if provider else operation_family
        else:
            resource_type = provider
    elif len(parts) == 1:
        action_verb = re.sub(r"[^A-Z0-9]", "", parts[0].upper())
        operation_family = ""
        resource_type = provider

    return operation, provider, operation_family, action_verb, resource_type


def normalize_activity_status(activity_status: str, activity_substatus: str, status_code: str) -> str:
    s = f"{activity_status} {activity_substatus} {status_code}".lower()
    if "start" in s:
        return "start"
    if "succeed" in s or "success" in s or "ok" in s:
        return "success"
    if "fail" in s or "error" in s or "denied" in s or "forbidden" in s or "unauthorized" in s:
        return "failure"
    if "cancel" in s or "timeout" in s or "abort" in s:
        return "other_terminal"
    if s.strip() == "":
        return "unknown"
    return "other"


def classify_identity(idtyp: str, appid: str, managed_identity_resource: str, identity_provider: str) -> str:
    idtyp_l = _safe_text(idtyp).lower()
    appid_l = _safe_text(appid)
    mirid_l = _safe_text(managed_identity_resource).lower()
    idp_l = _safe_text(identity_provider).lower()

    if mirid_l != "":
        return "managed_identity"
    if idtyp_l in {"app", "serviceprincipal", "service_principal"}:
        return "application_or_service_principal"
    if appid_l != "" and idtyp_l != "user":
        return "application_or_service_principal"
    if idtyp_l == "user":
        return "human_like"
    if "live.com" in idp_l or "aad" in idp_l or "sts.windows.net" in idp_l:
        return "unknown"
    return "unknown"


def derive_token_e(provider: str, operation_family: str, action_verb: str, event_category: str) -> str:
    # Token E intentionally avoids explicit outcome/status to reduce target leakage.
    p = _safe_text(provider).upper()
    f = _safe_text(operation_family).lower()
    a = _safe_text(action_verb).upper()
    c = _safe_text(event_category).lower()
    return "|".join([p, f, a, c])
