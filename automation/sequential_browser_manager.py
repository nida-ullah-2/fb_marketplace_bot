"""
Sequential Queue Manager for Facebook Marketplace Bot
====================================================

IMPROVED APPROACH - 2 QUEUES PER USER:
- Each user has 2 separate queues: POST queue and RENEW queue
- Both queues process in parallel (max 2 browsers per user)
- Sequential within each queue type (posts run one-by-one, renews run one-by-one)
- No limit on queue size - can handle unlimited operations

EXAMPLE:
User adds: Post1, Post2, Renew1, Post3, Renew2

POST Queue: [Post1, Post2, Post3]  → Browser 1 processes sequentially
RENEW Queue: [Renew1, Renew2]      → Browser 2 processes sequentially

Both run in parallel = Faster processing with controlled browsers
"""

import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from django.utils import timezone
import logging

# ✅ IMPORT YOUR EXISTING WORKING FUNCTIONS - NO CHANGES TO THEM
from .post_to_facebook import login_and_post
from .renew_posts import renew_listings

logger = logging.getLogger(__name__)


class SequentialBrowserManager:
    """
    Manages 2 parallel sequential queues per user

    STRUCTURE:
    - Each user gets 2 queues: posting_queue and renewing_queue
    - Each queue processes sequentially (one operation at a time)
    - Both queues can run in parallel (max 2 browsers per user)
    - Multiple users can work simultaneously
    """

    def __init__(self):
        # Separate queues for each operation type per user
        self.user_post_queues = defaultdict(deque)     # POST operations
        self.user_renew_queues = defaultdict(deque)    # RENEW operations

        # Track active processors per user per type
        self.user_post_processors = {}   # Posting processors
        self.user_renew_processors = {}  # Renewing processors

        # Track status for monitoring
        self.user_status = defaultdict(lambda: {
            'post_active': False,
            'renew_active': False,
            'current_post_operation': None,
            'current_renew_operation': None,
            'total_posts_queued': 0,
            'total_renews_queued': 0,
            'posts_completed': 0,
            'renews_completed': 0,
            'last_activity': None
        })

        # Thread lock for thread-safe operations
        self.lock = threading.Lock()

        print("🚀 Sequential Browser Manager initialized (2 queues per user)")

    def add_posting_operation(self, email, title, description, price, image_path):
        """
        Add a posting operation to user's POST queue

        Args:
            email: Facebook account email
            title: Post title
            description: Post description
            price: Item price
            image_path: Path to product image
        """
        operation = {
            'type': 'post',
            'email': email,
            'data': {
                'title': title,
                'description': description,
                'price': price,
                'image_path': image_path
            },
            'timestamp': timezone.now()
        }

        with self.lock:
            self.user_post_queues[email].append(operation)
            self.user_status[email]['total_posts_queued'] += 1

            print(f"📝 Added POSTING operation for {email}")
            print(f"   POST queue size: {len(self.user_post_queues[email])}")

            # Start post processor if not already active
            if not self.user_status[email]['post_active']:
                self._start_post_processor(email)

    def add_renewing_operation(self, email, renewal_count=20):
        """
        Add a renewing operation to user's RENEW queue

        Args:
            email: Facebook account email
            renewal_count: Number of listings to renew (no limit, uses user's value)
        """
        operation = {
            'type': 'renew',
            'email': email,
            'data': {
                'renewal_count': renewal_count  # Use whatever user specifies
            },
            'timestamp': timezone.now()
        }

        with self.lock:
            self.user_renew_queues[email].append(operation)
            self.user_status[email]['total_renews_queued'] += 1

            print(f"🔄 Added RENEWING operation for {email}")
            print(f"   RENEW queue size: {len(self.user_renew_queues[email])}")

            # Start renew processor if not already active
            if not self.user_status[email]['renew_active']:
                self._start_renew_processor(email)

    def _start_post_processor(self, email):
        """
        Start sequential processor for user's POST queue

        Args:
            email: User email to start post processing for
        """
        if email in self.user_post_processors:
            # Already has a post processor
            return

        # Create single-threaded executor for sequential post processing
        self.user_post_processors[email] = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"post_{email}")
        self.user_status[email]['post_active'] = True

        # Submit the processing task
        future = self.user_post_processors[email].submit(
            self._process_post_queue, email)
        future.add_done_callback(lambda f: self._cleanup_post_processor(email))

        print(f"🎬 Started POST processor for {email}")

    def _start_renew_processor(self, email):
        """
        Start sequential processor for user's RENEW queue

        Args:
            email: User email to start renew processing for
        """
        if email in self.user_renew_processors:
            # Already has a renew processor
            return

        # Create single-threaded executor for sequential renew processing
        self.user_renew_processors[email] = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"renew_{email}")
        self.user_status[email]['renew_active'] = True

        # Submit the processing task
        future = self.user_renew_processors[email].submit(
            self._process_renew_queue, email)
        future.add_done_callback(
            lambda f: self._cleanup_renew_processor(email))

        print(f"🎬 Started RENEW processor for {email}")

    def _process_post_queue(self, email):
        """
        Process POST operations sequentially for a specific user

        Args:
            email: User email whose post queue to process
        """
        print(f"\n🎯 POST processor started for: {email}")
        print(
            f"   Initial POST queue size: {len(self.user_post_queues[email])}")

        while True:
            # Get next post operation
            operation = None
            with self.lock:
                if self.user_post_queues[email]:
                    operation = self.user_post_queues[email].popleft()
                else:
                    # No more post operations, mark as inactive
                    self.user_status[email]['post_active'] = False
                    break

            if operation:
                # Update status
                self.user_status[email]['current_post_operation'] = 'Posting'
                self.user_status[email]['last_activity'] = timezone.now()

                print(f"\n▶️ Processing POST for {email}")
                print(
                    f"   Remaining POST operations: {len(self.user_post_queues[email])}")

                # Process the posting operation
                try:
                    self._execute_posting(operation)

                    # Update completed count
                    with self.lock:
                        self.user_status[email]['posts_completed'] += 1

                    print(f"✅ Completed POST operation for {email}")

                except Exception as e:
                    print(f"❌ Error processing POST for {email}: {str(e)}")
                    logger.error(
                        f"Post operation failed for {email}: {str(e)}")

                # Clear current operation status
                self.user_status[email]['current_post_operation'] = None

                # Small delay between operations
                time.sleep(1)

        print(f"🏁 POST processor finished for: {email}")
        print(
            f"   Total posts completed: {self.user_status[email]['posts_completed']}")

    def _process_renew_queue(self, email):
        """
        Process RENEW operations sequentially for a specific user

        Args:
            email: User email whose renew queue to process
        """
        print(f"\n🎯 RENEW processor started for: {email}")
        print(
            f"   Initial RENEW queue size: {len(self.user_renew_queues[email])}")

        while True:
            # Get next renew operation
            operation = None
            with self.lock:
                if self.user_renew_queues[email]:
                    operation = self.user_renew_queues[email].popleft()
                else:
                    # No more renew operations, mark as inactive
                    self.user_status[email]['renew_active'] = False
                    break

            if operation:
                # Update status
                self.user_status[email]['current_renew_operation'] = 'Renewing'
                self.user_status[email]['last_activity'] = timezone.now()

                print(f"\n▶️ Processing RENEW for {email}")
                print(
                    f"   Remaining RENEW operations: {len(self.user_renew_queues[email])}")

                # Process the renewing operation
                try:
                    self._execute_renewing(operation)

                    # Update completed count
                    with self.lock:
                        self.user_status[email]['renews_completed'] += 1

                    print(f"✅ Completed RENEW operation for {email}")

                except Exception as e:
                    print(f"❌ Error processing RENEW for {email}: {str(e)}")
                    logger.error(
                        f"Renew operation failed for {email}: {str(e)}")

                # Clear current operation status
                self.user_status[email]['current_renew_operation'] = None

                # Small delay between operations
                time.sleep(1)

        print(f"🏁 RENEW processor finished for: {email}")
        print(
            f"   Total renews completed: {self.user_status[email]['renews_completed']}")

    def _execute_posting(self, operation):
        """
        Simply calls your EXISTING login_and_post function
        No new code - just using what you already have!
        """
        email = operation['email']
        data = operation['data']

        print(f"📝 Calling YOUR EXISTING posting function for: {email}")

        # ✅ CALLS YOUR EXISTING FUNCTION - NO MODIFICATIONS
        result = login_and_post(
            email=email,
            title=data['title'],
            description=data['description'],
            price=data['price'],
            image_path=data['image_path'],
            headless=False  # Change to True for production
        )

        return result

    def _execute_renewing(self, operation):
        """
        Simply calls your EXISTING renew_listings function
        No new code - just using what you already have!
        """
        email = operation['email']
        data = operation['data']

        print(f"🔄 Calling YOUR EXISTING renewing function for: {email}")

        # ✅ CALLS YOUR EXISTING FUNCTION - NO MODIFICATIONS

        result = renew_listings(
            email=email,
            renewal_count=data['renewal_count'],
            headless=False  # Change to True for production
        )

        return result

    def _cleanup_post_processor(self, email):
        """
        Clean up post processor when done

        Args:
            email: User email to cleanup
        """
        with self.lock:
            if email in self.user_post_processors:
                self.user_post_processors[email].shutdown(wait=False)
                del self.user_post_processors[email]

            self.user_status[email]['post_active'] = False
            self.user_status[email]['current_post_operation'] = None

    def _cleanup_renew_processor(self, email):
        """
        Clean up renew processor when done

        Args:
            email: User email to cleanup
        """
        with self.lock:
            if email in self.user_renew_processors:
                self.user_renew_processors[email].shutdown(wait=False)
                del self.user_renew_processors[email]

            self.user_status[email]['renew_active'] = False
            self.user_status[email]['current_renew_operation'] = None

    def get_user_status(self, email):
        """
        Get current status for a user

        Args:
            email: User email

        Returns:
            dict: Status information
        """
        with self.lock:
            status = self.user_status[email].copy()
            status['post_queue_size'] = len(self.user_post_queues[email])
            status['renew_queue_size'] = len(self.user_renew_queues[email])
            status['total_queue_size'] = status['post_queue_size'] + \
                status['renew_queue_size']
            return status

    def get_all_users_status(self):
        """
        Get status for all users

        Returns:
            dict: All users' status information
        """
        with self.lock:
            all_status = {}
            all_emails = set(
                list(self.user_status.keys()) +
                list(self.user_post_queues.keys()) +
                list(self.user_renew_queues.keys())
            )
            for email in all_emails:
                status = self.user_status[email].copy()
                status['post_queue_size'] = len(self.user_post_queues[email])
                status['renew_queue_size'] = len(self.user_renew_queues[email])
                status['total_queue_size'] = status['post_queue_size'] + \
                    status['renew_queue_size']
                all_status[email] = status
            return all_status

    def shutdown(self):
        """
        Shutdown all processors and clean up
        """
        print("🛑 Shutting down Sequential Browser Manager...")

        with self.lock:
            for email, executor in self.user_post_processors.items():
                executor.shutdown(wait=False)
            for email, executor in self.user_renew_processors.items():
                executor.shutdown(wait=False)
            self.user_post_processors.clear()
            self.user_renew_processors.clear()

        print("✅ Sequential Browser Manager shutdown complete")


# Create global instance
sequential_manager = SequentialBrowserManager()


def post_to_marketplace_sequential(email, title, description, price, image_path):
    """
    Add posting operation to sequential queue

    Args:
        email: Facebook account email
        title: Post title
        description: Post description
        price: Item price
        image_path: Path to product image

    Returns:
        dict: Status information
    """
    sequential_manager.add_posting_operation(
        email, title, description, price, image_path)

    return {
        'status': 'queued',
        'message': f'Posting operation added to queue for {email}',
        'user_status': sequential_manager.get_user_status(email)
    }


def renew_listings_sequential(email, renewal_count=20):
    """
    Add renewing operation to sequential queue

    Args:
        email: Facebook account email
        renewal_count: Number of listings to renew

    Returns:
        dict: Status information
    """
    sequential_manager.add_renewing_operation(email, renewal_count)

    return {
        'status': 'queued',
        'message': f'Renewing operation added to queue for {email}',
        'user_status': sequential_manager.get_user_status(email)
    }


def get_user_automation_status(email):
    """
    Get automation status for a user

    Args:
        email: User email

    Returns:
        dict: User status information
    """
    return sequential_manager.get_user_status(email)


def get_all_automation_status():
    """
    Get automation status for all users

    Returns:
        dict: All users' status information
    """
    return sequential_manager.get_all_users_status()
