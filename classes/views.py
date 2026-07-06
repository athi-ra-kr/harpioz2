import json
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.timezone import localtime
from django.views.decorators.http import require_POST

from .models import ChatMessage, LiveClass, Participant


# ─── Admin: Login ────────────────────────────────────────────────────────────

def admin_login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')
    error = None
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user and user.is_staff:
            login(request, user)
            return redirect('admin_dashboard')
        error = 'Invalid credentials.'
    return render(request, 'admin_login.html', {'error': error})


def admin_logout_view(request):
    logout(request)
    return redirect('admin_login')


# ─── Admin: Dashboard ─────────────────────────────────────────────────────────

@login_required(login_url='/admin-login/')
def admin_dashboard(request):
    classes = LiveClass.objects.all()
    return render(request, 'admin_dashboard.html', {'classes': classes})


# ─── Admin: Create Class ──────────────────────────────────────────────────────

@login_required(login_url='/admin-login/')
def create_class(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        scheduled_at = request.POST.get('scheduled_at') or None
        is_instant = request.POST.get('type') == 'instant'

        lc = LiveClass.objects.create(
            title=title or 'Untitled Class',
            scheduled_at=timezone.now() if is_instant else scheduled_at,
            status='live' if is_instant else 'scheduled',
        )
        return redirect('class_created', class_id=lc.class_id)
    return render(request, 'create_class.html')


@login_required(login_url='/admin-login/')
def class_created(request, class_id):
    lc = get_object_or_404(LiveClass, class_id=class_id)
    join_url = request.build_absolute_uri(f'/class/{class_id}/')
    return render(request, 'class_created.html', {'lc': lc, 'join_url': join_url})


# ─── Admin: Manage Class ──────────────────────────────────────────────────────

@login_required(login_url='/admin-login/')
def admin_class_detail(request, class_id):
    lc = get_object_or_404(LiveClass, class_id=class_id)
    join_url = request.build_absolute_uri(f'/class/{class_id}/')
    participants = lc.participants.all()
    return render(request, 'admin_class_detail.html', {
        'lc': lc, 'join_url': join_url, 'participants': participants
    })


@login_required(login_url='/admin-login/')
@require_POST
def admin_class_status(request, class_id):
    lc = get_object_or_404(LiveClass, class_id=class_id)
    status = request.POST.get('status')
    if status in ['scheduled', 'live', 'ended']:
        lc.status = status
        lc.save()
    return redirect('admin_class_detail', class_id=class_id)


@login_required(login_url='/admin-login/')
@require_POST
def admin_delete_class(request, class_id):
    lc = get_object_or_404(LiveClass, class_id=class_id)
    lc.delete()
    return redirect('admin_dashboard')


# ─── Admin: Broadcast ─────────────────────────────────────────────────────────

@login_required(login_url='/admin-login/')
def admin_broadcast(request, class_id):
    lc = get_object_or_404(LiveClass, class_id=class_id)

    # Always mark as live when admin opens broadcast page
    # Also generate a fresh stream_key so MediaMTX treats it as a new stream
    # (avoids stale session causing black screen on re-broadcast)
    if lc.status != 'live':
        lc.status = 'live'
        # Fresh stream key = new MediaMTX path, no stale state
        import random, string
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        lc.stream_key = f"class-{lc.class_id}-{suffix}"
        lc.save(update_fields=['status', 'stream_key'])

    streaming_enabled = settings.STREAMING_ENABLED
    mediamtx_base = settings.MEDIAMTX_BASE_URL
    whip_url = f"{mediamtx_base}/{lc.stream_key}/whip" if streaming_enabled and mediamtx_base else None
    whep_url = f"{mediamtx_base}/{lc.stream_key}/whep" if streaming_enabled and mediamtx_base else None
    return render(request, 'broadcast.html', {
        'lc': lc, 'whip_url': whip_url, 'whep_url': whep_url, 'streaming_enabled': streaming_enabled
    })


# ─── Student: Join Page ───────────────────────────────────────────────────────

def join_class(request, class_id):
    lc = get_object_or_404(LiveClass, class_id=class_id)

    if lc.status == 'ended':
        return render(request, 'class_ended.html', {'lc': lc})

    # Already joined this session?
    participant_id = request.session.get(f'participant_{class_id}')
    if participant_id:
        try:
            p = Participant.objects.get(id=participant_id, live_class=lc)
            return redirect('class_room', class_id=class_id)
        except Participant.DoesNotExist:
            pass

    error = None
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        mobile = request.POST.get('mobile', '').strip()
        password = request.POST.get('password', '').strip()

        if not all([name, email, mobile, password]):
            error = 'All fields are required.'
        elif password != lc.password:
            error = 'Incorrect class password. Please check with your instructor.'
        else:
            p = Participant.objects.create(
                live_class=lc, name=name, email=email, mobile=mobile,
                session_key=request.session.session_key or ''
            )
            request.session[f'participant_{class_id}'] = p.id
            request.session.modified = True
            return redirect('class_room', class_id=class_id)

    return render(request, 'join_class.html', {'lc': lc, 'error': error})


# ─── Student: Class Room ──────────────────────────────────────────────────────

def class_room(request, class_id):
    lc = get_object_or_404(LiveClass, class_id=class_id)

    # Admin can enter without joining
    is_admin = request.user.is_authenticated and request.user.is_staff

    participant_id = request.session.get(f'participant_{class_id}')
    participant = None
    if participant_id:
        try:
            participant = Participant.objects.get(id=participant_id, live_class=lc)
        except Participant.DoesNotExist:
            pass

    if not is_admin and not participant:
        return redirect('join_class', class_id=class_id)

    streaming_enabled = settings.STREAMING_ENABLED
    mediamtx_base = settings.MEDIAMTX_BASE_URL
    whep_url = f"{mediamtx_base}/{lc.stream_key}/whep" if streaming_enabled and mediamtx_base else None

    return render(request, 'class_room.html', {
        'lc': lc, 'participant': participant, 'is_admin': is_admin,
        'whep_url': whep_url, 'streaming_enabled': streaming_enabled,
    })


# ─── Chat API ─────────────────────────────────────────────────────────────────

def chat_messages(request, class_id):
    lc = get_object_or_404(LiveClass, class_id=class_id)
    since = request.GET.get('since', 0)
    msgs = ChatMessage.objects.filter(
        live_class=lc, is_deleted=False, id__gt=since
    ).values('id', 'participant_name', 'is_admin', 'text', 'created_at')
    data = [{'id': m['id'], 'name': m['participant_name'],
              'is_admin': m['is_admin'], 'text': m['text'],
              'time': localtime(m['created_at']).strftime('%H:%M')} for m in msgs]
    return JsonResponse({'messages': data})


@require_POST
def chat_send(request, class_id):
    lc = get_object_or_404(LiveClass, class_id=class_id)
    if not lc.chat_enabled:
        return JsonResponse({'error': 'Chat disabled'}, status=403)

    text = request.POST.get('text', '').strip()
    if not text:
        return JsonResponse({'error': 'Empty message'}, status=400)

    is_admin = request.user.is_authenticated and request.user.is_staff
    if is_admin:
        name = 'Instructor'
    else:
        participant_id = request.session.get(f'participant_{class_id}')
        if not participant_id:
            return JsonResponse({'error': 'Not joined'}, status=403)
        try:
            p = Participant.objects.get(id=participant_id, live_class=lc)
            name = p.name
        except Participant.DoesNotExist:
            return JsonResponse({'error': 'Not joined'}, status=403)

    msg = ChatMessage.objects.create(live_class=lc, participant_name=name, is_admin=is_admin, text=text)
    return JsonResponse({'id': msg.id, 'name': name, 'text': text,
                         'is_admin': is_admin, 'time': localtime(msg.created_at).strftime('%H:%M')})


@login_required(login_url='/admin-login/')
@require_POST
def chat_delete(request, class_id, msg_id):
    msg = get_object_or_404(ChatMessage, id=msg_id, live_class__class_id=class_id)
    msg.is_deleted = True
    msg.save()
    return JsonResponse({'ok': True})


# ─── Admin: Site Settings ─────────────────────────────────────────────────────

@login_required(login_url='/admin-login/')
def admin_settings(request):
    from .models import SiteSettings
    settings_obj = SiteSettings.get()
    saved = False
    if request.method == 'POST':
        settings_obj.site_title = request.POST.get('site_title', 'Harpioz').strip()
        settings_obj.site_description = request.POST.get('site_description', '').strip()
        settings_obj.privacy_policy = request.POST.get('privacy_policy', '').strip()
        settings_obj.terms = request.POST.get('terms', '').strip()
        if 'logo' in request.FILES:
            settings_obj.logo = request.FILES['logo']
        if 'favicon' in request.FILES:
            settings_obj.favicon = request.FILES['favicon']
        settings_obj.save()
        saved = True
    return render(request, 'admin_settings.html', {'s': settings_obj, 'saved': saved})


# ─── Public: Privacy & Terms ─────────────────────────────────────────────────

def privacy_view(request):
    from .models import SiteSettings
    s = SiteSettings.get()
    return render(request, 'public_page.html', {'title': 'Privacy Policy', 'content': s.privacy_policy, 's': s})


def terms_view(request):
    from .models import SiteSettings
    s = SiteSettings.get()
    return render(request, 'public_page.html', {'title': 'Terms & Conditions', 'content': s.terms, 's': s})


# ─── Participants API (for broadcast page) ────────────────────────────────────

@login_required(login_url='/admin-login/')
def class_participants(request, class_id):
    lc = get_object_or_404(LiveClass, class_id=class_id)
    data = [{
        'name': p.name,
        'email': p.email,
        'mobile': p.mobile,
        'joined': localtime(p.joined_at).strftime('%H:%M'),
    } for p in lc.participants.all()]
    return JsonResponse({'participants': data})


# ─── Stream info API (for viewer to get current WHEP URL) ─────────────────────

def stream_info(request, class_id):
    from django.conf import settings as django_settings
    lc = get_object_or_404(LiveClass, class_id=class_id)
    mediamtx_base = django_settings.MEDIAMTX_BASE_URL
    streaming_enabled = django_settings.STREAMING_ENABLED
    whep_url = f"{mediamtx_base}/{lc.stream_key}/whep" if streaming_enabled and mediamtx_base else None
    return JsonResponse({'whep_url': whep_url, 'status': lc.status})
