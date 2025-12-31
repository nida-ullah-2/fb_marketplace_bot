from playwright.sync_api import sync_playwright
import os
from django.conf import settings


def debug_page_state(page, step_name):
    """Helper function to debug page state at any point"""
    print(f"\n🔍 DEBUG: {step_name}")
    print(f"   URL: {page.url}")

    # Check for error messages
    errors = page.locator("[role='alert'], .error").all()
    error_count = sum(1 for e in errors if e.is_visible())
    if error_count > 0:
        print(f"   ⚠️ Found {error_count} error message(s)")

    # Check for buttons
    buttons = page.locator("button").all()
    visible_buttons = []
    for btn in buttons:
        try:
            if btn.is_visible():
                text = btn.inner_text()[:50]  # Limit text length
                if text.strip():
                    visible_buttons.append(text.strip())
        except Exception:
            pass

    if visible_buttons:
        # Show first 5 unique
        print(f"   📍 Visible buttons: {', '.join(set(visible_buttons[:5]))}")
    else:
        print("   ⚠️ No visible buttons found")
    print()


def renew_listings(email, renewal_count=20, headless=False):
    """
    Renew marketplace listings for a Facebook account

    Args:
        email: Facebook account email
        renewal_count: Number of listings to renew (default: 20)
        headless: Run in headless mode (default: False for debugging)

    Returns:
        dict: Result with success status, renewed count, and details
    """
    session_file = f"sessions/{email.replace('@', '_').replace('.', '_')}.json"
    if not os.path.exists(session_file):
        return {
            'success': False,
            'renewed_count': 0,
            'available_count': 0,
            'message': 'Session file not found. Please import session first.',
            'condition_met': ''
        }

    result = {
        'success': False,
        'renewed_count': 0,
        'available_count': 0,
        'message': '',
        'condition_met': ''
    }

    with sync_playwright() as p:
        # Use settings value if headless parameter not explicitly provided
        use_headless = headless if headless is not None else getattr(
            settings, 'AUTOMATION_HEADLESS_MODE', False)

        if use_headless:
            print("🤖 Running in HEADLESS mode")
        else:
            print("🖥️  Running in VISIBLE mode (browser window will open)")

        browser = p.chromium.launch(headless=use_headless)
        context = browser.new_context(storage_state=session_file)
        page = context.new_page()

        try:
            # First, login to Facebook using session
            print(f"🌐 Logging in to Facebook for {email}...")
            page.goto('https://www.facebook.com', timeout=60000)
            page.wait_for_timeout(1500)

            # Check current URL to verify login
            current_url = page.url
            print(f"📍 After login, URL: {current_url}")

            # Check if we got redirected to login
            if 'login' in current_url.lower():
                result['message'] = 'Session expired. Please re-import session.'
                print("❌ Session expired - redirected to login")
                page.screenshot(path="renewal_session_expired.png")
                print("📷 Screenshot saved as renewal_session_expired.png")
                browser.close()
                return result

            print(f"✅ Logged in successfully")

            # Now navigate to the renewal page
            print(f"🔄 Opening renewal page...")
            page.goto('https://www.facebook.com/marketplace/selling/renew_listings/?is_routable_dialog=true',
                      timeout=60000)

            # Wait for page to load
            page.wait_for_timeout(1500)

            # Debug: Check page state after loading (only when needed)
            # debug_page_state(page, "After loading renewal page")

            # Check current URL
            current_url = page.url
            print(f"📍 Current URL: {current_url}")

            # Check if we got redirected to login
            if 'login' in current_url.lower():
                result['message'] = 'Session expired. Please re-import session.'
                print("❌ Session expired - redirected to login")
                page.screenshot(path="renewal_session_expired.png")
                print("📷 Screenshot saved as renewal_session_expired.png")
                browser.close()
                return result

            print(f"🔍 Looking for Renew buttons...")

            # Wait for Renew buttons to load
            try:
                page.wait_for_selector(
                    'div[role="button"]:has-text("Renew"), button:has-text("Renew")',
                    timeout=6000
                )
                page.wait_for_timeout(1000)
            except Exception as e:
                # Check if it's the "no more listings" scenario
                try:
                    no_listings_message = page.locator(
                        'text=/You have no more listings eligible to be renewed/i')
                    if no_listings_message.is_visible(timeout=3000):
                        result['renewed_count'] = 0
                        result['available_count'] = 0
                        result['message'] = 'No listings available for renewal'
                        result['success'] = True
                        print(f"✅ {result['message']}")
                        browser.close()
                        return result
                except Exception:
                    pass

                # If not the "no listings" case, it's a real error
                result['message'] = f'No Renew buttons found: {str(e)}'
                print(f"❌ {result['message']}")
                page.screenshot(path="renew_buttons_not_found.png")
                print("📷 Screenshot saved as renew_buttons_not_found.png")
                browser.close()
                return result

            # Find all Renew buttons
            renew_buttons = page.locator(
                'div[role="button"]:has-text("Renew"), button:has-text("Renew")'
            ).all()

            result['available_count'] = len(renew_buttons)
            print(
                f"📊 Found {result['available_count']} listings available for renewal")

            if result['available_count'] == 0:
                result['message'] = 'No listings available for renewal'
                result['success'] = True
                print(f"✅ {result['message']}")
                browser.close()
                return result

            clicks_done = 0

            # Debug: Check page state before starting clicks (disabled for speed)
            # debug_page_state(page, "Before starting renewal clicks")

            print(f"🔄 Starting to renew listings (target: {renewal_count})...")

            # Click renewal buttons
            for i, button in enumerate(renew_buttons):
                # CONDITION 2: Reached user's number
                if clicks_done >= renewal_count:
                    result['renewed_count'] = clicks_done
                    result['message'] = f'Renewed {clicks_done} of {result["available_count"]} available'
                    result['condition_met'] = 'Condition 2: Reached target'
                    result['success'] = True
                    print(f"✅ {result['message']} (Reached target)")
                    browser.close()
                    return result

                try:
                    if button.is_visible():
                        # Force click to bypass overlays
                        try:
                            button.scroll_into_view_if_needed()
                            button.click(force=True, timeout=3000)
                        except:
                            # Fallback: JavaScript click
                            try:
                                page.evaluate(
                                    '(element) => element.click()', button.element_handle())
                            except Exception as js_error:
                                print(
                                    f"⚠️  Could not click button {i+1}: {str(js_error)}")
                                continue

                        clicks_done += 1
                        print(
                            f"🔄 Renewed listing {clicks_done}/{renewal_count}")

                        # Small delay between clicks
                        page.wait_for_timeout(150)

                except Exception as click_error:
                    print(f"⚠️  Error with button {i+1}: {str(click_error)}")
                    continue

            # Check if we renewed any but stopped because no more buttons were clickable
            if clicks_done < renewal_count and clicks_done > 0:
                # Check if "Relist Other Items" is visible (meaning all available renewed)
                try:
                    if page.locator('text=/Relist Other Items/i').is_visible(timeout=2000):
                        result['renewed_count'] = clicks_done
                        result[
                            'message'] = f'Renewed {clicks_done} of {result["available_count"]} available (wanted {renewal_count})'
                        result['condition_met'] = 'Condition 1: All available renewed'
                        result['success'] = True
                        print(f"✅ {result['message']} (All available renewed)")
                        browser.close()
                        return result
                except Exception:
                    pass

            # If we finished loop without closing
            result['renewed_count'] = clicks_done
            result['message'] = f'Renewed {clicks_done} listings'
            result['success'] = True
            print(f"✅ {result['message']}")
            browser.close()
            return result

        except Exception as e:
            result['message'] = f'Error during renewal: {str(e)}'
            print(f"❌ {result['message']}")

            try:
                page.screenshot(path="renewal_error.png")
                print("📷 Screenshot saved as renewal_error.png")
            except:
                pass

            browser.close()
            return result
