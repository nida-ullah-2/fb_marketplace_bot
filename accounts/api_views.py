from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.conf import settings
from django.core.cache import cache
from threading import Thread
# from .serializers import UserSerializer, RegisterSerializer, FacebookAccountSerializer
# from .models import CustomUser, FacebookAccount
# from postings.models import MarketplacePost
# from automation.post_to_facebook import save_session, manual_login_and_save_session
# from automation.renew_posts import renew_listings as renew_listings_automation
# from automation.session_converter import auto_convert_session, is_browser_format
import os
import re
import json

# Automation imports
from automation.post_to_facebook import save_session, manual_login_and_save_session
from automation.session_converter import auto_convert_session, is_browser_format
from automation.sequential_browser_manager import (
    post_to_marketplace_sequential,
    renew_listings_sequential,
    get_user_automation_status,
    get_all_automation_status
)

# Local imports
from .serializers import UserSerializer, RegisterSerializer, FacebookAccountSerializer
from .models import CustomUser, FacebookAccount
from postings.models import MarketplacePost


def validate_password_strength(password):
    """Validate password contains uppercase, lowercase, number, and special character"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"

    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"

    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]', password):
        return False, "Password must contain at least one special character"

    return True, ""


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """Register a new user - requires admin approval before login"""
    # Validate password strength before proceeding
    password = request.data.get('password', '')
    is_valid, error_message = validate_password_strength(password)

    if not is_valid:
        return Response(
            {'error': error_message},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        # User is created but NOT approved (is_approved=False by default)

        # Don't return tokens - user needs approval first
        return Response({
            'success': True,
            'message': 'Account created successfully! Your account is pending approval. You will be able to login once an administrator approves your account.',
            'user': {
                'username': user.username,
                'email': user.email,
                'is_approved': user.is_approved
            }
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """Login user and return JWT tokens - only for approved users"""
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')

    # Allow login with email or username
    if email and not username:
        try:
            user = CustomUser.objects.get(email=email)
            username = user.username
        except CustomUser.DoesNotExist:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

    user = authenticate(username=username, password=password)

    if user is not None:
        # Check if user is approved
        if not user.is_approved:
            return Response({
                'error': 'Account pending approval',
                'message': 'Your account is waiting for administrator approval. Please contact the administrator.',
                'is_approved': False
            }, status=status.HTTP_403_FORBIDDEN)

        # User is approved, generate tokens
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })

    return Response(
        {'error': 'Invalid credentials'},
        status=status.HTTP_401_UNAUTHORIZED
    )


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def get_user(request):
    """Get or update current user profile"""
    if request.method == 'GET':
        return Response(UserSerializer(request.user).data)

    elif request.method == 'PUT':
        # Update user profile
        user = request.user
        data = request.data

        # Update fields
        if 'username' in data:
            # Check if username is already taken by another user
            if CustomUser.objects.filter(username=data['username']).exclude(id=user.id).exists():
                return Response(
                    {'error': 'Username already taken'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.username = data['username']

        if 'email' in data:
            # Check if email is already taken by another user
            if CustomUser.objects.filter(email=data['email']).exclude(id=user.id).exists():
                return Response(
                    {'error': 'Email already taken'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.email = data['email']

        if 'first_name' in data:
            user.first_name = data['first_name']

        if 'last_name' in data:
            user.last_name = data['last_name']

        user.save()

        # Clear dashboard cache when user info changes
        cache_key = f'dashboard_stats_user_{user.id}'
        cache.delete(cache_key)

        return Response({
            'success': True,
            'message': 'Profile updated successfully',
            'user': UserSerializer(user).data
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change user password"""
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')

    # Validation
    if not old_password or not new_password:
        return Response(
            {'error': 'Both old and new passwords are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check if old password is correct
    if not user.check_password(old_password):
        return Response(
            {'error': 'Current password is incorrect'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate password strength
    is_valid, error_message = validate_password_strength(new_password)
    if not is_valid:
        return Response(
            {'error': error_message},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Set new password
    user.set_password(new_password)
    user.save()

    return Response({
        'success': True,
        'message': 'Password changed successfully'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """Get dashboard statistics - optimized with caching and aggregation"""
    from django.db.models import Count, Q

    # Cache key unique to each user
    cache_key = f'dashboard_stats_user_{request.user.id}'
    cached_stats = cache.get(cache_key)

    if cached_stats:
        return Response(cached_stats)

    # Filter posts and accounts by current user
    user_posts = MarketplacePost.objects.filter(account__user=request.user)

    # Use aggregation for better performance with posted field
    from django.utils import timezone
    today = timezone.now().date()

    stats = user_posts.aggregate(
        total_posts=Count('id'),
        pending_posts=Count('id', filter=Q(posted=False)),
        posted_posts=Count('id', filter=Q(posted=True)),
    )

    # Get posts posted today
    posted_today = user_posts.filter(
        posted=True,
        updated_at__date=today
    ).count()

    total_accounts = FacebookAccount.objects.filter(user=request.user).count()

    # Calculate success rate
    total_posts = stats['total_posts']
    posted_posts = stats['posted_posts']
    success_rate = (posted_posts / total_posts * 100) if total_posts > 0 else 0

    response_data = {
        'total_accounts': total_accounts,
        'total_posts': total_posts,
        'pending_posts': stats['pending_posts'],
        'posted_today': posted_today,
        'success_rate': round(success_rate, 1)
    }

    # Cache for 60 seconds
    cache.set(cache_key, response_data, settings.CACHE_TTL['DASHBOARD_STATS'])

    return Response(response_data)


class FacebookAccountListCreateView(generics.ListCreateAPIView):
    """List all Facebook accounts or create a new one - optimized with prefetch_related"""
    serializer_class = FacebookAccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter accounts by current user"""
        return FacebookAccount.objects.filter(
            user=self.request.user
        ).prefetch_related('marketplacepost_set').order_by('-created_at')

    def perform_create(self, serializer):
        """Automatically set the user when creating an account"""
        serializer.save(user=self.request.user)


class FacebookAccountDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a Facebook account"""
    serializer_class = FacebookAccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Only allow users to access their own accounts"""
        return FacebookAccount.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        """Override delete to also remove session file"""
        account = self.get_object()

        # Delete session file if exists
        session_file = f"sessions/{account.email.replace('@', '_').replace('.', '_')}.json"
        if os.path.exists(session_file):
            os.remove(session_file)

        return super().delete(request, *args, **kwargs)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_facebook_account_with_login(request):
    """
    Add a new Facebook account and automatically open browser for login.
    If CAPTCHA appears, user can solve it manually.
    """
    email = request.data.get('email')
    password = request.data.get('password')

    if not email or not password:
        return Response(
            {'error': 'Email and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check if account already exists for this user
    if FacebookAccount.objects.filter(email=email, user=request.user).exists():
        return Response(
            {'error': 'Account with this email already exists'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Create account in database with user association
    account = FacebookAccount(
        user=request.user,
        email=email
    )
    account.set_password(password)  # Encrypt password before saving
    account.save()

    # Start browser automation in background thread
    def automated_login():
        try:
            print(f"\n🌐 Opening browser for {email}...")
            # Use decrypted password
            success = save_session(email, account.get_password())
            if success:
                print(f"✅ Session saved successfully for {email}")
            else:
                print(f"❌ Login failed for {email}")
        except Exception as e:
            print(f"❌ Error during automated login: {e}")

    # Start the login process in a background thread
    thread = Thread(target=automated_login, daemon=True)
    thread.start()

    # Return response immediately with account data
    serializer = FacebookAccountSerializer(account)
    return Response({
        'message': 'Account created successfully. Browser opening for login...',
        'account': serializer.data
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_facebook_account_manual_login(request):
    """
    Add a new Facebook account with FULLY MANUAL login
    Browser opens, user types everything manually, solves CAPTCHA
    Once logged in, session is saved automatically
    """
    email = request.data.get('email')

    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check if account already exists for this user
    if FacebookAccount.objects.filter(email=email, user=request.user).exists():
        return Response(
            {'error': 'Account with this email already exists'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Create account in database WITHOUT password (manual login)
    account = FacebookAccount(
        user=request.user,
        email=email
    )
    # Set a placeholder password (won't be used for login)
    account.set_password("manual_login_placeholder")
    account.save()

    # Start manual login in background thread
    def manual_login():
        try:
            print(f"\n🖥️  Starting manual login for {email}...")
            success = manual_login_and_save_session(email)
            if success:
                print(f"✅ Manual login completed successfully for {email}")
            else:
                print(f"❌ Manual login failed for {email}")
                # Optionally delete the account if login failed
                # account.delete()
        except Exception as e:
            print(f"❌ Error during manual login: {e}")

    # Start the manual login process in a background thread
    thread = Thread(target=manual_login, daemon=True)
    thread.start()

    # Return response immediately
    serializer = FacebookAccountSerializer(account)
    return Response({
        'message': 'Account created. Browser opening for MANUAL login. Please login yourself!',
        'account': serializer.data,
        'instructions': 'A browser window will open. Please login manually and wait for confirmation.'
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_upload_accounts_with_login(request):
    """
    Bulk upload Facebook accounts from a text file.
    Format: email:password (one per line)
    Browser will open for each account to save session.
    """
    if 'file' not in request.FILES:
        return Response(
            {'error': 'No file provided'},
            status=status.HTTP_400_BAD_REQUEST
        )

    file = request.FILES['file']

    # Validate file type
    if not file.name.endswith('.txt'):
        return Response(
            {'error': 'Only .txt files are allowed'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Read and parse file
        content = file.read().decode('utf-8')
        lines = content.strip().split('\n')

        accounts_created = []
        accounts_skipped = []
        accounts_failed = []

        for line in lines:
            line = line.strip()

            # Skip empty lines or comments
            if not line or line.startswith('#') or ':' not in line:
                continue

            try:
                # Split email and password
                parts = line.split(':', 1)
                if len(parts) != 2:
                    accounts_failed.append({
                        'line': line,
                        'error': 'Invalid format (use email:password)'
                    })
                    continue

                email = parts[0].strip()
                password = parts[1].strip()

                # Validate email and password
                if not email or not password:
                    accounts_failed.append({
                        'line': line,
                        'error': 'Email or password is empty'
                    })
                    continue

                # Check if account already exists for this user
                if FacebookAccount.objects.filter(email=email, user=request.user).exists():
                    accounts_skipped.append(email)
                    continue

                # Create account in database with user association
                account = FacebookAccount(
                    user=request.user,
                    email=email
                )
                # Encrypt password before saving
                account.set_password(password)
                account.save()
                accounts_created.append(email)

            except Exception as e:
                accounts_failed.append({
                    'line': line,
                    'error': str(e)
                })

        # Start browser automation for all new accounts in background
        if accounts_created:
            def process_bulk_sessions():
                for email in accounts_created:
                    try:
                        account = FacebookAccount.objects.get(email=email)
                        print(f"\n🌐 Opening browser for {email}...")
                        # Use decrypted password
                        success = save_session(email, account.get_password())
                        if success:
                            print(f"✅ Session saved for {email}")
                        else:
                            print(f"❌ Login failed for {email}")
                    except Exception as e:
                        print(f"❌ Error processing {email}: {e}")

            thread = Thread(target=process_bulk_sessions, daemon=True)
            thread.start()

        return Response({
            'message': f'Bulk upload completed. Processing {len(accounts_created)} accounts...',
            'summary': {
                'created': len(accounts_created),
                'skipped': len(accounts_skipped),
                'failed': len(accounts_failed)
            },
            'details': {
                'created_accounts': accounts_created,
                'skipped_accounts': accounts_skipped,
                'failed_accounts': accounts_failed
            }
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {'error': f'Failed to process file: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_account_session(request, pk):
    """
    Update session for an existing account by opening browser for re-login.
    Used when session expires or doesn't exist.
    """
    try:
        # Only allow users to update their own accounts
        account = FacebookAccount.objects.get(pk=pk, user=request.user)

        # Start browser automation in background thread
        def update_session():
            try:
                print(f"\n🔄 Update Session requested for: {account.email}")
                print(f"🌐 Opening browser for re-login...")
                # Use decrypted password
                success = save_session(account.email, account.get_password())
                if success:
                    print(
                        f"✅ Session updated successfully for {account.email}")
                else:
                    print(f"❌ Session update failed for {account.email}")
            except Exception as e:
                print(f"❌ Error updating session: {e}")

        thread = Thread(target=update_session, daemon=True)
        thread.start()

        # Return response immediately
        serializer = FacebookAccountSerializer(account)
        return Response({
            'message': f'Browser opening for {account.email}. Please complete login if CAPTCHA appears.',
            'account': serializer.data
        }, status=status.HTTP_200_OK)

    except FacebookAccount.DoesNotExist:
        return Response(
            {'error': 'Account not found'},
            status=status.HTTP_404_NOT_FOUND
        )


# Admin User Management Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_users(request):
    """Get all users - only accessible by admin users"""
    # Check if user is admin (staff or superuser)
    if not (request.user.is_staff or request.user.is_superuser):
        return Response(
            {'error': 'You do not have permission to access this resource'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Get all users
    users = CustomUser.objects.all().order_by('-date_joined')

    # Serialize user data
    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_approved': user.is_approved,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'date_joined': user.date_joined
        })

    return Response({
        'success': True,
        'users': users_data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_user(request, user_id):
    """Approve a user - only accessible by admin users"""
    # Check if user is admin (staff or superuser)
    if not (request.user.is_staff or request.user.is_superuser):
        return Response(
            {'error': 'You do not have permission to perform this action'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        user = CustomUser.objects.get(id=user_id)

        # Update user approval status
        user.is_approved = True
        user.save()

        return Response({
            'success': True,
            'message': f'User {user.username} has been approved successfully'
        })

    except CustomUser.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def disapprove_user(request, user_id):
    """Disapprove a user - only accessible by admin users"""
    # Check if user is admin (staff or superuser)
    if not (request.user.is_staff or request.user.is_superuser):
        return Response(
            {'error': 'You do not have permission to perform this action'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        user = CustomUser.objects.get(id=user_id)

        # Prevent disapproving superusers
        if user.is_superuser:
            return Response(
                {'error': 'Cannot disapprove superuser accounts'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Prevent admin from disapproving themselves
        if user.id == request.user.id:
            return Response(
                {'error': 'You cannot disapprove your own account'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update user approval status
        user.is_approved = False
        user.save()

        return Response({
            'success': True,
            'message': f'User {user.username} has been disapproved'
        })

    except CustomUser.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_user_permissions(request, user_id):
    """Update user permissions (staff/superuser) - only accessible by admin users"""
    # Check if user is admin (staff or superuser)
    if not (request.user.is_staff or request.user.is_superuser):
        return Response(
            {'error': 'You do not have permission to perform this action'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        user = CustomUser.objects.get(id=user_id)

        # Prevent admin from removing their own superuser status
        if user.id == request.user.id and not request.data.get('is_superuser', True):
            return Response(
                {'error': 'You cannot remove your own superuser status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update permissions
        user.is_staff = request.data.get('is_staff', user.is_staff)
        user.is_superuser = request.data.get('is_superuser', user.is_superuser)
        user.save()

        return Response({
            'success': True,
            'message': f'Permissions updated for {user.username}'
        })

    except CustomUser.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reset_user_password(request, user_id):
    """Reset user password - only accessible by admin users"""
    # Check if user is admin (staff or superuser)
    if not (request.user.is_staff or request.user.is_superuser):
        return Response(
            {'error': 'You do not have permission to perform this action'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        user = CustomUser.objects.get(id=user_id)
        new_password = request.data.get('new_password')

        if not new_password:
            return Response(
                {'error': 'New password is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate password strength
        is_valid, error_message = validate_password_strength(new_password)
        if not is_valid:
            return Response(
                {'error': error_message},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Set new password
        user.set_password(new_password)
        user.save()

        return Response({
            'success': True,
            'message': f'Password reset successfully for {user.username}'
        })

    except CustomUser.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_session(request):
    """
    Import a Facebook session from browser-exported JSON.
    Automatically detects format, validates, converts if needed, and saves.
    """
    session_data = request.data.get('session_data')
    filename = request.data.get('filename')

    if not session_data:
        return Response(
            {'error': 'Session data is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not filename:
        return Response(
            {'error': 'Filename is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Parse JSON if it's a string
        if isinstance(session_data, str):
            parsed_data = json.loads(session_data)
        else:
            parsed_data = session_data

        # Detect format
        format_type = "browser" if is_browser_format(
            parsed_data) else "playwright"

        # Auto-convert if needed
        playwright_session = auto_convert_session(parsed_data)

        # Validate required cookies
        cookies = playwright_session.get('cookies', [])
        if not cookies:
            return Response(
                {'error': 'No cookies found in session data'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract essential cookies
        cookie_names = {cookie['name'] for cookie in cookies}
        required_cookies = {'c_user', 'xs'}
        missing_cookies = required_cookies - cookie_names

        if missing_cookies:
            return Response(
                {'error': f'Missing required cookies: {", ".join(missing_cookies)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract Facebook user ID from c_user cookie
        fb_user_id = None
        for cookie in cookies:
            if cookie['name'] == 'c_user':
                fb_user_id = cookie['value']
                break

        # Prepare filename (ensure proper format)
        clean_filename = filename.replace('@', '_').replace('.', '_')
        if not clean_filename.endswith('.json'):
            clean_filename += '.json'

        # Only accept email format (e.g., test@gmail.com)
        email = filename.strip().replace('.json', '')  # Remove .json if present

        # Validate email format - must have @ and domain with .
        if '@' not in email:
            return Response(
                {'error': 'Invalid format. Please provide a valid email address (e.g., test@gmail.com)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if domain has a dot
        email_parts = email.split('@')
        if len(email_parts) != 2 or '.' not in email_parts[1]:
            return Response(
                {'error': 'Invalid email format. Please provide a valid email address (e.g., test@gmail.com)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if account already exists for this user
        existing_account = FacebookAccount.objects.filter(
            email=email,
            user=request.user
        ).first()

        if existing_account:
            return Response(
                {'error': f'Account with email {email} already exists. Please use "Update Session" button on the existing account instead, or delete it first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Save session file
        session_path = os.path.join('sessions', clean_filename)
        os.makedirs('sessions', exist_ok=True)

        with open(session_path, 'w', encoding='utf-8') as f:
            json.dump(playwright_session, f, indent=2)

        # Create new account with placeholder password
        account = FacebookAccount.objects.create(
            email=email,
            user=request.user
        )
        account.set_password('imported_session_no_password')
        account.save()

        created = True

        # Prepare response
        was_converted = format_type == "browser"

        return Response({
            'success': True,
            'message': 'Session imported successfully',
            'details': {
                'filename': clean_filename,
                'format': format_type,
                'converted': was_converted,
                'cookies_count': len(cookies),
                'facebook_user_id': fb_user_id,
                'email': email,
                'account_created': created,
                'account_id': account.id
            }
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    except json.JSONDecodeError:
        return Response(
            {'error': 'Invalid JSON format'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Failed to import session: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def renew_listings(request):
    """Renew marketplace listings for selected accounts"""
    account_ids = request.data.get('account_ids', [])
    renewal_count = request.data.get('renewal_count', 20)

    if not account_ids:
        return Response(
            {'error': 'Please select at least one account'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not isinstance(renewal_count, int) or renewal_count < 1 or renewal_count > 20:
        return Response(
            {'error': 'Renewal count must be between 1 and 20 (Facebook limit)'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get accounts belonging to the user
    accounts = FacebookAccount.objects.filter(
        id__in=account_ids,
        user=request.user
    )

    if not accounts.exists():
        return Response(
            {'error': 'No valid accounts found'},
            status=status.HTTP_400_BAD_REQUEST
        )

    results = []

    for account in accounts:
        # ✅ USE SEQUENTIAL QUEUE SYSTEM for proper browser management
        result = renew_listings_sequential(
            email=account.email,
            renewal_count=renewal_count
        )

        # Add account info to result
        result['account_id'] = account.id
        result['email'] = account.email
        results.append(result)

    # Calculate totals
    total_renewed = sum(r['renewed_count'] for r in results)
    successful_accounts = sum(1 for r in results if r['success'])

    return Response({
        'success': True,
        'total_renewed': total_renewed,
        'successful_accounts': successful_accounts,
        'total_accounts': len(accounts),
        'results': results
    })
