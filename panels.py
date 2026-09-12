"""لایه‌ی یکپارچه‌ی مدیریت/ارتباط با نمونه‌های پنل VPN.
این ماژول جایگزین انتخاب «پنل فعال» می‌شود: هر سرویس از mapping همان پلن
به یک instance مشخص پنل استفاده می‌کند.
"""
import time
import marzban_panel
import pasargad_panel

PANEL_TYPE_LABELS = {
    "marzban": "مرزبان (Marzban)",
    "pasargad": "پاسارگارد (PasarGuard)",
}
PANEL_TYPES = list(PANEL_TYPE_LABELS)

def panel_label(panel: dict) -> str:
    t = PANEL_TYPE_LABELS.get(panel.get("panel_type"), panel.get("panel_type") or "?")
    return f"{t} — {panel.get('name') or ('#' + str(panel.get('id')))}"

def _client(panel):
    ptype = panel.get("panel_type")
    if ptype == "marzban":
        return marzban_panel
    if ptype == "pasargad":
        return pasargad_panel
    return None

async def test_connection(panel):
    client = _client(panel)
    if not client:
        return False, None, "نوع پنل نامعتبر."
    return await client.test_connection(panel)

async def get_system_stats(panel):
    client = _client(panel)
    if not client:
        return False, None, "نوع پنل نامعتبر."
    fn = getattr(client, "get_system_stats", None)
    if fn:
        return await fn(panel)
    return await client.test_connection(panel)

async def get_catalog(panel):
    """کاتالوگ Templateهای همین instance را برای نگاشت برمی‌گرداند."""
    client = _client(panel)
    if not client:
        return [], "نوع پنل نامعتبر."
    ok, data, msg = await client.get_templates(panel)
    if not ok:
        return [], msg
    items = data if isinstance(data, list) else []
    result = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        ref = item.get("id")
        if ref is None:
            ref = item.get("slug")
        if ref is None:
            continue
        name = item.get("name") or item.get("remark") or str(ref)
        result.append({"idx": i, "ref": str(ref), "name": name, "label": f"📦 {name} (ID: {ref})"})
    if not result:
        return [], "هیچ Template/بسته‌ای در این پنل پیدا نشد."
    return result, "موفق"

async def get_template(panel, remote_ref):
    client = _client(panel)
    if not client:
        return False, None, "نوع پنل نامعتبر."
    try:
        return await client.get_template(int(remote_ref), panel)
    except (TypeError, ValueError):
        return False, None, "شناسه‌ی Template نامعتبر است."

async def create_service(panel, username, remote_ref, volume_gb=None, days=None, device_limit=None):
    client = _client(panel)
    if not client:
        return False, None, None, None, "نوع پنل نامعتبر."
    try:
        ref = int(remote_ref)
    except (TypeError, ValueError):
        return False, None, None, None, "شناسه‌ی Template نامعتبر است."
    try:
        ok, data, msg = await client.create_user_custom(
            panel, ref, username, volume_gb, days, device_limit=device_limit
        )
    except TypeError:
        ok, data, msg = await client.create_user_custom(panel, ref, username, volume_gb, days)
    if not ok:
        return False, None, None, data, msg
    link, service_id = client.extract_link_and_username(panel, data)
    return True, link, service_id or username, data, msg

async def renew_service(panel, service_id, remote_ref=None, volume_gb=None, days=None, device_limit=None):
    client = _client(panel)
    if not client:
        return False, None, service_id, None, "نوع پنل نامعتبر."
    if remote_ref is not None:
        try:
            remote_ref = int(remote_ref)
        except (TypeError, ValueError):
            pass
    if volume_gb is not None or days is not None:
        fn = getattr(client, "renew_user_custom", None)
        if fn:
            try:
                ok, data, msg = await fn(panel, service_id, volume_gb, days, device_limit=device_limit)
            except TypeError:
                ok, data, msg = await fn(panel, service_id, volume_gb, days)
        else:
            return False, None, service_id, None, "تمدید سفارشی برای این پنل پشتیبانی نمی‌شود."
    else:
        if remote_ref is None:
            return False, None, service_id, None, "برای تمدید این سرویس Template مشخص نشده است."
        ok, data, msg = await client.renew_user(panel, service_id, remote_ref, device_limit=device_limit)
    if not ok:
        return False, None, service_id, data, msg
    link, service_id2 = client.extract_link_and_username(panel, data)
    return True, link, service_id2 or service_id, data, msg

async def get_service_snapshot(panel, service_id):
    client = _client(panel)
    if not client:
        return False, None, "نوع پنل نامعتبر."
    fn = getattr(client, "get_user", None)
    if not fn:
        return False, None, "دریافت اطلاعات سرویس پشتیبانی نمی‌شود."
    ok, data, msg = await fn(panel, service_id)
    if not ok:
        return False, None, msg
    return True, data, msg

async def disable_service(panel, service_id):
    client = _client(panel)
    return await client.disable_user(panel, service_id) if client else (False, "نوع پنل نامعتبر.")

async def enable_service(panel, service_id):
    client = _client(panel)
    return await client.enable_user(panel, service_id) if client else (False, "نوع پنل نامعتبر.")

async def delete_service(panel, service_id):
    client = _client(panel)
    return await client.delete_user(panel, service_id) if client else (False, "نوع پنل نامعتبر.")

async def regenerate_sub_link(panel, service_id):
    client = _client(panel)
    if not client:
        return False, None, service_id, None, "نوع پنل نامعتبر."
    fn = getattr(client, "revoke_sub", None)
    if not fn:
        return False, None, service_id, None, "تغییر لینک ساب برای این پنل پشتیبانی نمی‌شود."
    ok, data, msg = await fn(panel, service_id)
    if not ok:
        return False, None, service_id, data, msg
    link, service_id2 = client.extract_link_and_username(panel, data)
    return True, link, service_id2 or service_id, data, msg

def extract_panel_configs(snapshot):
    if not isinstance(snapshot, dict):
        return []
    out=[]
    for key in ("links","links_v2ray","subscription_url","subscription_url_base","subscription_url_base64"):
        value=snapshot.get(key)
        if isinstance(value,str) and value.startswith(("http://","https://")):
            out.append(value)
        elif isinstance(value,list):
            out.extend(x for x in value if isinstance(x,str) and x.startswith(("http://","https://")))
    return list(dict.fromkeys(out))
