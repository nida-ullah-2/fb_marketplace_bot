from django.core.management.base import BaseCommand
from postings.models import MarketplacePost, PostingJob, ErrorLog
from automation.sequential_browser_manager import post_to_marketplace_sequential
from django.utils import timezone
from django.db.models import QuerySet, Manager
from django.core.files.base import ContentFile
import os
import uuid
import traceback


class Command(BaseCommand):
    help = 'Posts scheduled marketplace listings to Facebook'

    def add_arguments(self, parser):
        """Add command line arguments"""
        parser.add_argument(
            '--post-ids',
            type=str,
            help='Comma-separated list of post IDs to publish (e.g., "1,2,3")',
            dest='post_ids'
        )
        parser.add_argument(
            '--job-id',
            type=str,
            help='Job ID for tracking progress',
            dest='job_id'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID who initiated the posting job',
            dest='user_id'
        )

    def handle(self, *args, **options):
        print("Checking for posts to publish...")

        # Check if specific post IDs were provided
        post_ids_str = options.get('post_ids')
        job_id = options.get('job_id') or str(uuid.uuid4())
        user_id = options.get('user_id')

        if post_ids_str:
            # Parse comma-separated post IDs
            try:
                post_ids = [int(id.strip()) for id in post_ids_str.split(',')]
                print(f"Publishing specific posts: {post_ids}")

                # Get posts with specific IDs that haven't been posted
                posts: QuerySet[MarketplacePost] = MarketplacePost.objects.filter(
                    id__in=post_ids,
                    posted=False
                )
            except ValueError:
                print(f"Error: Invalid post IDs format: {post_ids_str}")
                return
        else:
            # Get all posts that are scheduled for now or earlier and haven't been posted
            posts: QuerySet[MarketplacePost] = MarketplacePost.objects.filter(
                scheduled_time__lte=timezone.now(),
                posted=False
            )

        total_posts = posts.count()
        print(f"Found {total_posts} posts to publish")

        if total_posts == 0:
            print("No posts found to publish. Make sure you have:")
            print("1. Created posts in the admin interface")
            print("2. Set scheduled_time to a past or current time")
            print("3. Set posted=False")
            return

        # Create posting job for tracking
        posting_job_data = {
            'job_id': job_id,
            'status': 'running',
            'total_posts': total_posts,
            'completed_posts': 0,
            'failed_posts': 0
        }

        # Add user if provided
        if user_id:
            from accounts.models import CustomUser
            try:
                user = CustomUser.objects.get(id=user_id)
                posting_job_data['user'] = user
            except CustomUser.DoesNotExist:
                print(f"Warning: User with ID {user_id} not found")

        posting_job = PostingJob.objects.create(**posting_job_data)

        completed = 0
        failed = 0

        # Group posts by title (product) to post same product across all accounts
        from collections import defaultdict
        posts_by_title = defaultdict(list)
        for post in posts.select_related('account'):
            posts_by_title[post.title].append(post)

        total_products = len(posts_by_title)
        total_accounts = len(set(post.account for post in posts))
        current_product_num = 0

        print(f"\n{'='*60}")
        print(
            f"Starting posting process for {total_products} product(s) across {total_accounts} account(s)")
        print(f"Strategy: Post each product to all accounts before moving to next product")
        print(f"This creates natural delays between posts to the same account")
        print(f"{'='*60}\n")

        # Process posts grouped by product (title)
        for product_title, product_posts in posts_by_title.items():
            current_product_num += 1
            product_accounts_count = len(product_posts)

            print(f"\n{'='*60}")
            print(
                f"📦 PRODUCT {current_product_num}/{total_products}: {product_title}")
            print(f"{'='*60}")
            print(
                f"Posting '{product_title}' to {product_accounts_count} account(s)")
            print(f"{'='*60}\n")

            product_completed = 0
            product_failed = 0

            for idx, post in enumerate(product_posts, 1):
                try:
                    print(
                        f"\n   └─ Account {idx}/{product_accounts_count}: {post.account.email}")

                    # Update job status
                    posting_job.current_post_id = post.id
                    posting_job.current_post_title = post.title
                    posting_job.save()

                    # Get the absolute path of the image
                    image_path = os.path.abspath(post.image.path)
                    print(f"      Image: {image_path}")

                    # ✅ ADD TO SEQUENTIAL QUEUE (will process one-by-one per user)
                    result = post_to_marketplace_sequential(
                        email=post.account.email,
                        title=post.title,
                        description=post.description,
                        price=str(post.price),
                        image_path=image_path
                    )
                    print(
                        f"      📋 Queued: {result['status']} - {result['message']}")

                    # Mark as posted
                    post.posted = True
                    post.save()

                    completed += 1
                    product_completed += 1
                    posting_job.completed_posts = completed
                    posting_job.save()

                    print(
                        f'      ✅ Successfully posted "{post.title}" to {post.account.email}')

                except Exception as e:
                    print(
                        f'      ❌ Failed to post "{post.title}" to {post.account.email}: {str(e)}')

                    # Update post status
                    post.posted = False
                    post.save()

                    # Determine error type
                    error_type = 'unknown'
                    error_str = str(e).lower()
                    if 'session' in error_str or 'cookie' in error_str or 'login' in error_str:
                        error_type = 'session_expired'
                    elif 'network' in error_str or 'connection' in error_str:
                        error_type = 'network_error'
                    elif 'captcha' in error_str:
                        error_type = 'captcha'
                    elif 'rate' in error_str or 'limit' in error_str:
                        error_type = 'rate_limit'

                    # Log detailed error
                    ErrorLog.objects.create(
                        post=post,
                        error_type=error_type,
                        error_message=str(e),
                        stack_trace=traceback.format_exc()
                    )

                    failed += 1
                    product_failed += 1
                    posting_job.failed_posts = failed
                    posting_job.save()

            # Print product completion summary
            print(f"\n{'='*60}")
            print(f"✅ Completed product: {product_title}")
            print(
                f"Product Summary: {product_completed} successful, {product_failed} failed")
            print(f"{'='*60}\n")

        # Mark job as complete
        posting_job.status = 'completed' if failed == 0 else 'failed'
        posting_job.completed_at = timezone.now()
        posting_job.error_message = f"{failed} posts failed" if failed > 0 else None
        posting_job.save()

        print(f"\n{'='*60}")
        print(f"🎉 ALL POSTING COMPLETED!")
        print(f"{'='*60}")
        print(f"Total Products Processed: {total_products}")
        print(f"Total Accounts: {total_accounts}")
        print(f"Total Posts: {total_posts}")
        print(f"✅ Successful: {completed}")
        print(f"❌ Failed: {failed}")
        print(f"Job ID: {job_id}")
        print(f"{'='*60}\n")


# from django.core.management.base import BaseCommand
# from postings.models import MarketplacePost, PostingJob, ErrorLog
# from automation.post_to_facebook import login_and_post
# from django.utils import timezone
# from django.db.models import QuerySet, Manager
# from django.core.files.base import ContentFile
# import os
# import uuid
# import traceback


# class Command(BaseCommand):
#     help = 'Posts scheduled marketplace listings to Facebook'

#     def add_arguments(self, parser):
#         """Add command line arguments"""
#         parser.add_argument(
#             '--post-ids',
#             type=str,
#             help='Comma-separated list of post IDs to publish (e.g., "1,2,3")',
#             dest='post_ids'
#         )
#         parser.add_argument(
#             '--job-id',
#             type=str,
#             help='Job ID for tracking progress',
#             dest='job_id'
#         )
#         parser.add_argument(
#             '--user-id',
#             type=int,
#             help='User ID who initiated the posting job',
#             dest='user_id'
#         )

#     def handle(self, *args, **options):
#         print("Checking for posts to publish...")

#         # Check if specific post IDs were provided
#         post_ids_str = options.get('post_ids')
#         job_id = options.get('job_id') or str(uuid.uuid4())
#         user_id = options.get('user_id')

#         if post_ids_str:
#             # Parse comma-separated post IDs
#             try:
#                 post_ids = [int(id.strip()) for id in post_ids_str.split(',')]
#                 print(f"Publishing specific posts: {post_ids}")

#                 # Get posts with specific IDs that haven't been posted
#                 posts: QuerySet[MarketplacePost] = MarketplacePost.objects.filter(
#                     id__in=post_ids,
#                     posted=False
#                 )
#             except ValueError:
#                 print(f"Error: Invalid post IDs format: {post_ids_str}")
#                 return
#         else:
#             # Get all posts that are scheduled for now or earlier and haven't been posted
#             posts: QuerySet[MarketplacePost] = MarketplacePost.objects.filter(
#                 scheduled_time__lte=timezone.now(),
#                 posted=False
#             )

#         total_posts = posts.count()
#         print(f"Found {total_posts} posts to publish")

#         if total_posts == 0:
#             print("No posts found to publish. Make sure you have:")
#             print("1. Created posts in the admin interface")
#             print("2. Set scheduled_time to a past or current time")
#             print("3. Set posted=False")
#             return

#         # Create posting job for tracking
#         posting_job_data = {
#             'job_id': job_id,
#             'status': 'running',
#             'total_posts': total_posts,
#             'completed_posts': 0,
#             'failed_posts': 0
#         }

#         # Add user if provided
#         if user_id:
#             from accounts.models import CustomUser
#             try:
#                 user = CustomUser.objects.get(id=user_id)
#                 posting_job_data['user'] = user
#             except CustomUser.DoesNotExist:
#                 print(f"Warning: User with ID {user_id} not found")

#         posting_job = PostingJob.objects.create(**posting_job_data)

#         completed = 0
#         failed = 0

#         # Group posts by account for better organization
#         from collections import defaultdict
#         posts_by_account = defaultdict(list)
#         for post in posts.select_related('account'):
#             posts_by_account[post.account].append(post)

#         total_accounts = len(posts_by_account)
#         current_account_num = 0

#         print(f"\n{'='*60}")
#         print(f"Starting posting process for {total_accounts} account(s)")
#         print(f"{'='*60}\n")

#         # Process posts grouped by account
#         for account, account_posts in posts_by_account.items():
#             current_account_num += 1
#             account_posts_count = len(account_posts)

#             print(f"\n{'='*60}")
#             print(
#                 f"📧 ACCOUNT {current_account_num}/{total_accounts}: {account.email}")
#             print(f"{'='*60}")
#             print(f"Posting initiated for account: {account.email}")
#             print(f"Posts to publish: {account_posts_count}")
#             print(f"{'='*60}\n")

#             account_completed = 0
#             account_failed = 0

#             for post in account_posts:
#                 try:
#                     print(f"\nProcessing post: {post.title}")

#                     # Update job status
#                     posting_job.current_post_id = post.id
#                     posting_job.current_post_title = post.title
#                     posting_job.save()

#                     # Get the absolute path of the image
#                     image_path = os.path.abspath(post.image.path)
#                     print(f"Image path: {image_path}")

#                     # Post to Facebook
#                     login_and_post(
#                         email=post.account.email,
#                         title=post.title,
#                         description=post.description,
#                         price=float(post.price),
#                         image_path=image_path
#                     )

#                     # Mark as posted
#                     post.posted = True
#                     post.save()

#                     completed += 1
#                     account_completed += 1
#                     posting_job.completed_posts = completed
#                     posting_job.save()

#                     print(
#                         f'✓ Successfully posted "{post.title}" to {post.account.email}')

#                 except Exception as e:
#                     print(
#                         f'✗ Failed to post "{post.title}" to {post.account.email}: {str(e)}')

#                     # Update post status
#                     post.posted = False
#                     post.save()

#                     # Determine error type
#                     error_type = 'unknown'
#                     error_str = str(e).lower()
#                     if 'session' in error_str or 'cookie' in error_str or 'login' in error_str:
#                         error_type = 'session_expired'
#                     elif 'network' in error_str or 'connection' in error_str:
#                         error_type = 'network_error'
#                     elif 'captcha' in error_str:
#                         error_type = 'captcha'
#                     elif 'rate' in error_str or 'limit' in error_str:
#                         error_type = 'rate_limit'

#                     # Log detailed error
#                     ErrorLog.objects.create(
#                         post=post,
#                         error_type=error_type,
#                         error_message=str(e),
#                         stack_trace=traceback.format_exc()
#                     )

#                     failed += 1
#                     account_failed += 1
#                     posting_job.failed_posts = failed
#                     posting_job.save()

#             # Print account completion summary
#             print(f"\n{'='*60}")
#             print(f"✅ Posting completed for account: {account.email}")
#             print(
#                 f"Account Summary: {account_completed} successful, {account_failed} failed")
#             print(f"{'='*60}\n")

#         # Mark job as complete
#         posting_job.status = 'completed' if failed == 0 else 'failed'
#         posting_job.completed_at = timezone.now()
#         posting_job.error_message = f"{failed} posts failed" if failed > 0 else None
#         posting_job.save()

#         print(f"\n{'='*60}")
#         print(f"🎉 ALL POSTING COMPLETED!")
#         print(f"{'='*60}")
#         print(f"Total Accounts Processed: {total_accounts}")
#         print(f"Total Posts: {total_posts}")
#         print(f"✅ Successful: {completed}")
#         print(f"❌ Failed: {failed}")
#         print(f"Job ID: {job_id}")
#         print(f"{'='*60}\n")
