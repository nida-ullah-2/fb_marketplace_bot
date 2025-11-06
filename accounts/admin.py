from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils import timezone
from .models import CustomUser, FacebookAccount
import os


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Custom User Admin with approval system"""
    list_display = ('username', 'email', 'first_name', 'last_name',
                    'is_approved_display', 'is_staff', 'date_joined')
    list_filter = ('is_approved', 'is_staff', 'is_superuser', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)

    # Add approval fields to fieldsets
    fieldsets = UserAdmin.fieldsets + (
        ('Approval Information', {
            'fields': ('is_approved', 'approved_at', 'approved_by', 'rejection_reason')
        }),
    )

    readonly_fields = ('approved_at', 'approved_by',
                       'date_joined', 'last_login')

    actions = ['approve_users', 'reject_users']

    def is_approved_display(self, obj):
        """Display approval status with color"""
        if obj.is_approved:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Approved</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ Pending</span>'
            )

    is_approved_display.short_description = 'Approval Status'

    def approve_users(self, request, queryset):
        """Approve selected users"""
        count = 0
        for user in queryset.filter(is_approved=False):
            user.approve(request.user)
            count += 1

        self.message_user(
            request,
            f'{count} user(s) have been approved successfully.'
        )

    approve_users.short_description = 'Approve selected users'

    def reject_users(self, request, queryset):
        """Reject/unapprove selected users"""
        count = queryset.filter(is_approved=True).update(
            is_approved=False,
            approved_at=None,
            approved_by=None
        )

        self.message_user(
            request,
            f'{count} user(s) have been rejected/unapproved.'
        )

    reject_users.short_description = 'Reject/unapprove selected users'

    def save_model(self, request, obj, form, change):
        """Auto-set approved_by when approving"""
        if change and 'is_approved' in form.changed_data:
            if obj.is_approved:
                obj.approved_at = timezone.now()
                obj.approved_by = request.user
                obj.rejection_reason = None
            else:
                obj.approved_at = None
                obj.approved_by = None

        super().save_model(request, obj, form, change)


@admin.register(FacebookAccount)
class FacebookAccountAdmin(admin.ModelAdmin):
    list_display = ['email', 'user', 'session_exists',
                    'post_count', 'created_at']
    list_filter = ['created_at', 'user']
    search_fields = ['email', 'user__username', 'user__email']
    readonly_fields = ['created_at', 'get_password', 'session_status']
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        """Filter accounts by user - superusers see all, staff see only their own"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

    def session_exists(self, obj):
        """Check if session file exists"""
        session_file = f"sessions/{obj.email.replace('@', '_').replace('.', '_')}.json"
        return os.path.exists(session_file)
    session_exists.boolean = True
    session_exists.short_description = 'Session File'

    def post_count(self, obj):
        """Count posts for this account"""
        return obj.marketplacepost_set.count()
    post_count.short_description = 'Posts'

    def session_status(self, obj):
        """Display detailed session status"""
        session_file = f"sessions/{obj.email.replace('@', '_').replace('.', '_')}.json"
        if os.path.exists(session_file):
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Session exists</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ No session</span>'
            )
    session_status.short_description = 'Session Status'
