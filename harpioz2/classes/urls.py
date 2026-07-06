from django.urls import path
from . import views

urlpatterns = [
    # Admin auth
    path('admin-login/', views.admin_login_view, name='admin_login'),
    path('admin-logout/', views.admin_logout_view, name='admin_logout'),

    # Admin dashboard & class management
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/create/', views.create_class, name='create_class'),
    path('admin/class/<str:class_id>/created/', views.class_created, name='class_created'),
    path('admin/class/<str:class_id>/', views.admin_class_detail, name='admin_class_detail'),
    path('admin/class/<str:class_id>/status/', views.admin_class_status, name='admin_class_status'),
    path('admin/class/<str:class_id>/delete/', views.admin_delete_class, name='admin_delete_class'),
    path('admin/class/<str:class_id>/broadcast/', views.admin_broadcast, name='admin_broadcast'),

    # Student join flow
    path('class/<str:class_id>/', views.join_class, name='join_class'),
    path('class/<str:class_id>/room/', views.class_room, name='class_room'),

    # Chat API
    path('class/<str:class_id>/chat/', views.chat_messages, name='chat_messages'),
    path('class/<str:class_id>/chat/send/', views.chat_send, name='chat_send'),
    path('class/<str:class_id>/chat/<int:msg_id>/delete/', views.chat_delete, name='chat_delete'),
    path('class/<str:class_id>/participants/', views.class_participants, name='class_participants'),

    # Admin settings
    path('admin/settings/', views.admin_settings, name='admin_settings'),

    # Public pages
    path('privacy/', views.privacy_view, name='privacy'),
    path('terms/', views.terms_view, name='terms'),
]
