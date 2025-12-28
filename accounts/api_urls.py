from django.urls import path
from . import api_views
from postings import realtime_views

app_name = 'accounts_api'

urlpatterns = [
    # Authentication
    path('auth/register/', api_views.register, name='register'),
    path('auth/login/', api_views.login, name='login'),
    path('auth/user/', api_views.get_user, name='get_user'),
    path('auth/change-password/', api_views.change_password, name='change_password'),

    # User management (Admin only)
    path('auth/users/', api_views.get_all_users, name='get_all_users'),
    path('auth/users/<int:user_id>/approve/',
         api_views.approve_user, name='approve_user'),
    path('auth/users/<int:user_id>/disapprove/',
         api_views.disapprove_user, name='disapprove_user'),
    path('auth/users/<int:user_id>/update-permissions/',
         api_views.update_user_permissions, name='update_user_permissions'),
    path('auth/users/<int:user_id>/reset-password/',
         api_views.reset_user_password, name='reset_user_password'),

    # Dashboard stats
    path('stats/dashboard/', api_views.dashboard_stats, name='dashboard_stats'),

    # Facebook accounts
    path('accounts/', api_views.FacebookAccountListCreateView.as_view(),
         name='account_list'),
    path('accounts/add-with-login/', api_views.add_facebook_account_with_login,
         name='add_account_with_login'),
    path('accounts/add-manual-login/', api_views.add_facebook_account_manual_login,
         name='add_account_manual_login'),
    path('accounts/bulk-upload/', api_views.bulk_upload_accounts_with_login,
         name='bulk_upload_accounts'),
    path('accounts/import-session/', api_views.import_session,
         name='import_session'),
    path('accounts/<int:pk>/update-session/', api_views.update_account_session,
         name='update_account_session'),
    path('accounts/<int:pk>/',
         api_views.FacebookAccountDetailView.as_view(), name='account_detail'),

    # Health checks
    path('accounts/health-check/',
         realtime_views.health_check_accounts, name='health_check_accounts'),
    path('accounts/<int:account_id>/validate-session/',
         realtime_views.validate_account_session, name='validate_session'),
]
