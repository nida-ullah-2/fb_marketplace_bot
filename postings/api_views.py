from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from .models import MarketplacePost
from .serializers import MarketplacePostSerializer
from .cache_utils import invalidate_dashboard_cache, invalidate_posts_cache
from accounts.models import FacebookAccount
import requests
from django.core.files.base import ContentFile
from urllib.parse import urlparse
import os
import csv
import io
from django.utils import timezone


class MarketplacePostListCreateView(generics.ListCreateAPIView):
    """List all marketplace posts or create a new one"""
    serializer_class = MarketplacePostSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter posts by current user's accounts - optimized with select_related"""
        # Use select_related to fetch account data in a single query (reduces N+1 queries)
        queryset = MarketplacePost.objects.filter(
            account__user=self.request.user
        ).select_related('account').order_by('-created_at')

        # Filter by posted status if provided
        posted = self.request.query_params.get('posted', None)
        if posted is not None:
            queryset = queryset.filter(posted=posted.lower() == 'true')
        return queryset

    def create(self, request, *args, **kwargs):
        """Handle post creation with optional image URL"""
        # Invalidate caches when creating a post
        invalidate_dashboard_cache()
        invalidate_posts_cache()

        # Check if image_url is provided
        image_url = request.data.get('image_url')

        if image_url and not request.data.get('image'):
            # Download image from URL
            try:
                response = requests.get(image_url, timeout=10, stream=True)
                if response.status_code == 200:
                    # Get filename from URL or generate one
                    parsed_url = urlparse(image_url)
                    filename = os.path.basename(parsed_url.path)
                    if not filename or '.' not in filename:
                        # Generate filename from title
                        title = request.data.get('title', 'image')
                        filename = f"{title[:30].replace(' ', '_')}.jpg"

                    # Create serializer with the data
                    serializer = self.get_serializer(data=request.data)
                    serializer.is_valid(raise_exception=True)

                    # Save the instance and then add the image
                    instance = serializer.save()

                    # Save the downloaded image to the instance
                    image_content = ContentFile(response.content)
                    instance.image.save(filename, image_content, save=True)

                    # Return the updated instance
                    output_serializer = self.get_serializer(instance)
                    headers = self.get_success_headers(output_serializer.data)
                    return Response(
                        output_serializer.data,
                        status=status.HTTP_201_CREATED,
                        headers=headers
                    )
                else:
                    return Response(
                        {'error': f'Failed to download image from URL (HTTP {response.status_code})'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except requests.exceptions.RequestException as e:
                return Response(
                    {'error': f'Error downloading image: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return super().create(request, *args, **kwargs)


class MarketplacePostDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a marketplace post"""
    serializer_class = MarketplacePostSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Only allow users to access posts from their own accounts"""
        return MarketplacePost.objects.filter(
            account__user=self.request.user
        ).select_related('account')

    def destroy(self, request, *args, **kwargs):
        """Override delete to invalidate caches"""
        invalidate_dashboard_cache()
        invalidate_posts_cache()
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Handle post update with better error handling - supports partial updates"""
        # Invalidate caches when updating a post
        invalidate_dashboard_cache()
        invalidate_posts_cache()

        # Force partial update (PATCH behavior even for PUT)
        kwargs['partial'] = True
        instance = self.get_object()

        # Log the incoming data for debugging
        print(f"\n=== Update Post #{instance.id} ===")
        print(f"Data received: {dict(request.data)}")
        print(f"Files: {list(request.FILES.keys())}")

        # Prepare data for serializer
        data = request.data.copy()

        # Handle boolean conversion for 'posted' field if sent as string
        if 'posted' in data:
            if isinstance(data['posted'], str):
                data['posted'] = data['posted'].lower() in ('true', '1', 'yes')

        serializer = self.get_serializer(
            instance, data=data, partial=True)

        try:
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)

            print(f"✓ Post #{instance.id} updated successfully")
            print(
                f"Updated fields: {list(serializer.validated_data.keys())}\n")

            return Response(serializer.data)
        except serializers.ValidationError as e:
            print(f"✗ Validation errors: {e.detail}")
            return Response(
                {'error': e.detail},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            print(f"✗ Unexpected error: {str(e)}\n")
            error_msg = str(e) if str(
                e) else "An error occurred while updating the post"
            return Response(
                {'error': error_msg},
                status=status.HTTP_400_BAD_REQUEST
            )


class BulkUploadPostsView(APIView):
    """Handle bulk upload of posts via CSV file"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Process CSV file and create posts for selected accounts"""
        # Invalidate caches at the start since we'll be creating multiple posts
        invalidate_dashboard_cache()
        invalidate_posts_cache()

        csv_file = request.FILES.get('csv_file')
        account_ids = request.data.getlist(
            'accounts[]') or request.data.getlist('accounts')

        # Validation
        if not csv_file:
            return Response(
                {'error': 'CSV file is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not csv_file.name.endswith('.csv'):
            return Response(
                {'error': 'Please upload a CSV file'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not account_ids:
            return Response(
                {'error': 'Please select at least one account'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get selected accounts - only from current user
        try:
            accounts = FacebookAccount.objects.filter(
                id__in=account_ids,
                user=request.user  # Only allow user's own accounts
            )
            if not accounts.exists():
                return Response(
                    {'error': 'No valid accounts found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': f'Error fetching accounts: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse CSV
        try:
            decoded_file = csv_file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(decoded_file))

            success_count = 0
            error_count = 0
            errors = []
            posts_data = []

            # First pass: Validate and collect all post data
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    # Extract data from CSV
                    title = row.get('title', '').strip()
                    description = row.get('description', '').strip()
                    price = row.get('price', '').strip()
                    image_url = row.get('image_url', '').strip()

                    # Validate required fields
                    if not all([title, description, price]):
                        errors.append({
                            'row': row_num,
                            'error': 'Missing required fields (title, description, or price)'
                        })
                        error_count += 1
                        continue

                    # Validate price
                    try:
                        price_decimal = float(price)
                        if price_decimal < 0:
                            raise ValueError("Price cannot be negative")
                    except ValueError as e:
                        errors.append({
                            'row': row_num,
                            'error': f"Invalid price '{price}' - {str(e)}"
                        })
                        error_count += 1
                        continue

                    # Download image from URL if provided
                    image_file = None
                    if image_url:
                        try:
                            response = requests.get(
                                image_url, timeout=10, stream=True)
                            if response.status_code == 200:
                                parsed_url = urlparse(image_url)
                                filename = os.path.basename(parsed_url.path)
                                if not filename or '.' not in filename:
                                    filename = f"{title[:30].replace(' ', '_')}.jpg"
                                image_file = ContentFile(
                                    response.content, name=filename)
                            else:
                                errors.append({
                                    'row': row_num,
                                    'error': f'Failed to download image (HTTP {response.status_code})'
                                })
                        except requests.exceptions.RequestException as e:
                            errors.append({
                                'row': row_num,
                                'error': f'Error downloading image - {str(e)}'
                            })

                    # Store validated post data
                    posts_data.append({
                        'title': title,
                        'description': description,
                        'price': price_decimal,
                        'image_file': image_file
                    })

                except Exception as e:
                    errors.append({
                        'row': row_num,
                        'error': f'Unexpected error - {str(e)}'
                    })
                    error_count += 1
                    continue

            # Second pass: Create posts for ALL selected accounts
            for post_data in posts_data:
                for account in accounts:
                    scheduled_time = timezone.now()

                    post = MarketplacePost.objects.create(
                        account=account,
                        title=post_data['title'],
                        description=post_data['description'],
                        price=post_data['price'],
                        scheduled_time=scheduled_time,
                        posted=False
                    )

                    # Assign image if available
                    if post_data.get('image_file'):
                        post.image.save(
                            post_data['image_file'].name,
                            post_data['image_file'],
                            save=True
                        )

                    success_count += 1

            # Prepare response
            num_posts = len(posts_data)
            num_accounts = len(accounts)

            response_data = {
                'success': True,
                'message': f'Successfully created {success_count} posts! ({num_posts} post(s) × {num_accounts} account(s))',
                'stats': {
                    'success_count': success_count,
                    'error_count': error_count,
                    'num_posts': num_posts,
                    'num_accounts': num_accounts
                }
            }

            if errors:
                # Limit to first 10 errors
                response_data['errors'] = errors[:10]
                if len(errors) > 10:
                    response_data['additional_errors'] = len(errors) - 10

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': f'Error processing CSV file: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class StartPostingView(APIView):
    """Start posting selected pending posts to Facebook Marketplace"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Trigger posting process for selected post IDs"""
        import subprocess
        import sys
        import uuid

        post_ids = request.data.get('post_ids', [])

        # Validation
        if not post_ids or not isinstance(post_ids, list):
            return Response(
                {'error': 'Please provide post_ids as an array'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Filter only pending posts from user's accounts - optimized with select_related
        try:
            pending_posts = MarketplacePost.objects.select_related('account').filter(
                id__in=post_ids,
                posted=False,
                account__user=request.user  # Only allow posting from user's own accounts
            )

            if not pending_posts.exists():
                return Response(
                    {'error': 'No pending posts found with the provided IDs'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            pending_count = pending_posts.count()

            # Generate unique job ID for tracking
            job_id = str(uuid.uuid4())

            # Start the posting script in background
            # This runs the Django management command asynchronously
            python_executable = sys.executable

            # Get the project root directory (where manage.py is)
            # __file__ is in postings/api_views.py
            # Go up 2 levels: postings/ -> fb_marketplace_bot/
            project_root = os.path.dirname(os.path.dirname(__file__))
            manage_py_path = os.path.join(project_root, 'manage.py')

            # Build command to run the management command
            # Passing post IDs, job ID, and user ID as comma-separated string
            post_ids_str = ','.join(map(str, post_ids))
            command = [
                python_executable,
                manage_py_path,
                'post_to_marketplace',
                '--post-ids',
                post_ids_str,
                '--job-id',
                job_id,
                '--user-id',
                str(request.user.id)
            ]

            # Create log files for debugging
            log_dir = os.path.join(project_root, 'logs')
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, 'posting_process.log')

            # Write initial log entry
            try:
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(
                        f"\n\n=== Starting posting process at {timezone.now()} ===\n")
                    log.write(f"Project root: {project_root}\n")
                    log.write(f"manage.py path: {manage_py_path}\n")
                    log.write(f"Command: {' '.join(command)}\n")
                    log.write(f"Post IDs: {post_ids_str}\n\n")
            except Exception as e:
                print(f"Error writing to log file: {e}")

            # Start subprocess in background with output logging
            # Open log file separately to avoid context manager closing it
            log_handle = open(log_file, 'a', encoding='utf-8')

            # Set environment variables for UTF-8 encoding (fixes emoji/unicode issues on Windows)
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            # In production (headless), don't create console window
            # In development, show console for debugging
            creation_flags = 0
            if os.name == 'nt':  # Windows
                # Only show console window if not in headless mode
                headless = os.getenv('PLAYWRIGHT_HEADLESS',
                                     'true').lower() == 'true'
                if not headless:
                    creation_flags = subprocess.CREATE_NEW_CONSOLE

            subprocess.Popen(
                command,
                stdout=log_handle,
                stderr=log_handle,
                cwd=project_root,
                env=env,
                creationflags=creation_flags
            )

            return Response({
                'success': True,
                'message': f'Started posting process for {pending_count} pending post(s)',
                'job_id': job_id,
                'pending_count': pending_count,
                'total_selected': len(post_ids),
                'log_file': log_file,
                'status_stream_url': f'/api/posts/status-stream/{job_id}/'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'Error starting posting process: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AnalyticsView(APIView):
    """Get analytics data with various time period filters"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import PostAnalytics
        from django.db.models import Count, Q
        from datetime import timedelta, datetime

        user = request.user
        period = request.query_params.get(
            'period', 'lifetime')  # weekly, monthly, lifetime
        account_email = request.query_params.get('account', None)

        # Calculate date range based on period
        now = timezone.now()
        if period == 'weekly':
            start_date = now - timedelta(days=7)
        elif period == 'monthly':
            start_date = now - timedelta(days=30)
        else:  # lifetime
            start_date = None

        # Base query
        analytics_query = PostAnalytics.objects.filter(user=user)

        if start_date:
            analytics_query = analytics_query.filter(timestamp__gte=start_date)

        if account_email:
            analytics_query = analytics_query.filter(
                account_email=account_email)

        # Get counts by action
        total_created = analytics_query.filter(action='created').count()
        total_posted = analytics_query.filter(action='posted').count()

        # Current status from MarketplacePost
        current_posts = MarketplacePost.objects.filter(account__user=user)
        if account_email:
            current_posts = current_posts.filter(account__email=account_email)

        currently_posted = current_posts.filter(posted=True).count()
        currently_pending = current_posts.filter(posted=False).count()

        # Get account-wise breakdown
        account_stats = analytics_query.values('account_email').annotate(
            created_count=Count('id', filter=Q(action='created')),
            posted_count=Count('id', filter=Q(action='posted'))
        ).order_by('-created_count')

        # Get daily breakdown for charts
        daily_stats = []
        if period != 'lifetime':
            days = 7 if period == 'weekly' else 30
            for i in range(days):
                day = now - timedelta(days=i)
                day_start = day.replace(
                    hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)

                created = analytics_query.filter(
                    action='created',
                    timestamp__gte=day_start,
                    timestamp__lt=day_end
                ).count()

                posted = analytics_query.filter(
                    action='posted',
                    timestamp__gte=day_start,
                    timestamp__lt=day_end
                ).count()

                daily_stats.append({
                    'date': day_start.strftime('%Y-%m-%d'),
                    'created': created,
                    'posted': posted
                })

            daily_stats.reverse()

        return Response({
            'period': period,
            'summary': {
                'total_created': total_created,
                'total_posted': total_posted,
                'currently_posted': currently_posted,
                'currently_pending': currently_pending,
                'not_posted': total_created - total_posted,
            },
            'by_account': list(account_stats),
            'daily_breakdown': daily_stats,
        })
