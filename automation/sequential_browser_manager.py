"""
Sequential Queue Manager for Facebook Marketplace Bot
====================================================

✅ TRUE SEQUENTIAL - GLOBAL QUEUES:
- ONE global POST queue for ALL users
- ONE global RENEW queue for ALL users  
- Each queue processes ONE operation at a time (TRUE sequential)
- Both queues can run in parallel (max 2 browsers total, not per user)

EXAMPLE:
User1 adds: Post1, Renew1
User2 adds: Post2, Renew2
User3 adds: Post3, Renew3

GLOBAL POST Queue: [Post1, Post2, Post3]  → Processes 1-by-1
GLOBAL RENEW Queue: [Renew1, Renew2, Renew3]  → Processes 1-by-1

Max 2 browsers total = POST browser + RENEW browser (not multiplied by users)
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
    Manages 2 GLOBAL sequential queues (not per user)

    STRUCTURE:
    - ONE global POST queue for all users
    - ONE global RENEW queue for all users
    - Each queue processes one operation at a time (TRUE sequential)
    - Both queues can run in parallel (max 2 browsers total)
    """

    def __init__(self):
        # ✅ GLOBAL QUEUES - all users share the same queues
        self.global_post_queue = deque()     # All POST operations
        self.global_renew_queue = deque()    # All RENEW operations

        # Single processors for global queues
        self.post_processor = None   # One posting processor
        self.renew_processor = None  # One renewing processor

        # Track status for monitoring
        self.status = {
            'post_active': False,
            'renew_active': False,
            'current_post_operation': None,
            'current_renew_operation': None,
            'total_posts_queued': 0,
            'total_renews_queued': 0,
            'posts_completed': 0,
            'renews_completed': 0,
            'last_activity': None
        }

        # Thread lock for thread-safe operations
        self.lock = threading.Lock()

        print("🚀 Sequential Browser Manager initialized (GLOBAL queues - TRUE sequential)")

    def add_posting_operation(self, email, title, description, price, image_path):
        """
        Add a posting operation to GLOBAL POST queue

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
            self.global_post_queue.append(operation)
            self.status['total_posts_queued'] += 1

            print(f"📝 Added POSTING operation for {email}")
            print(f"   GLOBAL POST queue size: {len(self.global_post_queue)}")

            # Start post processor if not already active
            if not self.status['post_active']:
                self._start_post_processor()

    def add_renewing_operation(self, email, renewal_count=20):
        """
        Add a renewing operation to GLOBAL RENEW queue

        Args:
            email: Facebook account email
            renewal_count: Number of listings to renew
        """
        operation = {
            'type': 'renew',
            'email': email,
            'data': {
                'renewal_count': renewal_count
            },
            'timestamp': timezone.now()
        }

        with self.lock:
            self.global_renew_queue.append(operation)
            self.status['total_renews_queued'] += 1

            print(f"🔄 Added RENEWING operation for {email}")
            print(
                f"   GLOBAL RENEW queue size: {len(self.global_renew_queue)}")

            # Start renew processor if not already active
            if not self.status['renew_active']:
                self._start_renew_processor()

    def _start_post_processor(self):
        """
        Start GLOBAL sequential processor for POST queue
        """
        if self.post_processor:
            # Already has a post processor
            return

        # Create single-threaded executor for sequential post processing
        self.post_processor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="global_post")
        self.status['post_active'] = True

        # Submit the processing task
        future = self.post_processor.submit(self._process_post_queue)
        future.add_done_callback(lambda f: self._cleanup_post_processor())

        print(f"🎬 Started GLOBAL POST processor")

    def _start_renew_processor(self):
        """
        Start GLOBAL sequential processor for RENEW queue
        """
        if self.renew_processor:
            # Already has a renew processor
            return

        # Create single-threaded executor for sequential renew processing
        self.renew_processor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="global_renew")
        self.status['renew_active'] = True

        # Submit the processing task
        future = self.renew_processor.submit(self._process_renew_queue)
        future.add_done_callback(lambda f: self._cleanup_renew_processor())

        print(f"🎬 Started GLOBAL RENEW processor")

    def _process_post_queue(self):
        """
        Process POST operations sequentially from GLOBAL queue
        """
        print(f"\n🎯 GLOBAL POST processor started")
        print(f"   Initial POST queue size: {len(self.global_post_queue)}")

        while True:
            # Get next post operation
            operation = None
            with self.lock:
                if self.global_post_queue:
                    operation = self.global_post_queue.popleft()
                else:
                    # No more post operations, mark as inactive
                    self.status['post_active'] = False
                    break

            if operation:
                email = operation['email']

                # Update status
                self.status['current_post_operation'] = f'Posting for {email}'
                self.status['last_activity'] = timezone.now()

                print(f"\n▶️ Processing POST for {email}")
                print(
                    f"   Remaining POST operations: {len(self.global_post_queue)}")

                # Process the posting operation
                try:
                    self._execute_posting(operation)

                    # Update completed count
                    with self.lock:
                        self.status['posts_completed'] += 1

                    print(f"✅ Completed POST operation for {email}")

                except Exception as e:
                    print(f"❌ Error processing POST for {email}: {str(e)}")
                    logger.error(
                        f"Post operation failed for {email}: {str(e)}")

                # Clear current operation status
                self.status['current_post_operation'] = None

                # Small delay between operations
                time.sleep(1)

        print(f"🏁 GLOBAL POST processor finished")
        print(f"   Total posts completed: {self.status['posts_completed']}")

    def _process_renew_queue(self):
        """
        Process RENEW operations sequentially from GLOBAL queue
        """
        print(f"\n🎯 GLOBAL RENEW processor started")
        print(f"   Initial RENEW queue size: {len(self.global_renew_queue)}")

        while True:
            # Get next renew operation
            operation = None
            with self.lock:
                if self.global_renew_queue:
                    operation = self.global_renew_queue.popleft()
                else:
                    # No more renew operations, mark as inactive
                    self.status['renew_active'] = False
                    break

            if operation:
                email = operation['email']

                # Update status
                self.status['current_renew_operation'] = f'Renewing for {email}'
                self.status['last_activity'] = timezone.now()

                print(f"\n▶️ Processing RENEW for {email}")
                print(
                    f"   Remaining RENEW operations: {len(self.global_renew_queue)}")

                # Process the renewing operation
                try:
                    self._execute_renewing(operation)

                    # Update completed count
                    with self.lock:
                        self.status['renews_completed'] += 1

                    print(f"✅ Completed RENEW operation for {email}")

                except Exception as e:
                    print(f"❌ Error processing RENEW for {email}: {str(e)}")
                    logger.error(
                        f"Renew operation failed for {email}: {str(e)}")

                # Clear current operation status
                self.status['current_renew_operation'] = None

                # Small delay between operations
                time.sleep(1)

        print(f"🏁 GLOBAL RENEW processor finished")
        print(f"   Total renews completed: {self.status['renews_completed']}")

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

    def _cleanup_post_processor(self):
        """Clean up post processor when done"""
        with self.lock:
            if self.post_processor:
                self.post_processor.shutdown(wait=False)
                self.post_processor = None

            self.status['post_active'] = False
            self.status['current_post_operation'] = None

    def _cleanup_renew_processor(self):
        """Clean up renew processor when done"""
        with self.lock:
            if self.renew_processor:
                self.renew_processor.shutdown(wait=False)
                self.renew_processor = None

            self.status['renew_active'] = False
            self.status['current_renew_operation'] = None

    def get_user_status(self, email):
        """
        Get current status for a specific user

        Args:
            email: User email

        Returns:
            dict: Status information for this user
        """
        # Return global status (applies to all users now)
        with self.lock:
            return {
                **self.status,
                'post_queue_size': len(self.global_post_queue),
                'renew_queue_size': len(self.global_renew_queue),
                'total_queue_size': len(self.global_post_queue) + len(self.global_renew_queue),
            }

    def get_all_users_status(self):
        """
        Get global status (all users share same queues)

        Returns:
            dict: Global status information
        """
        with self.lock:
            return {
                **self.status,
                'post_queue_size': len(self.global_post_queue),
                'renew_queue_size': len(self.global_renew_queue),
                'total_queue_size': len(self.global_post_queue) + len(self.global_renew_queue),
            }

    def shutdown(self):
        """
        Shutdown all processors and clean up
        """
        print("🛑 Shutting down Sequential Browser Manager...")

        with self.lock:
            if self.post_processor:
                self.post_processor.shutdown(wait=False)
            if self.renew_processor:
                self.renew_processor.shutdown(wait=False)
            self.post_processor = None
            self.renew_processor = None

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
