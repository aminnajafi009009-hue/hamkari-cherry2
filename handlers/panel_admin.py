from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
import database as db
import vpn_panel
from states import AdminStates
from utils import answer_rich
from keyboards import admin_pasargad_panels_keyboard, admin_pasargad_panel_detail_keyboard, admin_pasargad_panel_edit_keyboard, admin_pasargad_panel_mapping_keyboard, admin_pasargad_panel_template_map_keyboard, admin_vip_plan_panel_keyboard, admin_vip_plan_panel_template_keyboard, admin_vip_plan_detail_keyboard
from handlers.admin import _is_admin
router=Router(name='panel_admin')

def ptext(p):
    return f"🛡️ <b>{p.get('name') or 'پنل پاسارگارد'}</b>\n\nوضعیت: {'🟢 فعال' if p.get('enabled') else '🔴 غیرفعال'}\nآدرس: <code>{p.get('base_url') or '-'}</code>\nروش اتصال: Username / Password"

@router.callback_query(F.data.in_({'admin_pasargad', 'admin_pasargad_panels'}))
async def open_panels(c):
    if not _is_admin(c.from_user.id): return
    await c.message.edit_text('🛡️ <b>مدیریت پنل‌های پاسارگارد</b>\n\nهر پنل یک نمونه مستقل است.',reply_markup=admin_pasargad_panels_keyboard(db.list_vpn_panels('pasargad'))); await c.answer()
@router.message(F.text=='🛡️ مدیریت پنل‌های پاسارگارد')
async def open_panels_msg(m,state):
    if not _is_admin(m.from_user.id): return
    await state.clear(); await answer_rich(m,'🛡️ <b>مدیریت پنل‌های پاسارگارد</b>\n\nهر پنل یک نمونه مستقل است.',reply_markup=admin_pasargad_panels_keyboard(db.list_vpn_panels('pasargad')))
@router.callback_query(F.data=='pp_add')
async def add_start(c,state):
    if not _is_admin(c.from_user.id): return
    await state.clear(); await state.update_data(pp_mode='add'); await state.set_state(AdminStates.waiting_vpn_panel_name); await c.message.edit_text('➕ نام پنل را بفرستید:'); await c.answer()
@router.message(AdminStates.waiting_vpn_panel_name)
async def name_input(m,state):
    if not _is_admin(m.from_user.id): return
    d=await state.get_data(); v=(m.text or '').strip()
    if not v:return await m.answer('❌ مقدار نمی‌تواند خالی باشد.')
    if d.get('pp_mode')=='edit':
        db.update_vpn_panel(int(d['pp_id']),**{d['pp_field']:v}); await state.clear(); return await m.answer('✅ ذخیره شد.',reply_markup=admin_pasargad_panel_detail_keyboard(db.get_vpn_panel(int(d['pp_id']))))
    await state.update_data(pp_name=v); await state.set_state(AdminStates.waiting_vpn_panel_url); await m.answer('🌐 آدرس پایه پنل را بفرستید:')
@router.message(AdminStates.waiting_vpn_panel_url)
async def url_input(m,state):
    if not _is_admin(m.from_user.id):return
    v=(m.text or '').strip().rstrip('/')
    if not v.startswith(('http://','https://')):return await m.answer('❌ آدرس نامعتبر است.')
    await state.update_data(pp_url=v); await state.set_state(AdminStates.waiting_vpn_panel_username); await m.answer('👤 نام کاربری پنل را بفرستید:')
@router.message(AdminStates.waiting_vpn_panel_username)
async def user_input(m,state):
    if not _is_admin(m.from_user.id):return
    await state.update_data(pp_user=(m.text or '').strip()); await state.set_state(AdminStates.waiting_vpn_panel_password); await m.answer('🔑 رمز عبور پنل را بفرستید:')
@router.message(AdminStates.waiting_vpn_panel_password)
async def pass_input(m,state):
    if not _is_admin(m.from_user.id):return
    d=await state.get_data(); pid=db.add_vpn_panel(d['pp_name'],d['pp_url'],d['pp_user'],(m.text or '').strip()); await state.clear(); ok,_,msg=await vpn_panel.test_connection(pid); p=db.get_vpn_panel(pid); await m.answer(('✅ اتصال موفق بود.' if ok else '⚠️ پنل ذخیره شد ولی تست اتصال ناموفق بود:\n'+msg),reply_markup=admin_pasargad_panel_detail_keyboard(p))
@router.callback_query(F.data.startswith('pp_detail|'))
async def detail(c):
    if not _is_admin(c.from_user.id):return
    p=db.get_vpn_panel(int(c.data.split('|')[1]));
    if not p:return await c.answer('پنل پیدا نشد.',show_alert=True)
    await c.message.edit_text(ptext(p),reply_markup=admin_pasargad_panel_detail_keyboard(p)); await c.answer()
@router.callback_query(F.data.startswith('pp_test|'))
async def test(c):
    if not _is_admin(c.from_user.id):return
    await c.answer('⏳ در حال تست اتصال...'); ok,_,msg=await vpn_panel.test_connection(int(c.data.split('|')[1])); await c.message.answer(('✅ ' if ok else '❌ ')+msg)
@router.callback_query(F.data.startswith('pp_toggle|'))
async def toggle(c):
    if not _is_admin(c.from_user.id):return
    pid=int(c.data.split('|')[1]); p=db.get_vpn_panel(pid); db.update_vpn_panel(pid,enabled=not bool(p.get('enabled'))); p=db.get_vpn_panel(pid); await c.message.edit_text(ptext(p),reply_markup=admin_pasargad_panel_detail_keyboard(p)); await c.answer()
@router.callback_query(F.data.startswith('pp_delete|'))
async def delete(c):
    if not _is_admin(c.from_user.id):return
    db.delete_vpn_panel(int(c.data.split('|')[1])); await c.message.edit_text('🗑 پنل حذف شد.',reply_markup=admin_pasargad_panels_keyboard(db.list_vpn_panels('pasargad'))); await c.answer()
@router.callback_query(F.data.startswith('pp_edit|'))
async def edit(c):
    if not _is_admin(c.from_user.id):return
    pid=int(c.data.split('|')[1]); p=db.get_vpn_panel(pid); await c.message.edit_text('✏️ مشخصه موردنظر را انتخاب کنید:',reply_markup=admin_pasargad_panel_edit_keyboard(p)); await c.answer()
@router.callback_query(F.data.startswith('pp_editfield|'))
async def editfield(c,state):
    if not _is_admin(c.from_user.id):return
    _,pid,field=c.data.split('|'); await state.update_data(pp_mode='edit',pp_id=int(pid),pp_field=field); await state.set_state(AdminStates.waiting_vpn_panel_name); await c.message.edit_text('✏️ مقدار جدید را ارسال کنید:'); await c.answer()


@router.callback_query(F.data.startswith('pp_mapping|'))
async def panel_mapping(c):
    if not _is_admin(c.from_user.id): return
    _, pid, page = c.data.split('|')
    pid, page = int(pid), int(page)
    panel = db.get_vpn_panel(pid)
    if not panel:
        return await c.answer('پنل پیدا نشد.', show_alert=True)
    all_plans = list(db.get_all_vip_plans_flat().values())
    all_plans.sort(key=lambda x: (int(x.get('category_id') or 0), int(x.get('sort_order') or 0), int(x.get('id') or 0)))
    mappings = {int(p['scope_id']): p for p in db.list_panel_plan_maps('vip_plan') if str(p.get('panel_id')) == str(pid)}
    await c.message.edit_text(
        f"🔀 <b>نگاشت پلن‌ها به پنل «{panel.get('name') or pid}»</b>\n\n"
        "هر پلن را انتخاب کن و بعد یکی از Templateهای همین پنل را برای ساخت سرویس انتخاب کن.\n"
        "حجم، مدت و محدودیت کاربر از خود پلن ربات می‌آید؛ Template فقط تنظیمات پنل مثل پروتکل/این‌باند/گروه را تأمین می‌کند.",
        reply_markup=admin_pasargad_panel_mapping_keyboard(pid, all_plans, mappings, page=page),
    )
    await c.answer()

@router.callback_query(F.data.startswith('pp_mapplan|'))
async def panel_map_plan(c):
    if not _is_admin(c.from_user.id): return
    _, pid, plan_id, page = c.data.split('|')
    pid, plan_id, page = int(pid), int(plan_id), int(page)
    panel = db.get_vpn_panel(pid); plan = None
    for p in db.get_all_vip_plans_flat().values():
        if int(p.get('id')) == plan_id: plan = p; break
    if not panel or not plan:
        return await c.answer('پنل یا پلن پیدا نشد.', show_alert=True)
    ok, templates, msg = await vpn_panel.get_templates(pid)
    if not ok:
        return await c.answer('خطا در دریافت Templateها: '+str(msg), show_alert=True)
    row = db.get_panel_plan_map('vip_plan', plan_id)
    current_ref = row.get('remote_ref') if row and str(row.get('panel_id')) == str(pid) else None
    await c.message.edit_text(
        f"📦 <b>Template پلن «{plan.get('name')}»</b>\n\n"
        f"پنل: <b>{panel.get('name') or pid}</b>\n"
        "یکی از Templateهای همین پنل را انتخاب کن:",
        reply_markup=admin_pasargad_panel_template_map_keyboard(pid, plan_id, templates, current_ref),
    )
    await c.answer()

@router.callback_query(F.data.startswith('pp_maptest|'))
async def panel_map_test(c):
    if not _is_admin(c.from_user.id): return
    pid = int(c.data.split('|')[1])
    panel = db.get_vpn_panel(pid)
    if not panel:
        return await c.answer('پنل پیدا نشد.', show_alert=True)
    ok, templates, msg = await vpn_panel.get_templates(pid)
    if not ok:
        return await c.answer('خطا در دریافت Templateها: ' + str(msg), show_alert=True)
    row = db.get_panel_plan_map('free_test', 0)
    current_ref = row.get('remote_ref') if row and str(row.get('panel_id')) == str(pid) else None
    await c.message.edit_text(
        f"🧪 <b>Template تست رایگان</b>\n\nپنل: <b>{panel.get('name') or pid}</b>\nیکی از Templateهای همین پنل را برای تست رایگان انتخاب کن:",
        reply_markup=admin_pasargad_panel_template_map_keyboard(pid, 0, templates, current_ref),
    )
    await c.answer()

@router.callback_query(F.data.startswith('pp_maptemplate|'))
async def panel_map_template(c):
    if not _is_admin(c.from_user.id): return
    _, pid, scope_id, tid = c.data.split('|')
    pid, scope_id, tid = int(pid), int(scope_id), int(tid)
    panel = db.get_vpn_panel(pid)
    if not panel:
        return await c.answer('پنل پیدا نشد.', show_alert=True)
    ok, template, msg = await vpn_panel.get_template(tid, pid)
    if not ok:
        return await c.answer('Template پیدا نشد: ' + str(msg), show_alert=True)
    template_name = template.get('name') or template.get('remark') or str(tid)
    if scope_id == 0:
        db.set_panel_plan_map('free_test', 0, pid, str(tid), template_name)
        await c.answer('✅ نگاشت تست رایگان ذخیره شد.', show_alert=True)
        all_plans = list(db.get_all_vip_plans_flat().values())
        mappings = {int(x['scope_id']): x for x in db.list_panel_plan_maps('vip_plan') if str(x.get('panel_id')) == str(pid)}
        await c.message.edit_text('✅ تست رایگان به Template «' + template_name + '» پنل «' + (panel.get('name') or str(pid)) + '» متصل شد.', reply_markup=admin_pasargad_panel_mapping_keyboard(pid, all_plans, mappings, page=0))
        return
    plan_id = scope_id
    plan = next((x for x in db.get_all_vip_plans_flat().values() if int(x.get('id')) == plan_id), None)
    if not plan:
        return await c.answer('پلن پیدا نشد.', show_alert=True)
    db.set_panel_plan_map('vip_plan', plan_id, pid, str(tid), template_name)
    await c.answer('✅ نگاشت ذخیره شد.', show_alert=True)
    await c.message.edit_text(
        f"✅ پلن «{plan.get('name')}» از این به بعد از Template «{template_name}» پنل «{panel.get('name') or pid}» تغذیه می‌شود.\n\n"
        "هنگام ساخت سرویس، تنظیمات Template از پنل خوانده می‌شود و حجم/مدت/HWID از خود پلن ربات اعمال می‌شود.",
        reply_markup=admin_pasargad_panel_mapping_keyboard(pid, list(db.get_all_vip_plans_flat().values()), {int(plan_id): db.get_panel_plan_map('vip_plan', plan_id)}, page=0),
    )

@router.callback_query(F.data.startswith('pp_mapclear|'))
async def panel_map_clear(c):
    if not _is_admin(c.from_user.id): return
    _, pid, plan_id = c.data.split('|')
    pid, plan_id = int(pid), int(plan_id)
    row = db.get_panel_plan_map('vip_plan', plan_id)
    if row and str(row.get('panel_id')) == str(pid):
        db.delete_panel_plan_map('vip_plan', plan_id)
    await c.answer('🗑 نگاشت حذف شد.', show_alert=True)
    all_plans = list(db.get_all_vip_plans_flat().values())
    all_plans.sort(key=lambda x: (int(x.get('category_id') or 0), int(x.get('sort_order') or 0), int(x.get('id') or 0)))
    mappings = {int(p['scope_id']): p for p in db.list_panel_plan_maps('vip_plan') if str(p.get('panel_id')) == str(pid)}
    await c.message.edit_text(f"🔀 <b>نگاشت پلن‌ها به پنل</b>\n\nپلن موردنظر را انتخاب کن:", reply_markup=admin_pasargad_panel_mapping_keyboard(pid, all_plans, mappings, page=0))

@router.callback_query(F.data == 'noop')
async def noop(c):
    await c.answer()

@router.callback_query(F.data.startswith('vipplanpanel|'))
async def plan_panel(c):
    if not _is_admin(c.from_user.id):return
    key=c.data.split('|',1)[1]; plan=db.get_vip_plan(key); row=db.get_panel_plan_map('vip_plan',plan['id']) if plan else None
    if not plan:return await c.answer('پلن پیدا نشد.',show_alert=True)
    await c.message.edit_text(f"🖥️ پنل پلن «{plan['name']}» را انتخاب کنید:",reply_markup=admin_vip_plan_panel_keyboard(key,db.list_vpn_panels('pasargad',True),row.get('panel_id') if row else None)); await c.answer()
@router.callback_query(F.data.startswith('vipplanpanelset|'))
async def plan_panel_set(c):
    if not _is_admin(c.from_user.id):return
    _,key,pid=c.data.split('|'); plan=db.get_vip_plan(key); p=db.get_vpn_panel(int(pid))
    if not plan or not p:return await c.answer('پلن یا پنل پیدا نشد.',show_alert=True)
    ok,ts,msg=await vpn_panel.get_templates(int(pid))
    if not ok:return await c.answer('خطا در دریافت تمپلیت‌ها: '+msg,show_alert=True)
    await c.message.edit_text(f"📦 تمپلیت پنل «{p['name']}» را انتخاب کنید:",reply_markup=admin_vip_plan_panel_template_keyboard(key,int(pid),ts)); await c.answer()
@router.callback_query(F.data.startswith('vipplanpaneltemplate|'))
async def template_set(c):
    if not _is_admin(c.from_user.id):return
    _,key,pid,tid=c.data.split('|'); plan=db.get_vip_plan(key); p=db.get_vpn_panel(int(pid)); ok,t,msg=await vpn_panel.get_template(int(tid),int(pid))
    if not plan or not p or not ok:return await c.answer(msg or 'اطلاعات نامعتبر.',show_alert=True)
    db.set_panel_plan_map('vip_plan',plan['id'],int(pid),str(tid),t.get('name') or t.get('remark') or str(tid)); await c.answer('✅ نگاشت ذخیره شد.',show_alert=True); cat=db.get_vip_category(plan['category_id']); await c.message.edit_text(f"✅ پلن «{plan['name']}» به «{p['name']}» متصل شد.",reply_markup=admin_vip_plan_detail_keyboard(key,cat['key']))
@router.callback_query(F.data.startswith('vipplanpanelclear|'))
async def clear(c):
    if not _is_admin(c.from_user.id):return
    key=c.data.split('|',1)[1]; plan=db.get_vip_plan(key)
    if plan: db.delete_panel_plan_map('vip_plan',plan['id'])
    cat=db.get_vip_category(plan['category_id']); await c.message.edit_text('🚫 اتصال پنل این پلن حذف شد.',reply_markup=admin_vip_plan_detail_keyboard(key,cat['key'])); await c.answer()
