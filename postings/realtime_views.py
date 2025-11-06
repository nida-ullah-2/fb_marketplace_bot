"""
Real-time status updates and health check views
"""
from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import PostingJob, ErrorLog
from .serializers import PostingJobSerializer, ErrorLogSerializer
from accounts.models import FacebookAccount
import json
import time
import os


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def posting_status_stream(request, job_id):
    """
    Server-Sent Events endpoint for real-time posting status updates
    Usage: GET /api/posts/status-stream/<job_id>/
    """
    def event_stream():
        """Generator function that yields SSE formatted data"""
        last_completed = -1
        max_iterations = 600  # 10 minutes max (600 * 1 second)
        iteration = 0

        while iteration < max_iterations:
            try:
                # Get current job status - filter by user for security
                job = PostingJob.objects.filter(
                    job_id=job_id,
                    user=request.user
                ).first()

                if not job:
                    # Job not found or doesn't belong to user
                    yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                    break

                # Send update if progress changed or every 5 seconds
                if job.completed_posts != last_completed or iteration % 5 == 0:
                    serializer = PostingJobSerializer(job)
                    data = serializer.data
                    yield f"data: {json.dumps(data)}\n\n"
                    last_completed = job.completed_posts

                # Check if job is complete
                if job.status in ['completed', 'failed']:
                    yield f"data: {json.dumps({'status': 'complete', 'final': True})}\n\n"
                    break

                time.sleep(1)  # Poll every second
                iteration += 1

            except Exception as e:
                error_data = {'error': str(e)}
                yield f"data: {json.dumps(error_data)}\n\n"
                break

        # Send final close event
        yield f"data: {json.dumps({'status': 'stream_closed'})}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable buffering in nginx
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_posting_job_status(request, job_id):
    """
    Get current status of a posting job (one-time request, not streaming)
    Usage: GET /api/posts/job-status/<job_id>/
    """
    try:
        # Filter by user for security
        job = PostingJob.objects.get(job_id=job_id, user=request.user)
        serializer = PostingJobSerializer(job)
        return Response(serializer.data)
    except PostingJob.DoesNotExist:
        return Response(
            {'error': 'Job not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_error_logs(request):
    """
    Get error logs with optional filtering - filtered by current user
    Query params: post_id, error_type, limit
    Usage: GET /api/posts/error-logs/?post_id=1&limit=10
    """
    # Filter error logs to only show current user's posts
    error_logs = ErrorLog.objects.filter(post__account__user=request.user)

    # Filter by post_id if provided
    post_id = request.query_params.get('post_id')
    if post_id:
        error_logs = error_logs.filter(post_id=post_id)

    # Filter by error_type if provided
    error_type = request.query_params.get('error_type')
    if error_type:
        error_logs = error_logs.filter(error_type=error_type)

    # Limit results
    limit = request.query_params.get('limit', 50)
    try:
        limit = int(limit)
    except ValueError:
        limit = 50

    error_logs = error_logs[:limit]

    serializer = ErrorLogSerializer(error_logs, many=True)
    return Response({
        'count': len(serializer.data),
        'error_logs': serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def health_check_accounts(request):
    """
    Health check endpoint to verify account sessions are valid
    Usage: GET /api/accounts/health-check/
    Returns status of current user's accounts and their sessions
    """
    # Filter accounts by current user
    accounts = FacebookAccount.objects.filter(user=request.user)
    results = []

    for account in accounts:
        # Check if session file exists
        session_file = f"sessions/{account.email.replace('@', '_').replace('.', '_')}.json"
        session_exists = os.path.exists(session_file)

        # Check if session file is recent (DISABLED - Keep sessions forever)
        session_valid = session_exists  # Session is always valid if it exists
        session_age_days = None

        if session_exists:
            import datetime
            file_modified = os.path.getmtime(session_file)
            age_seconds = time.time() - file_modified
            session_age_days = round(age_seconds / 86400, 1)  # Convert to days
            # No age limit - session valid forever as long as file exists

        # Get post statistics for this account
        from .models import MarketplacePost
        total_posts = MarketplacePost.objects.filter(account=account).count()
        posted_count = MarketplacePost.objects.filter(
            account=account, posted=True).count()
        failed_count = MarketplacePost.objects.filter(
            account=account, status='failed').count()

        results.append({
            'account_id': account.id,
            'email': account.email,
            'session_exists': session_exists,
            'session_valid': session_valid,
            'session_age_days': session_age_days,
            'total_posts': total_posts,
            'posted_count': posted_count,
            'failed_count': failed_count,
            'health_status': 'healthy' if session_valid else ('warning' if session_exists else 'error')
        })

    # Calculate overall health
    healthy_count = sum(1 for r in results if r['health_status'] == 'healthy')
    warning_count = sum(1 for r in results if r['health_status'] == 'warning')
    error_count = sum(1 for r in results if r['health_status'] == 'error')

    return Response({
        'overall_health': 'healthy' if error_count == 0 else ('warning' if healthy_count > 0 else 'error'),
        'summary': {
            'total_accounts': len(results),
            'healthy': healthy_count,
            'warning': warning_count,
            'error': error_count
        },
        'accounts': results
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def validate_account_session(request, account_id):
    """
    Validate a specific account's session
    Usage: GET /api/accounts/<id>/validate-session/
    """
    try:
        # Filter by user for security
        account = FacebookAccount.objects.get(id=account_id, user=request.user)

        # Check session file
        session_file = f"sessions/{account.email.replace('@', '_').replace('.', '_')}.json"
        session_exists = os.path.exists(session_file)

        if not session_exists:
            return Response({
                'valid': False,
                'message': 'Session file does not exist',
                'action_required': 'Please update session for this account'
            }, status=status.HTTP_200_OK)

        # Check file age
        import datetime
        file_modified = os.path.getmtime(session_file)
        age_seconds = time.time() - file_modified
        age_days = round(age_seconds / 86400, 1)

        # Read session file to check if it's valid JSON
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)

            # Session is valid if file exists and has cookies (no age limit)
            session_valid = 'cookies' in session_data

            return Response({
                'valid': session_valid,
                'session_age_days': age_days,
                'message': 'Session is valid (kept forever)' if session_valid else 'Session file missing cookies',
                'action_required': None if session_valid else 'Please update session for this account'
            })

        except json.JSONDecodeError:
            return Response({
                'valid': False,
                'message': 'Session file is corrupted',
                'action_required': 'Please update session for this account'
            }, status=status.HTTP_200_OK)

    except FacebookAccount.DoesNotExist:
        return Response(
            {'error': 'Account not found'},
            status=status.HTTP_404_NOT_FOUND
        )
