from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
import database as db
import vpn_panel
from states import AdminStates
from utils import answer_rich, edit_rich
from text_catalog import text as t
from keyboards import admin_pasargad_panels_keyboard, admin_pasargad_panel_detail_keyboard, admin_pasargad_panel_edit_keyboard
from handlers.admin import _is_admin
router=Router(name='panel_admin')

def ptext(p):
    return t(
        "admin_panel_detail",
        "🛡️ {name}\n\nوضعیت: {status}\nآدرس: {url}\nروش اتصال: Username / Password",
        name=p.get("name") or "پنل پاسارگارد",
        status="🟢 فعال" if p.get("enabled") else "🔴 غیرفعال",
        url=p.get("base_url") or "-",
    )

@router.callback_query(F.data=='admin_pasargad_panels')
async def open_panels(c):
    if not _is_admin(c.from_user.id): return
    await edit_rich(c.message, t('admin_panels_intro'),reply_markup=admin_pasargad_panels_keyboard(db.list_vpn_panels('pasargad'))); await c.answer()
@router.message(F.text=='🛡️ مدیریت پنل‌های پاسارگارد')
async def open_panels_msg(m,state):
    if not _is_admin(m.from_user.id): return
    await state.clear(); await answer_rich(m,t('admin_panels_intro'),reply_markup=admin_pasargad_panels_keyboard(db.list_vpn_panels('pasargad')))
@router.callback_query(F.data=='pp_add')
async def add_start(c,state):
    if not _is_admin(c.from_user.id): return
    await state.clear(); await state.update_data(pp_mode='add'); await state.set_state(AdminStates.waiting_vpn_panel_name); await edit_rich(c.message, t('admin_panel_name_prompt', '➕ نام پنل را بفرستید:')); await c.answer()
@router.message(AdminStates.waiting_vpn_panel_name)
async def name_input(m,state):
    if not _is_admin(m.from_user.id): return
    d=await state.get_data(); v=(m.text or '').strip()
    if not v:return await answer_rich(m, t('admin_panel_value_required', '❌ مقدار نمی‌تواند خالی باشد.'))
    if d.get('pp_mode')=='edit':
        db.update_vpn_panel(int(d['pp_id']),**{d['pp_field']:v}); await state.clear(); return await answer_rich(m, '✅ ذخیره شد.',reply_markup=admin_pasargad_panel_detail_keyboard(db.get_vpn_panel(int(d['pp_id']))))
    await state.update_data(pp_name=v); await state.set_state(AdminStates.waiting_vpn_panel_url); await answer_rich(m, t('admin_panel_url_prompt', '🌐 آدرس پایه پنل را بفرستید:'))
@router.message(AdminStates.waiting_vpn_panel_url)
async def url_input(m,state):
    if not _is_admin(m.from_user.id):return
    v=(m.text or '').strip().rstrip('/')
    if not v.startswith(('http://','https://')):return await answer_rich(m, t('admin_panel_invalid_url', '❌ آدرس نامعتبر است.'))
    await state.update_data(pp_url=v); await state.set_state(AdminStates.waiting_vpn_panel_username); await answer_rich(m, t('admin_panel_username_prompt', '👤 نام کاربری پنل را بفرستید:'))
@router.message(AdminStates.waiting_vpn_panel_username)
async def user_input(m,state):
    if not _is_admin(m.from_user.id):return
    await state.update_data(pp_user=(m.text or '').strip()); await state.set_state(AdminStates.waiting_vpn_panel_password); await answer_rich(m, t('admin_panel_password_prompt', '🔑 رمز عبور پنل را بفرستید:'))
@router.message(AdminStates.waiting_vpn_panel_password)
async def pass_input(m,state):
    if not _is_admin(m.from_user.id):return
    d=await state.get_data(); pid=db.add_vpn_panel(d['pp_name'],d['pp_url'],d['pp_user'],(m.text or '').strip()); await state.clear(); ok,_,msg=await vpn_panel.test_connection(pid); p=db.get_vpn_panel(pid); await answer_rich(m, (t('admin_panel_connection_ok','✅ اتصال موفق بود.') if ok else t('admin_panel_saved_test_failed','⚠️ پنل ذخیره شد ولی تست اتصال ناموفق بود:\n{msg}').format(msg=msg)),reply_markup=admin_pasargad_panel_detail_keyboard(p))
@router.callback_query(F.data.startswith('pp_detail|'))
async def detail(c):
    if not _is_admin(c.from_user.id):return
    p=db.get_vpn_panel(int(c.data.split('|')[1]));
    if not p:return await c.answer('پنل پیدا نشد.',show_alert=True)
    await edit_rich(c.message, ptext(p),reply_markup=admin_pasargad_panel_detail_keyboard(p)); await c.answer()
@router.callback_query(F.data.startswith('pp_test|'))
async def test(c):
    if not _is_admin(c.from_user.id):return
    await c.answer(t('admin_panel_testing', '⏳ در حال تست اتصال...')); ok,_,msg=await vpn_panel.test_connection(int(c.data.split('|')[1])); await answer_rich(c.message, ('✅ ' if ok else '❌ ')+msg)
@router.callback_query(F.data.startswith('pp_toggle|'))
async def toggle(c):
    if not _is_admin(c.from_user.id):return
    pid=int(c.data.split('|')[1]); p=db.get_vpn_panel(pid); db.update_vpn_panel(pid,enabled=not bool(p.get('enabled'))); p=db.get_vpn_panel(pid); await edit_rich(c.message, ptext(p),reply_markup=admin_pasargad_panel_detail_keyboard(p)); await c.answer()
@router.callback_query(F.data.startswith('pp_delete|'))
async def delete(c):
    if not _is_admin(c.from_user.id):return
    db.delete_vpn_panel(int(c.data.split('|')[1])); await edit_rich(c.message, '🗑 پنل حذف شد.',reply_markup=admin_pasargad_panels_keyboard(db.list_vpn_panels('pasargad'))); await c.answer()
@router.callback_query(F.data.startswith('pp_edit|'))
async def edit(c):
    if not _is_admin(c.from_user.id):return
    pid=int(c.data.split('|')[1]); p=db.get_vpn_panel(pid); await edit_rich(c.message, t('admin_panel_edit_choose', '✏️ مشخصه موردنظر را انتخاب کنید:'),reply_markup=admin_pasargad_panel_edit_keyboard(p)); await c.answer()
@router.callback_query(F.data.startswith('pp_editfield|'))
async def editfield(c,state):
    if not _is_admin(c.from_user.id):return
    _,pid,field=c.data.split('|'); await state.update_data(pp_mode='edit',pp_id=int(pid),pp_field=field); await state.set_state(AdminStates.waiting_vpn_panel_name); await edit_rich(c.message, t('admin_panel_edit_value', '✏️ مقدار جدید را ارسال کنید:')); await c.answer()

