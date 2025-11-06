from django.db import models
from django.conf import settings
from accounts.models import FacebookAccount


class PostAnalytics(models.Model):
    """
    Permanent analytics tracking for posts.
    Records every post creation and posting action.
    Data is never deleted to maintain lifetime statistics.
    """
    ACTION_CHOICES = [
        ('created', 'Post Created'),
        ('posted', 'Post Posted to Facebook'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    account = models.ForeignKey(
        FacebookAccount, on_delete=models.SET_NULL, null=True, blank=True)
    # Reference to MarketplacePost
    post_id = models.IntegerField(null=True, blank=True)
    post_title = models.CharField(max_length=255)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    # Additional metadata
    account_email = models.EmailField()  # Store email in case account is deleted
    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'action', 'timestamp'],
                         name='user_action_time_idx'),
            models.Index(fields=['user', 'timestamp'], name='user_time_idx'),
            models.Index(fields=['account', 'action'],
                         name='account_action_idx'),
            models.Index(fields=['action', 'timestamp'],
                         name='action_time_idx'),
        ]
        ordering = ['-timestamp']
        verbose_name_plural = "Post Analytics"

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.post_title}"


class MarketplacePost(models.Model):
    account = models.ForeignKey(FacebookAccount, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='posts/', blank=True)
    scheduled_time = models.DateTimeField()
    posted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['posted'], name='posted_idx'),
            models.Index(fields=['scheduled_time'], name='scheduled_time_idx'),
            models.Index(fields=['account', 'posted'],
                         name='account_posted_idx'),
            models.Index(fields=['posted', 'scheduled_time'],
                         name='posted_scheduled_idx'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.account.email}"


class PostingJob(models.Model):
    """Track posting job progress for real-time updates"""
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    job_id = models.CharField(max_length=100, unique=True)
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='posting_jobs',
        null=True,  # Temporary for migration
        blank=True,
        help_text="User who started this posting job"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='queued')
    total_posts = models.IntegerField()
    completed_posts = models.IntegerField(default=0)
    failed_posts = models.IntegerField(default=0)
    current_post_id = models.IntegerField(null=True, blank=True)
    current_post_title = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True, null=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Job {self.job_id} - {self.status}"


class ErrorLog(models.Model):
    """Detailed error logging for posting failures"""
    ERROR_TYPES = [
        ('session_expired', 'Session Expired'),
        ('network_error', 'Network Error'),
        ('captcha', 'CAPTCHA Required'),
        ('rate_limit', 'Rate Limited'),
        ('validation_error', 'Validation Error'),
        ('unknown', 'Unknown Error'),
    ]

    post = models.ForeignKey(
        MarketplacePost, on_delete=models.CASCADE, related_name='error_logs')
    error_type = models.CharField(
        max_length=50, choices=ERROR_TYPES, default='unknown')
    error_message = models.TextField()
    stack_trace = models.TextField(blank=True, null=True)
    screenshot = models.ImageField(
        upload_to='error_screenshots/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Error for {self.post.title} - {self.error_type}"
