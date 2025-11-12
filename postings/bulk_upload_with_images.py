"""
Bulk Upload with Images - Enhanced API View
This allows users to upload TXT + multiple image files
Images are automatically matched BY ORDER (1st image → 1st product, 2nd image → 2nd product, etc.)
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import MarketplacePost
from accounts.models import FacebookAccount
from django.utils import timezone
import random
import re


class BulkUploadWithImagesView(APIView):
    """
    Accept TXT + multiple image files (no ZIP needed!)
    Images are automatically matched by ORDER:
    - 1st image → 1st product
    - 2nd image → 2nd product
    - 3rd image → 3rd product

    TXT Format (each product has 3 lines + blank line):
    Title
    Description
    Price

    Title 2
    Description 2
    Price 2
    """

    def post(self, request):
        # Get files
        txt_file = request.FILES.get('txt_file')
        image_files = request.FILES.getlist('images')  # Multiple image files
        account_ids = request.data.getlist('account_ids[]')

        # Validation
        if not txt_file:
            return Response(
                {'error': 'TXT file is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not account_ids:
            return Response(
                {'error': 'At least one account must be selected'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get accounts
        try:
            accounts = FacebookAccount.objects.filter(
                id__in=account_ids
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

        # Parse TXT/CSV compact formats
        try:
            decoded_file = txt_file.read().decode('utf-8')
            # Normalize newlines and split
            raw_lines = [l.strip() for l in re.split(r'\r?\n', decoded_file) if l.strip()]

            success_count = 0
            error_count = 0
            errors = []
            posts_data = []

            # Helper to parse a compact single-line format
            # Examples accepted:
            #   "Nice chair | 10-40"
            #   "Nice chair|10-40"
            #   "Nice chair - 10-40"
            price_range_re = re.compile(r"(\d+(?:\.\d+)? )?\s*(\d+(?:\.\d+)?)?\s*-\s*(\d+(?:\.\d+)?)")

            def parse_compact_line(line):
                # If there's a pipe, split into parts
                if '|' in line:
                    parts = [p.strip() for p in line.split('|') if p.strip()]
                    title = parts[0]
                    if len(parts) == 1:
                        description = title
                        price_spec = None
                    elif len(parts) == 2:
                        # assume last part is price or range
                        price_spec = parts[1]
                        description = title
                    else:
                        # title | description | price
                        description = parts[1]
                        price_spec = parts[-1]
                else:
                    # Try to find a price range with regex
                    m = re.search(r"(\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?)", line)
                    if m:
                        price_spec = m.group(1)
                        title = line.replace(m.group(1), '').strip(' -|,')
                        description = title
                    else:
                        # No price specified - treat whole line as title
                        title = line
                        description = title
                        price_spec = None

                # Normalize price_spec
                price = None
                price_low = None
                price_high = None
                if price_spec:
                    # handle single number or range
                    if '-' in price_spec:
                        try:
                            parts = [p.strip() for p in price_spec.split('-')]
                            low = float(parts[0])
                            high = float(parts[1])
                            if low > high:
                                low, high = high, low
                            # store range; sampling will be done per-post later
                            price_low = low
                            price_high = high
                        except Exception:
                            price_low = price_high = None
                    else:
                        try:
                            price = float(price_spec)
                        except Exception:
                            price = None

                return {
                    'title': title,
                    'description': description,
                    'price': price,
                    'price_low': price_low,
                    'price_high': price_high
                }

            # Detect format: if the file appears to be triple-line per product (old format)
            # we can try to detect by presence of multiple lines that look like a price-only line
            def looks_like_old_format(lines):
                # old format uses groups of 3 lines; check if there are price-like lines every 3rd line
                if len(lines) < 3:
                    return False
                sample_count = min(3, len(lines)//3)
                for i in range(sample_count):
                    idx = i*3 + 2
                    if idx < len(lines):
                        if re.match(r"^\d+(?:\.\d+)?$", lines[idx]):
                            return True
                return False

            if looks_like_old_format(raw_lines):
                # Parse original 3-line-per-product format
                i = 0
                product_index = 0
                while i < len(raw_lines):
                    try:
                        if i + 2 >= len(raw_lines):
                            errors.append({'line': i + 1, 'error': 'Incomplete product data (need 3 lines: title, description, price)'} )
                            error_count += 1
                            break
                        title = raw_lines[i]
                        description = raw_lines[i+1]
                        price_str = raw_lines[i+2]
                        try:
                            price_decimal = float(price_str)
                        except ValueError:
                            errors.append({'line': i + 3, 'error': f'Invalid price: {price_str}'})
                            error_count += 1
                            i += 3
                            product_index += 1
                            continue

                        posts_data.append({'title': title, 'description': description, 'price': price_decimal, 'price_low': None, 'price_high': None})
                        product_index += 1
                        i += 3
                    except Exception as e:
                        errors.append({'line': i+1, 'error': str(e)})
                        error_count += 1
                        i += 3

            else:
                # Compact single-line format: one product per line, with optional price or range
                for idx, line in enumerate(raw_lines):
                    parsed = parse_compact_line(line)
                    posts_data.append(parsed)

            # Now map images to posts
            final_posts = []

            if image_files:
                num_images = len(image_files)
                num_products = len(posts_data)

                # Case: single product + multiple images -> replicate product for each image
                if num_products == 1 and num_images >= 1:
                    base = posts_data[0]
                    for img in image_files:
                        # If base.price is None -> leave None (error will be reported)
                        final_posts.append({
                            'title': base['title'],
                            'description': base['description'],
                            'price': base.get('price'),
                            'price_low': base.get('price_low'),
                            'price_high': base.get('price_high'),
                            'image_file': img
                        })
                else:
                    # General mapping: pair by order up to max(products, images)
                    max_count = max(num_products, num_images)
                    for i in range(max_count):
                        prod = posts_data[i] if i < num_products else None
                        img = image_files[i] if i < num_images else None
                        if prod:
                            final_posts.append({
                                'title': prod['title'],
                                'description': prod.get('description') or prod['title'],
                                'price': prod.get('price'),
                                'price_low': prod.get('price_low'),
                                'price_high': prod.get('price_high'),
                                'image_file': img
                            })
                        else:
                            # No product but image exists - create a generic post using image filename as title
                            title = getattr(img, 'name', 'Untitled')
                            final_posts.append({
                                'title': title,
                                'description': title,
                                'price': None,
                                'price_low': None,
                                'price_high': None,
                                'image_file': img
                            })
            else:
                # No images uploaded: create posts from parsed data (images None)
                for prod in posts_data:
                    final_posts.append({
                        'title': prod['title'],
                        'description': prod.get('description') or prod['title'],
                        'price': prod.get('price'),
                        'price_low': prod.get('price_low'),
                        'price_high': prod.get('price_high'),
                        'image_file': None
                    })

            # Create posts for all accounts
            for post_data in final_posts:
                # Determine actual price per post: if a range was provided, sample per post
                actual_price = None
                if post_data.get('price') is not None:
                    # Convert explicit price to integer (no decimals)
                    try:
                        actual_price = int(round(float(post_data.get('price'))))
                    except Exception:
                        actual_price = None
                elif post_data.get('price_low') is not None and post_data.get('price_high') is not None:
                    try:
                        low = float(post_data.get('price_low'))
                        high = float(post_data.get('price_high'))
                        if low > high:
                            low, high = high, low
                        # Sample a value and convert to integer (no decimals)
                        actual_price = int(round(random.uniform(low, high)))
                    except Exception:
                        actual_price = None
                else:
                    actual_price = None

                # Build description from title (do NOT include suggested price)
                desc = post_data.get('description') or post_data.get('title')

                for account in accounts:
                    post = MarketplacePost.objects.create(
                        account=account,
                        title=post_data['title'],
                        description=desc,
                        price=actual_price if actual_price is not None else 0.0,
                        scheduled_time=timezone.now(),
                        posted=False
                    )

                    if post_data.get('image_file'):
                        post.image.save(
                            post_data['image_file'].name,
                            post_data['image_file'],
                            save=True
                        )

                    success_count += 1

            response_data = {
                'success': True,
                'message': f'Created {success_count} posts!',
                'stats': {
                    'success_count': success_count,
                    'error_count': error_count,
                    'num_posts_created': len(final_posts),
                    'num_accounts': len(accounts)
                }
            }

            if errors:
                response_data['errors'] = errors[:20]
                if len(errors) > 20:
                    response_data['additional_errors'] = len(errors) - 20

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'Error processing TXT file: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
