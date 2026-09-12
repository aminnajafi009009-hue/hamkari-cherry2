"""مدیریت یکپارچه‌ی نمونه‌های پنل VPN.
معماری این فایل بر اساس مدیریت پنل‌های ربات Business است:
- چند نمونه مرزبان/پاسارگارد هم‌زمان
- هر پلن به یک نمونه‌ی مشخص نگاشت می‌شود
- مفهوم «پنل فعال» حذف شده است.
"""
import html
import json
import logging
import random
import re

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

import database as db
import panels
from states import AdminStates
from keyboards import (
    admin_vpn_panel_types_keyboard, admin_vpn_panel_list_keyboard,
    admin_vpn_panel_detail_keyboard, admin_vpn_panel_delete_confirm_keyboard,
    admin_vpn_panel_edit_menu_keyboard, admin_vpn_panel_auth_choice_keyboard,
    vpn_panel_back_keyboard, admin_vpn_panel_types_cancel_keyboard,
    admin_vpn_panel_map_menu_keyboard, vpn_map_vip_category_pick_keyboard,
    vpn_map_vip_plans_keyboard, vpn_catalog_pick_keyboard,
)
from handlers.admin import _is_admin
from utils import answer_rich

router = Router(name="panel_admin")
logger = logging.getLogger(__name__)


def _pretty(data, limit=1800):
    try:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        text = str(data)
    return html.escape(text[:limit] + ("..." if len(text) > limit else ""))


def _username(uid):
    prefix = "tg"
    try:
        from bot_info import get
        prefix = re.sub(r"[^A-Za-z0-9_]+", "", str(get("config_name_prefix") or "tg")) or "tg"
    except Exception:
        pass
    for _ in range(50):
        candidate = f"{prefix}_{random.randint(100000,999999)}"
        if not db.is_service_id_taken(candidate):
            return candidate
    return f"{prefix}_{uid}_{random.randint(1000,9999)}"


# ---------------------------------------------------------------------------
# ورودی مدیریت پنل‌ها
# ---------------------------------------------------------------------------
@router.callback_query(F.data == "admin_vpn_panels")
async def open_panel_manager(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "🖥️ <b>مدیریت پنل‌های VPN</b>\n\n"
        "هر نمونه‌ی پنل مستقل است و می‌تواند هم‌زمان با نمونه‌های دیگر فعال باشد.\n"
        "برای هر پلن، پنل مقصد از طریق «نگاشت» همان پنل مشخص می‌شود.",
        parse_mode="HTML",
        reply_markup=admin_vpn_panel_types_keyboard(),
    )
    await callback.answer()


@router.message(F.text == "🖥️ مدیریت پنل‌های VPN")
async def open_panel_manager_msg(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    await answer_rich(
        message,
        "🖥️ <b>مدیریت پنل‌های VPN</b>\n\n"
        "یک نوع پنل را انتخاب کنید:",
        reply_markup=admin_vpn_panel_types_keyboard(),
    )


@router.callback_query(F.data.startswith("vpntype|"))
async def panel_type_list(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    panel_type = callback.data.split("|", 1)[1]
    if panel_type not in panels.PANEL_TYPES:
        return await callback.answer("❌ نوع پنل نامعتبر.", show_alert=True)
    items = db.list_vpn_panels(panel_type)
    await callback.message.edit_text(
        f"🖥️ <b>پنل‌های {panels.PANEL_TYPE_LABELS[panel_type]}</b>\n\n"
        "می‌توانی چند نمونه را هم‌زمان نگه داری و فعال کنی.",
        parse_mode="HTML",
        reply_markup=admin_vpn_panel_list_keyboard(panel_type, items),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vpndetail|"))
async def panel_detail(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    pid = int(callback.data.split("|")[1])
    panel = db.get_vpn_panel(pid)
    if not panel:
        return await callback.answer("❌ پنل پیدا نشد.", show_alert=True)
    status = "🟢 فعال" if panel.get("enabled") else "🔴 غیرفعال"
    text = (
        f"🖥️ <b>{html.escape(panels.panel_label(panel))}</b>\n"
        f"وضعیت: {status}\n"
        f"🌐 آدرس: <code>{html.escape(panel.get('base_url') or '')}</code>\n"
        f"🔌 روش اتصال: {html.escape(panel.get('auth_method') or 'userpass')}"
    )
    await callback.message.edit_text(text, parse_mode="HTML",
                                     reply_markup=admin_vpn_panel_detail_keyboard(panel))
    await callback.answer()


@router.callback_query(F.data.startswith("vpntest|"))
async def panel_test(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    pid = int(callback.data.split("|")[1])
    panel = db.get_vpn_panel(pid)
    if not panel:
        return await callback.answer("❌ پنل پیدا نشد.", show_alert=True)
    await callback.answer("⏳ در حال تست اتصال...")
    ok, data, msg = await panels.test_connection(panel)
    await callback.message.answer(
        ("✅ اتصال موفق بود." if ok else f"❌ اتصال ناموفق بود:\n{msg}") +
        (f"\n\n<pre>{_pretty(data)}</pre>" if ok and data else ""),
        parse_mode="HTML", reply_markup=vpn_panel_back_keyboard(pid)
    )


@router.callback_query(F.data.startswith("vpntoggle|"))
async def panel_toggle(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    pid = int(callback.data.split("|")[1])
    panel = db.get_vpn_panel(pid)
    if not panel:
        return await callback.answer("❌ پنل پیدا نشد.", show_alert=True)
    db.update_vpn_panel(pid, enabled=not bool(panel.get("enabled")))
    panel = db.get_vpn_panel(pid)
    await callback.message.edit_text(
        f"🖥️ <b>{html.escape(panels.panel_label(panel))}</b>\n"
        f"وضعیت: {'🟢 فعال' if panel.get('enabled') else '🔴 غیرفعال'}\n"
        f"🌐 آدرس: <code>{html.escape(panel.get('base_url') or '')}</code>",
        parse_mode="HTML", reply_markup=admin_vpn_panel_detail_keyboard(panel)
    )
    await callback.answer("✅ وضعیت پنل تغییر کرد.")


@router.callback_query(F.data.startswith("vpndelete|"))
async def panel_delete_confirm(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    pid = int(callback.data.split("|")[1])
    panel = db.get_vpn_panel(pid)
    if not panel:
        return await callback.answer("❌ پنل پیدا نشد.", show_alert=True)
    await callback.message.edit_text(
        f"⚠️ حذف {html.escape(panels.panel_label(panel))}؟\n"
        "نگاشت‌های مربوط به این نمونه هم حذف می‌شوند؛ سرویس‌های قبلی دست‌نخورده می‌مانند.",
        parse_mode="HTML",
        reply_markup=admin_vpn_panel_delete_confirm_keyboard(pid),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vpndeleteconfirm|"))
async def panel_delete(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    pid = int(callback.data.split("|")[1])
    panel = db.get_vpn_panel(pid)
    if not panel:
        return await callback.answer("❌ پنل پیدا نشد.", show_alert=True)
    ptype = panel["panel_type"]
    db.delete_vpn_panel(pid)
    await callback.message.edit_text(
        "🗑️ پنل حذف شد.",
        reply_markup=admin_vpn_panel_list_keyboard(ptype, db.list_vpn_panels(ptype)),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# افزودن پنل
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("vpnadd|"))
async def panel_add_start(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    ptype = callback.data.split("|")[1]
    if ptype not in panels.PANEL_TYPES:
        return await callback.answer("❌ نوع پنل نامعتبر.", show_alert=True)
    await state.update_data(new_panel_type=ptype)
    await state.set_state(AdminStates.waiting_vpn_panel_name)
    await callback.message.edit_text(
        f"➕ افزودن {panels.PANEL_TYPE_LABELS[ptype]}\n\nنام دلخواه این نمونه را بفرستید:",
        reply_markup=admin_vpn_panel_types_cancel_keyboard(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_vpn_panel_name)
async def panel_add_name(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    value=(message.text or "").strip()
    if not value:
        return await message.answer("❌ نام نمی‌تواند خالی باشد.")
    await state.update_data(new_panel_name=value)
    await state.set_state(AdminStates.waiting_vpn_panel_url)
    await message.answer("🌐 آدرس پایه پنل را بفرستید (مثلاً https://panel.example.com):")


@router.message(AdminStates.waiting_vpn_panel_url)
async def panel_add_url(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    value=(message.text or "").strip().rstrip("/")
    if not value.startswith(("http://","https://")):
        return await message.answer("❌ آدرس معتبر نیست.")
    data=await state.get_data()
    await state.update_data(new_panel_base_url=value)
    await state.update_data(new_panel_auth_method="userpass")
    await message.answer("🔌 روش اتصال را انتخاب کنید:",
                         reply_markup=admin_vpn_panel_auth_choice_keyboard(data["new_panel_type"]))


@router.callback_query(F.data.startswith("vpnauthadd|"))
async def panel_auth_choice(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    _,ptype,method=callback.data.split("|")
    await state.update_data(new_panel_auth_method=method)
    if method=="api_key":
        await state.set_state(AdminStates.waiting_vpn_panel_api_key)
        await callback.message.edit_text("🔑 API Key را بفرستید:")
    else:
        await state.set_state(AdminStates.waiting_vpn_panel_username)
        await callback.message.edit_text("👤 نام کاربری را بفرستید:")
    await callback.answer()


@router.message(AdminStates.waiting_vpn_panel_api_key)
async def panel_add_api_key(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    value=(message.text or "").strip()
    if not value:
        return await message.answer("❌ API Key نمی‌تواند خالی باشد.")
    data=await state.get_data()
    pid=db.create_vpn_panel(data["new_panel_type"],data["new_panel_name"],data["new_panel_base_url"],
                            api_key=value,auth_method="api_key")
    await state.clear()
    panel=db.get_vpn_panel(pid)
    await message.answer(f"✅ {panels.panel_label(panel)} اضافه شد.",
                         reply_markup=admin_vpn_panel_detail_keyboard(panel))


@router.message(AdminStates.waiting_vpn_panel_username)
async def panel_add_username(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    value=(message.text or "").strip()
    if not value:
        return await message.answer("❌ نام کاربری نمی‌تواند خالی باشد.")
    await state.update_data(new_panel_username=value)
    await state.set_state(AdminStates.waiting_vpn_panel_password)
    await message.answer("🔐 رمز عبور را بفرستید:")


@router.message(AdminStates.waiting_vpn_panel_password)
async def panel_add_password(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    value=(message.text or "").strip()
    if not value:
        return await message.answer("❌ رمز عبور نمی‌تواند خالی باشد.")
    data=await state.get_data()
    pid=db.create_vpn_panel(data["new_panel_type"],data["new_panel_name"],data["new_panel_base_url"],
                            username=data["new_panel_username"],password=value,auth_method="userpass")
    await state.clear()
    panel=db.get_vpn_panel(pid)
    await message.answer(f"✅ {panels.panel_label(panel)} اضافه شد.",
                         reply_markup=admin_vpn_panel_detail_keyboard(panel))


# ---------------------------------------------------------------------------
# ویرایش
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("vpnedit|"))
async def panel_edit(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    pid=int(callback.data.split("|")[1]); panel=db.get_vpn_panel(pid)
    if not panel:
        return await callback.answer("❌ پنل پیدا نشد.", show_alert=True)
    await callback.message.edit_text("✏️ مشخصه‌ای که می‌خواهید تغییر کند را انتخاب کنید:",
                                     reply_markup=admin_vpn_panel_edit_menu_keyboard(panel))
    await callback.answer()


@router.callback_query(F.data.startswith("vpnauthswitch|"))
async def panel_auth_switch(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    pid=int(callback.data.split("|")[1]); panel=db.get_vpn_panel(pid)
    if not panel:
        return await callback.answer("❌ پنل پیدا نشد.", show_alert=True)
    new="api_key" if (panel.get("auth_method") or "userpass")=="userpass" else "userpass"
    db.update_vpn_panel(pid,auth_method=new)
    panel=db.get_vpn_panel(pid)
    await callback.message.edit_text(
        f"✅ روش اتصال روی {new} قرار گرفت.",
        reply_markup=admin_vpn_panel_edit_menu_keyboard(panel)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vpneditfield|"))
async def panel_edit_field_start(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    _,pid,field=callback.data.split("|")
    pid=int(pid); panel=db.get_vpn_panel(pid)
    if not panel:
        return await callback.answer("❌ پنل پیدا نشد.", show_alert=True)
    labels={"name":"نام","base_url":"آدرس پایه","username":"نام کاربری","password":"رمز عبور","api_key":"API Key"}
    await state.update_data(edit_panel_id=pid,edit_panel_field=field)
    await state.set_state(AdminStates.waiting_vpn_panel_edit_field)
    await callback.message.edit_text(f"✏️ {labels.get(field,field)} جدید را بفرستید:",
                                     reply_markup=vpn_panel_back_keyboard(pid))
    await callback.answer()


@router.message(AdminStates.waiting_vpn_panel_edit_field)
async def panel_edit_field_received(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    value=(message.text or "").strip()
    if not value:
        return await message.answer("❌ مقدار نمی‌تواند خالی باشد.")
    data=await state.get_data(); pid=data.get("edit_panel_id"); field=data.get("edit_panel_field")
    if field=="base_url": value=value.rstrip("/")
    db.update_vpn_panel(int(pid),**{field:value})
    await state.clear()
    panel=db.get_vpn_panel(int(pid))
    await message.answer("✅ ذخیره شد.",reply_markup=admin_vpn_panel_detail_keyboard(panel))


# ---------------------------------------------------------------------------
# نگاشت پلن → نمونه‌ی پنل
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("vpnmap|"))
async def panel_map_menu(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    pid=int(callback.data.split("|")[1]); panel=db.get_vpn_panel(pid)
    if not panel:
        return await callback.answer("❌ پنل پیدا نشد.", show_alert=True)
    await callback.message.edit_text(
        f"🗂️ <b>نگاشت برای {html.escape(panels.panel_label(panel))}</b>\n\n"
        "دسته‌بندی VIP را انتخاب کنید؛ سپس پلن موردنظر را به یک Template همین نمونه نگاشت کنید.",
        parse_mode="HTML", reply_markup=admin_vpn_panel_map_menu_keyboard(pid)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vpnmapvip|"))
async def map_vip_categories(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    pid=int(callback.data.split("|")[1])
    cats=db.get_vip_categories()
    if not cats:
        return await callback.answer("هنوز دسته‌بندی VIP ساخته نشده.", show_alert=True)
    await callback.message.edit_text("🗂️ دسته‌بندی VIP را انتخاب کنید:",
                                     reply_markup=vpn_map_vip_category_pick_keyboard(cats,pid))
    await callback.answer()


@router.callback_query(F.data.startswith("vpnmapvipcat|"))
async def map_vip_plans(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    _,pid,cat=callback.data.split("|"); pid=int(pid); cat=int(cat)
    plans=db.get_vip_plans(cat)
    if not plans:
        return await callback.answer("این دسته پلنی ندارد.", show_alert=True)
    await callback.message.edit_text("📦 پلن را انتخاب کنید:",
                                     reply_markup=vpn_map_vip_plans_keyboard(cat,plans,pid))
    await callback.answer()


@router.callback_query(F.data.startswith("vpnmapvipplan|"))
async def map_vip_plan(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    _,pid,cat,plan_id=callback.data.split("|")
    pid=int(pid); cat=int(cat); plan_id=int(plan_id)
    panel=db.get_vpn_panel(pid); plan=db.get_vip_plan_by_id(plan_id)
    if not panel or not plan:
        return await callback.answer("❌ پنل یا پلن پیدا نشد.", show_alert=True)
    items,msg=await panels.get_catalog(panel)
    if not items:
        return await callback.answer(f"❌ {msg}", show_alert=True)
    # برای نگاشت مستقیم، idx محلی به ref واقعی تبدیل می‌شود.
    await callback.message.edit_text(
        f"📦 Template پلن «{html.escape(plan['name'])}» را از {html.escape(panels.panel_label(panel))} انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=vpn_catalog_pick_keyboard(items,pid,plan_id,cat)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vpnmaptemplate|"))
async def map_template(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    _,pid,cat,plan_id,idx=callback.data.split("|")
    pid=int(pid); cat=int(cat); plan_id=int(plan_id); idx=int(idx)
    panel=db.get_vpn_panel(pid); plan=db.get_vip_plan_by_id(plan_id)
    items,msg=await panels.get_catalog(panel) if panel else ([], "پنل پیدا نشد")
    if not panel or not plan or idx<0 or idx>=len(items):
        return await callback.answer("❌ گزینه نامعتبر است.", show_alert=True)
    item=items[idx]
    db.set_panel_plan_map("vip_plan",plan_id,pid,item["ref"],item["name"])
    await callback.answer("✅ نگاشت ذخیره شد.", show_alert=True)
    await callback.message.edit_text(
        f"✅ پلن «{html.escape(plan['name'])}» به Template «{html.escape(item['name'])}» از پنل "
        f"«{html.escape(panel['name'])}» نگاشت شد.",
        parse_mode="HTML",
        reply_markup=vpn_map_vip_plans_keyboard(cat,db.get_vip_plans(cat),pid)
    )


@router.callback_query(F.data.startswith("vpnmapcat|"))
async def map_category_start(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    _,pid,scope,cat=callback.data.split("|")
    pid=int(pid); cat=int(cat)
    panel=db.get_vpn_panel(pid)
    if not panel:
        return await callback.answer("❌ پنل پیدا نشد.", show_alert=True)
    items,msg=await panels.get_catalog(panel)
    if not items:
        return await callback.answer(f"❌ {msg}", show_alert=True)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons=[
        [InlineKeyboardButton(text=x["label"],callback_data=f"vpnmapcatset|{pid}|{cat}|{x['idx']}",style="primary")]
        for x in items
    ]
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",callback_data=f"vpnmapvipcat|{pid}|{cat}",style="primary")])
    await callback.message.edit_text("📦 Template پیش‌فرض این دسته را انتخاب کنید:",reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("vpnmapcatset|"))
async def map_category_set(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    _,pid,cat,idx=callback.data.split("|")
    pid=int(pid); cat=int(cat); idx=int(idx)
    panel=db.get_vpn_panel(pid); items,msg=await panels.get_catalog(panel) if panel else ([], "پنل پیدا نشد")
    if not panel or idx<0 or idx>=len(items):
        return await callback.answer("❌ گزینه نامعتبر است.", show_alert=True)
    item=items[idx]
    db.set_panel_plan_map("vip_category",cat,pid,item["ref"],item["name"])
    await callback.answer("✅ نگاشت پیش‌فرض دسته ذخیره شد.",show_alert=True)
    await callback.message.edit_text("✅ نگاشت پیش‌فرض دسته ذخیره شد.",
                                     reply_markup=vpn_map_vip_plans_keyboard(cat,db.get_vip_plans(cat),pid))


@router.callback_query(F.data.startswith("vpnmapdelcat|"))
async def map_category_delete(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    _,pid,scope,cat=callback.data.split("|")
    if scope!="vip_category":
        return await callback.answer("❌ نگاشت نامعتبر.",show_alert=True)
    db.delete_panel_plan_map("vip_category",int(cat))
    await callback.answer("🗑️ نگاشت دسته حذف شد.",show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=vpn_map_vip_plans_keyboard(
        int(cat),db.get_vip_plans(int(cat)),int(pid)
    ))


# ---------------------------------------------------------------------------
# ارسال خودکار خرید آنلاین/کیف‌پول بر اساس نگاشت همان پلن
# ---------------------------------------------------------------------------
async def auto_fulfill_vip_via_panel(bot, uid, plan_key: str, order_id: int | None) -> bool:
    mapping=db.get_panel_map_for_plan_key(plan_key)
    if not mapping or not mapping.get("enabled"):
        return False
    panel=db.get_vpn_panel(int(mapping["panel_id"]))
    plan=db.get_effective_plan(plan_key)
    user=db.get_user(uid)
    if not panel or not panel.get("enabled") or not plan or not user:
        return False
    username=_username(uid)
    ok,link,service_id,data,msg=await panels.create_service(
        panel,username,mapping["remote_ref"],volume_gb=plan.get("volume_gb"),
        days=plan.get("days"),device_limit=plan.get("user_limit")
    )
    if not ok:
        logger.error("auto panel fulfillment failed: %s",msg)
        return False
    # همان مسیر تحویل قبلی، بدون نمایش/انتخاب «پنل فعال»
    try:
        from handlers.marzban_admin import _deliver_marzban_link
        ctx={"uid":uid,"plan_key":plan_key,"order_id":order_id,"order_kind":"plan",
             "slug":service_id,"snapshot":{"name":plan.get("name"),
             "volume_gb":plan.get("volume_gb"),"days":plan.get("days"),
             "user_limit":plan.get("user_limit")},"panel_id":panel["id"]}
        await _deliver_marzban_link(bot,ctx,link)
    except Exception:
        logger.exception("panel delivery failed after successful creation")
    return True
