from django.contrib import admin
from .models import MarketplacePost, PostAnalytics, PostingJob, ErrorLog
from django.urls import reverse

# admin.site.register(MarketplacePost)


@admin.register(MarketplacePost)
class MarketplacePostAdmin(admin.ModelAdmin):
    list_display = ['title', 'account', 'price',
                    'posted', 'created_at']
    list_filter = ['posted', 'created_at']
    search_fields = ['title', 'description', 'account__email']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']

    def get_queryset(self, request):
        """Filter posts by user - superusers see all, staff see only their own"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(account__user=request.user)


@admin.register(PostAnalytics)
class PostAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['post_title', 'user',
                    'account_email', 'action', 'timestamp']
    list_filter = ['action', 'timestamp', 'user']
    search_fields = ['post_title', 'account_email', 'user__email']
    date_hierarchy = 'timestamp'
    readonly_fields = ['user', 'account', 'post_id', 'post_title',
                       'action', 'timestamp', 'account_email', 'price']

    def get_queryset(self, request):
        """Filter analytics by user - superusers see all, staff see only their own"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

    def has_add_permission(self, request):
        # Prevent manual creation of analytics records
        return False

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of analytics records to maintain permanent history
        return False


@admin.register(PostingJob)
class PostingJobAdmin(admin.ModelAdmin):
    list_display = ['job_id', 'user', 'status', 'total_posts',
                    'completed_posts', 'failed_posts', 'started_at']
    list_filter = ['status', 'started_at', 'user']
    search_fields = ['job_id', 'user__username', 'user__email']
    readonly_fields = ['job_id', 'user', 'total_posts', 'completed_posts',
                       'failed_posts', 'started_at', 'completed_at']

    def get_queryset(self, request):
        """Filter posting jobs by user - superusers see all, staff see only their own"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ['post', 'error_type', 'created_at']
    list_filter = ['error_type', 'created_at']
    search_fields = ['post__title', 'error_message']
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        """Filter error logs by user - superusers see all, staff see only their own"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(post__account__user=request.user)
