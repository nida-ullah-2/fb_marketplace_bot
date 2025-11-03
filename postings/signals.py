from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import MarketplacePost, PostAnalytics


# Store the previous state of the post before saving
@receiver(pre_save, sender=MarketplacePost)
def store_previous_posted_state(sender, instance, **kwargs):
    """
    Store the previous 'posted' state before the post is saved.
    This helps us detect when the posted status changes.
    """
    if instance.pk:  # Only for existing posts (not new ones)
        try:
            previous = MarketplacePost.objects.get(pk=instance.pk)
            instance._previous_posted = previous.posted
        except MarketplacePost.DoesNotExist:
            instance._previous_posted = False
    else:
        instance._previous_posted = False


@receiver(post_save, sender=MarketplacePost)
def track_post_analytics(sender, instance, created, **kwargs):
    """
    Automatically track analytics when posts are created or posted.
    This tracks EVERY time a post is marked as posted, even if edited multiple times.
    This provides complete history of all posting activities.
    """
    user = instance.account.user

    # Track post creation (only once when created)
    if created:
        PostAnalytics.objects.create(
            user=user,
            account=instance.account,
            post_id=instance.id,
            post_title=instance.title,
            action='created',
            account_email=instance.account.email,
            price=instance.price
        )

    # Track EVERY time post is marked as posted (including re-posts/edits)
    # This creates a new analytics entry each time, building complete history
    if not created and instance.posted:
        # Check if the posted status changed from False to True
        previous_posted = getattr(instance, '_previous_posted', False)

        # Track when status changes from False to True (new posting)
        if not previous_posted:
            PostAnalytics.objects.create(
                user=user,
                account=instance.account,
                post_id=instance.id,
                post_title=instance.title,
                action='posted',
                account_email=instance.account.email,
                price=instance.price
            )
