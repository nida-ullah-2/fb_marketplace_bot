from playwright.sync_api import sync_playwright
import time
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


def save_session(email, password=None):
    """
    Save Facebook login session
    Always runs with visible browser (headless=False) so user can solve CAPTCHA
    """
    with sync_playwright() as p:
        print("🖥️  Opening browser for login (visible mode for CAPTCHA solving)")
        browser = p.chromium.launch(headless=False)  # Always visible for login
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.facebook.com/login",
                  wait_until="domcontentloaded")

        login_successful = False

        if password:
            print(f"🔐 Auto-logging in for: {email}")

            try:
                page.fill('input[name="email"]', email)
                page.fill('input[name="pass"]', password)
                page.click('button[name="login"]')

                print("⏳ Waiting for login response...")
                time.sleep(5)

                # Check if still on login page or error occurred
                current_url = page.url

                # Check for various login failure indicators
                is_still_login = (
                    "login" in current_url or
                    page.locator('input[name="email"]').is_visible() or
                    page.locator('input[name="pass"]').is_visible()
                )

                # Check for checkpoint/captcha
                is_checkpoint = (
                    "checkpoint" in current_url or
                    "captcha" in current_url or
                    page.locator('text=Security Check').is_visible() or
                    page.locator('text=Enter the code').is_visible()
                )

                if is_checkpoint:
                    print("🔒 Captcha/2FA/Checkpoint detected!")
                    print("👉 Please solve it manually in the browser...")
                    print("⏳ Waiting 90 seconds for you to complete...")
                    time.sleep(90)

                    # Verify login after manual intervention
                    current_url = page.url
                    is_logged_in = (
                        "facebook.com" in current_url and
                        "login" not in current_url and
                        "checkpoint" not in current_url and
                        not page.locator('input[name="email"]').is_visible()
                    )

                    if is_logged_in:
                        login_successful = True
                        print("✅ Login successful after solving checkpoint!")
                    else:
                        print("❌ Login still not completed - checkpoint not solved")

                elif is_still_login:
                    print("❌ Login failed - wrong password or blocked")

                else:
                    # Appears to be logged in
                    login_successful = True
                    print("✅ Auto-login successful!")

            except Exception as e:
                print(f"⚠️ Auto-login failed: {e}")
                print("👉 Please log in manually")
                time.sleep(60)

                # Check if manual login succeeded
                try:
                    current_url = page.url
                    if "login" not in current_url and not page.locator('input[name="email"]').is_visible():
                        login_successful = True
                        print("✅ Manual login successful!")
                except Exception:
                    pass
        else:
            print(f"👉 Please log in manually for: {email}")
            print("⏳ You have 60 seconds...")
            time.sleep(60)

            # Check if manual login succeeded
            try:
                current_url = page.url
                if "login" not in current_url and not page.locator('input[name="email"]').is_visible():
                    login_successful = True
                    print("✅ Manual login successful!")
            except Exception:
                pass

        if login_successful:
            session_path = f"sessions/{email.replace('@', '_').replace('.', '_')}.json"
            context.storage_state(path=session_path)
            print(f"✅ Session saved: {session_path}")
        else:
            print(f"❌ Session NOT saved - Login failed for {email}")

        browser.close()
        return login_successful


def manual_login_and_save_session(email):
    """
    Open browser and let user manually login to Facebook
    User types email, password, solves CAPTCHA, etc.
    Once logged in, session is saved automatically

    Args:
        email: Facebook account email (used for session filename)

    Returns:
        bool: True if session saved successfully, False otherwise
    """
    with sync_playwright() as p:
        print(f"\n🌐 Opening browser for MANUAL login...")
        print(f"📧 Account: {email}")
        print("=" * 60)
        print("📝 INSTRUCTIONS:")
        print("   1. Browser will open to Facebook login page")
        print("   2. Manually type your email and password")
        print("   3. Solve any CAPTCHA or security checks")
        print("   4. Complete 2FA if required")
        print("   5. Wait until you see Facebook homepage")
        print("   6. Browser will close automatically and save session")
        print("=" * 60)
        print("⏳ You have 120 seconds to complete login...")
        print()

        # Slower for better observation
        browser = p.chromium.launch(headless=False, slow_mo=100)

        # Add realistic browser settings
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1366, 'height': 768},
            locale='en-US',
            timezone_id='America/New_York'
        )

        page = context.new_page()

        # Go to Facebook login
        print("🌐 Loading Facebook login page...")
        page.goto("https://www.facebook.com/login",
                  wait_until="domcontentloaded", timeout=30000)

        login_successful = False
        check_interval = 5  # Check every 5 seconds
        # 5 minutes total (increased for 2FA/device approval)
        max_wait_time = 300
        elapsed_time = 0
        last_status = None  # Track status changes

        print("👀 Waiting for you to login manually...")
        print("💡 Tip: Take your time, the bot is watching and waiting!")
        print("⏰ Extended wait time: Up to 5 minutes for 2FA/device approval")
        print()

        # Monitor login progress
        while elapsed_time < max_wait_time:
            time.sleep(check_interval)
            elapsed_time += check_interval

            try:
                # Check if browser/page is still open
                if page.is_closed():
                    print("\n🔒 Browser closed by user")
                    print("❌ Login cancelled")
                    break

                current_url = page.url
                current_status = None

                # Check if login form is still visible
                login_form_visible = False
                try:
                    login_form_visible = page.locator(
                        'input[name="email"]').is_visible(timeout=1000)
                except:
                    pass

                # Determine current status
                if "checkpoint" in current_url or page.locator('text=/Security Check|Enter the code|Two-factor|Approve/i').count() > 0:
                    current_status = "checkpoint"
                elif "captcha" in current_url:
                    current_status = "captcha"
                elif login_form_visible or "login" in current_url:
                    current_status = "login"
                elif "facebook.com" in current_url:
                    # Additional checks to confirm we're on Facebook homepage/feed
                    try:
                        # Check for common Facebook homepage elements
                        is_home = (
                            page.locator('[aria-label*="Home"]').count() > 0 or
                            page.locator('[aria-label*="News Feed"]').count() > 0 or
                            page.locator('[role="main"]').count() > 0 or
                            page.locator(
                                'text=/What\'s on your mind|Create post/i').count() > 0
                        )
                        if is_home:
                            current_status = "logged_in"
                        else:
                            current_status = "unknown"
                    except:
                        # If we can't check, assume logged in if not on login/checkpoint
                        current_status = "logged_in"
                else:
                    current_status = "unknown"

                # Check if successfully logged in
                if current_status == "logged_in":
                    login_successful = True
                    print("\n✅ Login detected! You're now logged into Facebook!")
                    print("💾 Saving session...")
                    # Wait a bit more to ensure page is fully loaded
                    time.sleep(3)
                    break

                # Show progress only if status changed
                if current_status != last_status:
                    remaining = max_wait_time - elapsed_time
                    print(f"\n⏳ Status update ({remaining}s remaining):")

                    if current_status == "checkpoint":
                        print("   🔐 2FA/Checkpoint detected")
                        print(
                            "   👉 Please complete verification or approve from your device")
                        print("   ⏰ Bot will keep waiting until you're logged in...")
                    elif current_status == "captcha":
                        print("   🔒 CAPTCHA detected - please solve it")
                    elif current_status == "login":
                        print("   📝 Still on login page - please enter credentials")
                    elif current_status == "unknown":
                        print("   🔍 Processing... please wait")

                    last_status = current_status
                else:
                    # Just show a simple progress indicator every 30 seconds
                    if elapsed_time % 30 == 0:
                        remaining = max_wait_time - elapsed_time
                        print(f"⏳ Still waiting... ({remaining}s remaining)")

            except Exception as e:
                # If we get an error, browser might be closed
                error_str = str(e).lower()
                if "closed" in error_str or "target" in error_str:
                    print("\n🔒 Browser closed by user")
                    print("❌ Login cancelled")
                    break
                # Silently continue on other errors
                continue

        # Final check
        if not login_successful:
            print("\n⏰ Maximum wait time reached! Doing final check...")
            time.sleep(2)
            try:
                current_url = page.url
                login_form_visible = False
                try:
                    login_form_visible = page.locator(
                        'input[name="email"]').is_visible(timeout=1000)
                except:
                    pass

                # Check if we're on Facebook and not on login/checkpoint
                if "facebook.com" in current_url and "login" not in current_url and "checkpoint" not in current_url and not login_form_visible:
                    login_successful = True
                    print("✅ Login successful!")
                else:
                    print("❌ Login not completed")
                    print(f"   Current URL: {current_url}")
            except:
                pass

        # Save session if successful
        if login_successful:
            try:
                session_path = f"sessions/{email.replace('@', '_').replace('.', '_')}.json"
                os.makedirs("sessions", exist_ok=True)
                context.storage_state(path=session_path)
                print(f"✅ Session saved successfully: {session_path}")
                print("🎉 You can now use this account for automated posting!")
            except Exception as e:
                print(f"❌ Failed to save session: {e}")
                login_successful = False
        else:
            print("❌ Login failed or timed out")
            print("💡 Tip: Try again and complete login faster")

        print("\n🔒 Closing browser...")
        browser.close()

        return login_successful


def auto_login_and_save_session(email, password):
    """Automatically login to Facebook and save session"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"🌐 Opening Facebook login page...")
        page.goto("https://www.facebook.com/login", timeout=60000)
        page.wait_for_timeout(3000)

        print(f"📧 Entering email: {email}")
        email_input = page.locator("input[name='email']")
        email_input.fill(email)

        print(f"🔒 Entering password...")
        password_input = page.locator("input[name='pass']")
        password_input.fill(password)

        print(f"🔐 Clicking login button...")
        login_button = page.locator("button[name='login']")
        login_button.click()

        # Wait for login to complete
        print(f"⏳ Waiting for login to complete...")
        page.wait_for_timeout(10000)

        # Check if login was successful
        if "login" in page.url.lower():
            print(f"❌ Login may have failed - still on login page")
            browser.close()
            return False

        session_path = f"sessions/{email.replace('@', '_').replace('.', '_')}.json"
        context.storage_state(path=session_path)
        print(f"✅ Session saved: {session_path}")

        browser.close()
        return True


# def login_and_post(email, title, description, price, image_path, location):
def login_and_post(email, title, description, price, image_path, headless=False):
    """
    Post to Facebook Marketplace

    Args:
        email: Facebook account email
        title: Post title
        description: Post description
        price: Item price
        image_path: Path to product image
        headless: Run in headless mode (default: True for background posting)
    """
    session_file = f"sessions/{email.replace('@', '_').replace('.', '_')}.json"
    if not os.path.exists(session_file):
        raise Exception(
            f"❌ Session not found. Run save_session('{email}') first.")

    with sync_playwright() as p:
        # Run in headless mode by default for automated posting
        # Use settings value if headless parameter not explicitly provided
        use_headless = headless if headless is not None else getattr(
            settings, 'AUTOMATION_HEADLESS_MODE', True)

        if use_headless:
            print("🤖 Running in HEADLESS mode (background posting)")
        else:
            print("🖥️  Running in VISIBLE mode (browser window will open)")

        browser = p.chromium.launch(headless=use_headless)
        context = browser.new_context(storage_state=session_file)
        page = context.new_page()

        print("🌐 Opening Marketplace listing page...")
        page.goto("https://www.facebook.com/marketplace/create/item",
                  timeout=60000)

        try:
            print("📸 Uploading image first...")
            image_input = page.locator("input[type='file'][accept*='image']")
            image_input.set_input_files(image_path)
            page.wait_for_timeout(800)  # Reduced from 2000ms

            print("📝 Filling Title...")
            # Find all visible text inputs that are empty and not in the header
            text_inputs = page.locator("input[type='text']")
            title_input = None

            for i in range(text_inputs.count()):
                el = text_inputs.nth(i)
                # Check if visible and empty
                if el.is_visible() and el.input_value() == "":
                    # Optionally, skip if it's in the header (search bar)
                    # You can check its position on the page
                    box = el.bounding_box()
                    if box and box['y'] > 100:  # Skip inputs at the very top
                        title_input = el
                        break

            if not title_input:
                all_inputs = page.locator("input")
                print(
                    f"Found {all_inputs.count()} input fields. Printing their outerHTML:")
                for i in range(all_inputs.count()):
                    print(all_inputs.nth(i).evaluate("el => el.outerHTML"))
                raise Exception("Could not find title input field")

            title_input.fill(title)

            print("💰 Filling Price...")

            # Find all text inputs again
            text_inputs = page.locator("input[type='text']")
            price_input = None
            title_filled = False

            for i in range(text_inputs.count()):
                el = text_inputs.nth(i)
                if el.is_visible():
                    # If this is the title input, mark as found
                    if not title_filled and el.input_value() == title:
                        title_filled = True
                        continue
                    # The next visible, empty input after title is likely the price
                    if title_filled and el.input_value() == "":
                        price_input = el
                        break

            if not price_input:
                print(
                    "Could not find price input. Printing all text input values for debug:")
                for i in range(text_inputs.count()):
                    el = text_inputs.nth(i)
                    print(
                        f"Input {i}: value='{el.input_value()}', visible={el.is_visible()}")
                raise Exception("Could not find price input field")

            price_input.fill(str(price))
            # page.locator("text=Category").first.wait_for(
            # state="visible", timeout=10000)

            print("📂 Selecting Category...")
            category_clicked = False
            category_elements = page.locator("text=Category")
            for i in range(category_elements.count()):
                el = category_elements.nth(i)
                if el.is_visible():
                    el.scroll_into_view_if_needed()
                    el.click(force=True)
                    category_clicked = True
                    print("✅ Clicked on Category dropdown")
                    break

            if not category_clicked:
                print("❌ Could not find Category dropdown")
            else:
                # Wait for dropdown to fully open
                page.wait_for_timeout(500)  # Reduced from 2000ms

                # Try to select "Furniture"
                furniture_selected = False

                # Approach 1: Try role-based selection
                try:
                    furniture_option = page.get_by_role(
                        "option", name="Furniture")
                    if furniture_option.is_visible():
                        furniture_option.click()
                        furniture_selected = True
                        print("✅ Selected Category: Furniture (via role)")
                except Exception:
                    pass

                # Approach 2: Try text locator
                if not furniture_selected:
                    try:
                        furniture_options = page.locator(
                            "text='Furniture'").all()
                        for option in furniture_options:
                            if option.is_visible():
                                option.scroll_into_view_if_needed()
                                option.click(force=True)
                                furniture_selected = True
                                print("✅ Selected Category: Furniture (via text)")
                                break
                    except Exception:
                        pass

                if not furniture_selected:
                    print(
                        "❌ Could not select Furniture category - trying to continue anyway")

            print("🔧 Selecting Condition...")
            condition_elements = page.locator("text=Condition")
            condition_clicked = False
            for i in range(condition_elements.count()):
                el = condition_elements.nth(i)
                if el.is_visible():
                    el.scroll_into_view_if_needed()
                    el.click(force=True)
                    condition_clicked = True
                    print("✅ Clicked on Condition dropdown")
                    break

            if not condition_clicked:
                print("❌ Could not find Condition dropdown")
            else:
                # Wait for dropdown to fully open
                page.wait_for_timeout(500)  # Reduced from 2000ms

                # Try multiple approaches to find and click "New" condition
                new_clicked = False

                # Approach 1: Try exact text match with role
                try:
                    new_option = page.get_by_role("option", name="New")
                    if new_option.is_visible():
                        new_option.click()
                        new_clicked = True
                        print("✅ Selected Condition: New (via role)")
                except Exception:
                    pass

                # Approach 2: Try text locator with exact match
                if not new_clicked:
                    try:
                        # Find all elements containing "New" and filter
                        new_options = page.locator("text='New'").all()
                        for option in new_options:
                            if option.is_visible():
                                option.scroll_into_view_if_needed()
                                option.click(force=True)
                                new_clicked = True
                                print("✅ Selected Condition: New (via text)")
                                break
                    except Exception:
                        pass

                # Approach 3: Use keyboard navigation
                if not new_clicked:
                    try:
                        page.keyboard.press("Home")  # Go to top
                        page.keyboard.press("ArrowDown")  # Navigate to "New"
                        page.keyboard.press("Enter")
                        new_clicked = True
                        print("✅ Selected Condition: New (via keyboard)")
                    except Exception:
                        pass

                if not new_clicked:
                    print(
                        "❌ Could not select New condition - trying to continue anyway")

            print("🧾 Filling Description...")
            try:
                # Try by accessible name
                description_area = page.get_by_role(
                    "textbox", name="Description")
                description_area.fill(description)
            except Exception:
                # Fallback: use the first visible textarea
                textareas = page.locator("textarea")
                for i in range(textareas.count()):
                    el = textareas.nth(i)
                    if el.is_visible():
                        el.fill(description)
                        break

            print("📦 Setting Availability: In Stock...")

            availability_clicked = False
            availability_elements = page.locator("text=List as in Stock")
            for i in range(availability_elements.count()):
                el = availability_elements.nth(i)
                if el.is_visible():
                    el.scroll_into_view_if_needed()
                    el.click(force=True)
                    availability_clicked = True
                    print("✅ Clicked on Availability dropdown")
                    break

            if availability_clicked:
                page.wait_for_timeout(500)  # Reduced from 2000ms

                # Try to select "In Stock"
                in_stock_set = False

                # Approach 1: Try direct selection
                try:
                    in_stock_option = page.get_by_role(
                        "option", name="In stock")
                    if in_stock_option.is_visible():
                        in_stock_option.click()
                        in_stock_set = True
                        print("✅ Set Availability: In Stock (via role)")
                except Exception:
                    pass

                # Approach 2: Keyboard navigation
                if not in_stock_set:
                    try:
                        page.keyboard.press("Home")
                        page.keyboard.press("ArrowDown")
                        page.keyboard.press("Enter")
                        in_stock_set = True
                        print("✅ Set Availability: In Stock (via keyboard)")
                    except Exception:
                        pass

                if not in_stock_set:
                    print("❌ Could not set availability - trying to continue anyway")
            else:
                print("❌ Could not find Availability dropdown")

            print("📍 Skipping location (using proxy/VPN for region)...")

            # Scroll to bottom to ensure all fields are visible and validated
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(400)  # Reduced from 2000ms

            print("📤 Looking for Next button...")
            next_clicked = False

            # Try multiple approaches to click Next button
            # Approach 1: Text-based selector
            try:
                next_buttons = page.locator("text='Next'").all()
                for btn in next_buttons:
                    if btn.is_visible():
                        btn.scroll_into_view_if_needed()
                        btn.click()
                        next_clicked = True
                        print("✅ Clicked Next button (via text)")
                        break
            except Exception:
                pass

            # Approach 2: Role-based selector
            if not next_clicked:
                try:
                    next_btn = page.get_by_role("button", name="Next")
                    if next_btn.is_visible():
                        next_btn.click()
                        next_clicked = True
                        print("✅ Clicked Next button (via role)")
                except Exception:
                    pass

            # Approach 3: Try finding button with aria-label
            if not next_clicked:
                try:
                    next_btn = page.locator("button[aria-label*='Next']").first
                    if next_btn.is_visible():
                        next_btn.click()
                        next_clicked = True
                        print("✅ Clicked Next button (via aria-label)")
                except Exception:
                    pass

            if not next_clicked:
                print(
                    "⚠️ Could not find Next button - form might be single page, looking for Publish directly")
            else:
                # Wait for page transition after clicking Next
                page.wait_for_timeout(1000)  # Reduced from 3000ms

            # Scroll to bottom again to reveal Publish button
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(400)  # Reduced from 2000ms

            print("🔍 Looking for Publish button...")
            publish_clicked = False

            # Try multiple variations of the Publish button
            publish_variations = [
                "Publish",
                "Publish listing",
                "Post",
                "Post listing",
                "Confirm",
                "Submit"
            ]

            for variation in publish_variations:
                if publish_clicked:
                    break

                # Try text-based selector
                try:
                    publish_buttons = page.locator(f"text='{variation}'").all()
                    for btn in publish_buttons:
                        if btn.is_visible():
                            btn.scroll_into_view_if_needed()
                            page.wait_for_timeout(1000)
                            btn.click()
                            publish_clicked = True
                            print(
                                f"✅ Clicked Publish button (found as '{variation}')")
                            break
                except Exception:
                    pass

                # Try role-based selector
                if not publish_clicked:
                    try:
                        publish_btn = page.get_by_role(
                            "button", name=variation)
                        if publish_btn.is_visible():
                            publish_btn.scroll_into_view_if_needed()
                            page.wait_for_timeout(1000)
                            publish_btn.click()
                            publish_clicked = True
                            print(
                                f"✅ Clicked Publish button (role, found as '{variation}')")
                            break
                    except Exception:
                        pass

            if not publish_clicked:
                print("❌ Could not find Publish button!")
                raise Exception(
                    "Publish button not found after multiple attempts")

            # Wait for posting to complete
            page.wait_for_timeout(1500)  # Reduced from 3000ms
            print("✅ Posted successfully!")

        except Exception as e:
            print("❌ Something went wrong while trying to fill the form.")
            page.screenshot(path="error_screenshot.png")
            print("📷 Screenshot saved as error_screenshot.png")
            raise e

        finally:
            context.close()
            browser.close()


# from playwright.sync_api import sync_playwright
# import time
# import os
# from django.conf import settings


# def debug_page_state(page, step_name):
#     """Helper function to debug page state at any point"""
#     print(f"\n🔍 DEBUG: {step_name}")
#     print(f"   URL: {page.url}")

#     # Check for error messages
#     errors = page.locator("[role='alert'], .error").all()
#     error_count = sum(1 for e in errors if e.is_visible())
#     if error_count > 0:
#         print(f"   ⚠️ Found {error_count} error message(s)")

#     # Check for buttons
#     buttons = page.locator("button").all()
#     visible_buttons = []
#     for btn in buttons:
#         try:
#             if btn.is_visible():
#                 text = btn.inner_text()[:50]  # Limit text length
#                 if text.strip():
#                     visible_buttons.append(text.strip())
#         except Exception:
#             pass

#     if visible_buttons:
#         # Show first 5 unique
#         print(f"   📍 Visible buttons: {', '.join(set(visible_buttons[:5]))}")
#     else:
#         print("   ⚠️ No visible buttons found")
#     print()


# def save_session(email, password=None):
#     """
#     Save Facebook login session
#     Always runs with visible browser (headless=False) so user can solve CAPTCHA
#     """
#     with sync_playwright() as p:
#         print("🖥️  Opening browser for login (visible mode for CAPTCHA solving)")
#         browser = p.chromium.launch(headless=False)  # Always visible for login
#         context = browser.new_context()
#         page = context.new_page()
#         page.goto("https://www.facebook.com/login",
#                   wait_until="domcontentloaded")

#         login_successful = False

#         if password:
#             print(f"🔐 Auto-logging in for: {email}")

#             try:
#                 page.fill('input[name="email"]', email)
#                 page.fill('input[name="pass"]', password)
#                 page.click('button[name="login"]')

#                 print("⏳ Waiting for login response...")
#                 time.sleep(5)

#                 # Check if still on login page or error occurred
#                 current_url = page.url

#                 # Check for various login failure indicators
#                 is_still_login = (
#                     "login" in current_url or
#                     page.locator('input[name="email"]').is_visible() or
#                     page.locator('input[name="pass"]').is_visible()
#                 )

#                 # Check for checkpoint/captcha
#                 is_checkpoint = (
#                     "checkpoint" in current_url or
#                     "captcha" in current_url or
#                     page.locator('text=Security Check').is_visible() or
#                     page.locator('text=Enter the code').is_visible()
#                 )

#                 if is_checkpoint:
#                     print("🔒 Captcha/2FA/Checkpoint detected!")
#                     print("👉 Please solve it manually in the browser...")
#                     print("⏳ Waiting 90 seconds for you to complete...")
#                     time.sleep(90)

#                     # Verify login after manual intervention
#                     current_url = page.url
#                     is_logged_in = (
#                         "facebook.com" in current_url and
#                         "login" not in current_url and
#                         "checkpoint" not in current_url and
#                         not page.locator('input[name="email"]').is_visible()
#                     )

#                     if is_logged_in:
#                         login_successful = True
#                         print("✅ Login successful after solving checkpoint!")
#                     else:
#                         print("❌ Login still not completed - checkpoint not solved")

#                 elif is_still_login:
#                     print("❌ Login failed - wrong password or blocked")

#                 else:
#                     # Appears to be logged in
#                     login_successful = True
#                     print("✅ Auto-login successful!")

#             except Exception as e:
#                 print(f"⚠️ Auto-login failed: {e}")
#                 print("👉 Please log in manually")
#                 time.sleep(60)

#                 # Check if manual login succeeded
#                 try:
#                     current_url = page.url
#                     if "login" not in current_url and not page.locator('input[name="email"]').is_visible():
#                         login_successful = True
#                         print("✅ Manual login successful!")
#                 except Exception:
#                     pass
#         else:
#             print(f"👉 Please log in manually for: {email}")
#             print("⏳ You have 60 seconds...")
#             time.sleep(60)

#             # Check if manual login succeeded
#             try:
#                 current_url = page.url
#                 if "login" not in current_url and not page.locator('input[name="email"]').is_visible():
#                     login_successful = True
#                     print("✅ Manual login successful!")
#             except Exception:
#                 pass

#         if login_successful:
#             session_path = f"sessions/{email.replace('@', '_').replace('.', '_')}.json"
#             context.storage_state(path=session_path)
#             print(f"✅ Session saved: {session_path}")
#         else:
#             print(f"❌ Session NOT saved - Login failed for {email}")

#         browser.close()
#         return login_successful


# def manual_login_and_save_session(email):
#     """
#     Open browser and let user manually login to Facebook
#     User types email, password, solves CAPTCHA, etc.
#     Once logged in, session is saved automatically

#     Args:
#         email: Facebook account email (used for session filename)

#     Returns:
#         bool: True if session saved successfully, False otherwise
#     """
#     with sync_playwright() as p:
#         print(f"\n🌐 Opening browser for MANUAL login...")
#         print(f"📧 Account: {email}")
#         print("=" * 60)
#         print("📝 INSTRUCTIONS:")
#         print("   1. Browser will open to Facebook login page")
#         print("   2. Manually type your email and password")
#         print("   3. Solve any CAPTCHA or security checks")
#         print("   4. Complete 2FA if required")
#         print("   5. Wait until you see Facebook homepage")
#         print("   6. Browser will close automatically and save session")
#         print("=" * 60)
#         print("⏳ You have 120 seconds to complete login...")
#         print()

#         # Slower for better observation
#         browser = p.chromium.launch(headless=False, slow_mo=100)

#         # Add realistic browser settings
#         context = browser.new_context(
#             user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
#             viewport={'width': 1366, 'height': 768},
#             locale='en-US',
#             timezone_id='America/New_York'
#         )

#         page = context.new_page()

#         # Go to Facebook login
#         print("🌐 Loading Facebook login page...")
#         page.goto("https://www.facebook.com/login",
#                   wait_until="domcontentloaded", timeout=30000)

#         login_successful = False
#         check_interval = 5  # Check every 5 seconds
#         max_wait_time = 120  # 2 minutes total
#         elapsed_time = 20

#         print("👀 Waiting for you to login manually...")
#         print("💡 Tip: Take your time, the bot is watching and waiting!")
#         print()

#         # Monitor login progress
#         while elapsed_time < max_wait_time:
#             time.sleep(check_interval)
#             elapsed_time += check_interval

#             try:
#                 # Check if browser/page is still open
#                 if page.is_closed():
#                     print("\n🔒 Browser closed by user")
#                     print("❌ Login cancelled")
#                     break

#                 current_url = page.url

#                 # Check if successfully logged in (not on login page anymore)
#                 is_logged_in = (
#                     "facebook.com" in current_url and
#                     "login" not in current_url and
#                     "checkpoint" not in current_url and
#                     "captcha" not in current_url
#                 )

#                 # Also check if login form is gone
#                 login_form_gone = False
#                 try:
#                     login_form_gone = not page.locator(
#                         'input[name="email"]').is_visible(timeout=1000)
#                 except:
#                     login_form_gone = True  # Form not found = probably logged in

#                 if is_logged_in and login_form_gone:
#                     login_successful = True
#                     print("✅ Login detected! You're now logged into Facebook!")
#                     print("💾 Saving session...")
#                     break
#                 else:
#                     # Show progress
#                     remaining = max_wait_time - elapsed_time
#                     print(f"⏳ Still waiting... ({remaining}s remaining)")

#                     # Give hints based on URL
#                     if "checkpoint" in current_url:
#                         print(
#                             "   📍 Checkpoint detected - please complete verification")
#                     elif "captcha" in current_url:
#                         print("   🔒 CAPTCHA detected - please solve it")
#                     elif "login" in current_url:
#                         print("   📝 Still on login page - please enter credentials")

#             except Exception as e:
#                 # If we get an error, browser might be closed
#                 error_str = str(e).lower()
#                 if "closed" in error_str or "target" in error_str:
#                     print("\n🔒 Browser closed by user")
#                     print("❌ Login cancelled")
#                     break
#                 print(f"   ⚠️ Checking login status... ({str(e)[:50]})")
#                 continue

#         # Final check
#         if not login_successful:
#             print("\n⏰ Time's up! Doing final check...")
#             time.sleep(2)
#             try:
#                 current_url = page.url
#                 if "facebook.com" in current_url and "login" not in current_url:
#                     login_successful = True
#                     print("✅ Login successful!")
#             except:
#                 pass

#         # Save session if successful
#         if login_successful:
#             try:
#                 session_path = f"sessions/{email.replace('@', '_').replace('.', '_')}.json"
#                 os.makedirs("sessions", exist_ok=True)
#                 context.storage_state(path=session_path)
#                 print(f"✅ Session saved successfully: {session_path}")
#                 print("🎉 You can now use this account for automated posting!")
#             except Exception as e:
#                 print(f"❌ Failed to save session: {e}")
#                 login_successful = False
#         else:
#             print("❌ Login failed or timed out")
#             print("💡 Tip: Try again and complete login faster")

#         print("\n🔒 Closing browser...")
#         browser.close()

#         return login_successful


# def auto_login_and_save_session(email, password):
#     """Automatically login to Facebook and save session"""
#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=False)
#         context = browser.new_context()
#         page = context.new_page()

#         print(f"🌐 Opening Facebook login page...")
#         page.goto("https://www.facebook.com/login", timeout=60000)
#         page.wait_for_timeout(3000)

#         print(f"📧 Entering email: {email}")
#         email_input = page.locator("input[name='email']")
#         email_input.fill(email)

#         print(f"🔒 Entering password...")
#         password_input = page.locator("input[name='pass']")
#         password_input.fill(password)

#         print(f"🔐 Clicking login button...")
#         login_button = page.locator("button[name='login']")
#         login_button.click()

#         # Wait for login to complete
#         print(f"⏳ Waiting for login to complete...")
#         page.wait_for_timeout(10000)

#         # Check if login was successful
#         if "login" in page.url.lower():
#             print(f"❌ Login may have failed - still on login page")
#             browser.close()
#             return False

#         session_path = f"sessions/{email.replace('@', '_').replace('.', '_')}.json"
#         context.storage_state(path=session_path)
#         print(f"✅ Session saved: {session_path}")

#         browser.close()
#         return True


# # def login_and_post(email, title, description, price, image_path, location):
# def login_and_post(email, title, description, price, image_path, headless=True):
#     """
#     Post to Facebook Marketplace

#     Args:
#         email: Facebook account email
#         title: Post title
#         description: Post description
#         price: Item price
#         image_path: Path to product image
#         headless: Run in headless mode (default: True for background posting)
#     """
#     session_file = f"sessions/{email.replace('@', '_').replace('.', '_')}.json"
#     if not os.path.exists(session_file):
#         raise Exception(
#             f"❌ Session not found. Run save_session('{email}') first.")

#     with sync_playwright() as p:
#         # Run in headless mode by default for automated posting
#         # Use settings value if headless parameter not explicitly provided
#         use_headless = headless if headless is not None else getattr(
#             settings, 'AUTOMATION_HEADLESS_MODE', True)

#         if use_headless:
#             print("🤖 Running in HEADLESS mode (background posting)")
#         else:
#             print("🖥️  Running in VISIBLE mode (browser window will open)")

#         browser = p.chromium.launch(headless=use_headless)
#         context = browser.new_context(storage_state=session_file)
#         page = context.new_page()

#         print("🌐 Opening Marketplace listing page...")
#         page.goto("https://www.facebook.com/marketplace/create/item",
#                   timeout=60000)

#         try:
#             print("📸 Uploading image first...")
#             image_input = page.locator("input[type='file'][accept*='image']")
#             image_input.set_input_files(image_path)
#             page.wait_for_timeout(2000)  # Wait for UI to update after upload

#             print("📝 Filling Title...")
#             # Find all visible text inputs that are empty and not in the header
#             text_inputs = page.locator("input[type='text']")
#             title_input = None

#             for i in range(text_inputs.count()):
#                 el = text_inputs.nth(i)
#                 # Check if visible and empty
#                 if el.is_visible() and el.input_value() == "":
#                     # Optionally, skip if it's in the header (search bar)
#                     # You can check its position on the page
#                     box = el.bounding_box()
#                     if box and box['y'] > 100:  # Skip inputs at the very top
#                         title_input = el
#                         break

#             if not title_input:
#                 all_inputs = page.locator("input")
#                 print(
#                     f"Found {all_inputs.count()} input fields. Printing their outerHTML:")
#                 for i in range(all_inputs.count()):
#                     print(all_inputs.nth(i).evaluate("el => el.outerHTML"))
#                 raise Exception("Could not find title input field")

#             title_input.fill(title)

#             print("💰 Filling Price...")

#             # Find all text inputs again
#             text_inputs = page.locator("input[type='text']")
#             price_input = None
#             title_filled = False

#             for i in range(text_inputs.count()):
#                 el = text_inputs.nth(i)
#                 if el.is_visible():
#                     # If this is the title input, mark as found
#                     if not title_filled and el.input_value() == title:
#                         title_filled = True
#                         continue
#                     # The next visible, empty input after title is likely the price
#                     if title_filled and el.input_value() == "":
#                         price_input = el
#                         break

#             if not price_input:
#                 print(
#                     "Could not find price input. Printing all text input values for debug:")
#                 for i in range(text_inputs.count()):
#                     el = text_inputs.nth(i)
#                     print(
#                         f"Input {i}: value='{el.input_value()}', visible={el.is_visible()}")
#                 raise Exception("Could not find price input field")

#             price_input.fill(str(price))
#             # page.locator("text=Category").first.wait_for(
#             # state="visible", timeout=10000)

#             print("📂 Selecting Category...")
#             category_clicked = False
#             category_elements = page.locator("text=Category")
#             for i in range(category_elements.count()):
#                 el = category_elements.nth(i)
#                 if el.is_visible():
#                     el.scroll_into_view_if_needed()
#                     el.click(force=True)
#                     category_clicked = True
#                     print("✅ Clicked on Category dropdown")
#                     break

#             if not category_clicked:
#                 print("❌ Could not find Category dropdown")
#             else:
#                 # Wait for dropdown to fully open
#                 page.wait_for_timeout(2000)

#                 # Try to select "Furniture"
#                 furniture_selected = False

#                 # Approach 1: Try role-based selection
#                 try:
#                     furniture_option = page.get_by_role(
#                         "option", name="Furniture")
#                     if furniture_option.is_visible():
#                         furniture_option.click()
#                         furniture_selected = True
#                         print("✅ Selected Category: Furniture (via role)")
#                 except Exception:
#                     pass

#                 # Approach 2: Try text locator
#                 if not furniture_selected:
#                     try:
#                         furniture_options = page.locator(
#                             "text='Furniture'").all()
#                         for option in furniture_options:
#                             if option.is_visible():
#                                 option.scroll_into_view_if_needed()
#                                 option.click(force=True)
#                                 furniture_selected = True
#                                 print("✅ Selected Category: Furniture (via text)")
#                                 break
#                     except Exception:
#                         pass

#                 if not furniture_selected:
#                     print(
#                         "❌ Could not select Furniture category - trying to continue anyway")

#             print("🔧 Selecting Condition...")
#             condition_elements = page.locator("text=Condition")
#             condition_clicked = False
#             for i in range(condition_elements.count()):
#                 el = condition_elements.nth(i)
#                 if el.is_visible():
#                     el.scroll_into_view_if_needed()
#                     el.click(force=True)
#                     condition_clicked = True
#                     print("✅ Clicked on Condition dropdown")
#                     break

#             if not condition_clicked:
#                 print("❌ Could not find Condition dropdown")
#             else:
#                 # Wait for dropdown to fully open
#                 page.wait_for_timeout(2000)

#                 # Try multiple approaches to find and click "New" condition
#                 new_clicked = False

#                 # Approach 1: Try exact text match with role
#                 try:
#                     new_option = page.get_by_role("option", name="New")
#                     if new_option.is_visible():
#                         new_option.click()
#                         new_clicked = True
#                         print("✅ Selected Condition: New (via role)")
#                 except Exception:
#                     pass

#                 # Approach 2: Try text locator with exact match
#                 if not new_clicked:
#                     try:
#                         # Find all elements containing "New" and filter
#                         new_options = page.locator("text='New'").all()
#                         for option in new_options:
#                             if option.is_visible():
#                                 option.scroll_into_view_if_needed()
#                                 option.click(force=True)
#                                 new_clicked = True
#                                 print("✅ Selected Condition: New (via text)")
#                                 break
#                     except Exception:
#                         pass

#                 # Approach 3: Use keyboard navigation
#                 if not new_clicked:
#                     try:
#                         page.keyboard.press("Home")  # Go to top
#                         page.keyboard.press("ArrowDown")  # Navigate to "New"
#                         page.keyboard.press("Enter")
#                         new_clicked = True
#                         print("✅ Selected Condition: New (via keyboard)")
#                     except Exception:
#                         pass

#                 if not new_clicked:
#                     print(
#                         "❌ Could not select New condition - trying to continue anyway")

#             print("🧾 Filling Description...")
#             try:
#                 # Try by accessible name
#                 description_area = page.get_by_role(
#                     "textbox", name="Description")
#                 description_area.fill(description)
#             except Exception:
#                 # Fallback: use the first visible textarea
#                 textareas = page.locator("textarea")
#                 for i in range(textareas.count()):
#                     el = textareas.nth(i)
#                     if el.is_visible():
#                         el.fill(description)
#                         break

#             print("📦 Setting Availability: In Stock...")

#             availability_clicked = False
#             availability_elements = page.locator("text=List as in Stock")
#             for i in range(availability_elements.count()):
#                 el = availability_elements.nth(i)
#                 if el.is_visible():
#                     el.scroll_into_view_if_needed()
#                     el.click(force=True)
#                     availability_clicked = True
#                     print("✅ Clicked on Availability dropdown")
#                     break

#             if availability_clicked:
#                 page.wait_for_timeout(2000)

#                 # Try to select "In Stock"
#                 in_stock_set = False

#                 # Approach 1: Try direct selection
#                 try:
#                     in_stock_option = page.get_by_role(
#                         "option", name="In stock")
#                     if in_stock_option.is_visible():
#                         in_stock_option.click()
#                         in_stock_set = True
#                         print("✅ Set Availability: In Stock (via role)")
#                 except Exception:
#                     pass

#                 # Approach 2: Keyboard navigation
#                 if not in_stock_set:
#                     try:
#                         page.keyboard.press("Home")
#                         page.keyboard.press("ArrowDown")
#                         page.keyboard.press("Enter")
#                         in_stock_set = True
#                         print("✅ Set Availability: In Stock (via keyboard)")
#                     except Exception:
#                         pass

#                 if not in_stock_set:
#                     print("❌ Could not set availability - trying to continue anyway")
#             else:
#                 print("❌ Could not find Availability dropdown")

#             print("📍 Skipping location (using proxy/VPN for region)...")

#             # Debug: Check page state after filling all fields
#             debug_page_state(page, "After filling all fields")

#             # Check for any validation errors before proceeding
#             print("🔍 Checking for validation errors...")
#             page.wait_for_timeout(1000)

#             # Look for error messages or required field indicators
#             error_indicators = page.locator(
#                 "[role='alert'], .error, [aria-invalid='true']").all()
#             if error_indicators:
#                 print("⚠️ Warning: Found potential validation errors on the page")
#                 for i, indicator in enumerate(error_indicators):
#                     try:
#                         if indicator.is_visible():
#                             text = indicator.inner_text()
#                             print(f"  Error {i+1}: {text}")
#                     except Exception:
#                         pass

#             # Scroll to bottom to ensure all fields are visible and validated
#             print("📜 Scrolling to bottom of form...")
#             page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
#             page.wait_for_timeout(2000)

#             print("📤 Looking for Next button...")
#             next_clicked = False

#             # Try multiple approaches to click Next button
#             # Approach 1: Text-based selector
#             try:
#                 next_buttons = page.locator("text='Next'").all()
#                 for btn in next_buttons:
#                     if btn.is_visible():
#                         btn.scroll_into_view_if_needed()
#                         btn.click()
#                         next_clicked = True
#                         print("✅ Clicked Next button (via text)")
#                         break
#             except Exception:
#                 pass

#             # Approach 2: Role-based selector
#             if not next_clicked:
#                 try:
#                     next_btn = page.get_by_role("button", name="Next")
#                     if next_btn.is_visible():
#                         next_btn.click()
#                         next_clicked = True
#                         print("✅ Clicked Next button (via role)")
#                 except Exception:
#                     pass

#             # Approach 3: Try finding button with aria-label
#             if not next_clicked:
#                 try:
#                     next_btn = page.locator("button[aria-label*='Next']").first
#                     if next_btn.is_visible():
#                         next_btn.click()
#                         next_clicked = True
#                         print("✅ Clicked Next button (via aria-label)")
#                 except Exception:
#                     pass

#             if not next_clicked:
#                 print(
#                     "⚠️ Could not find Next button - form might be single page, looking for Publish directly")
#             else:
#                 # Wait for page transition after clicking Next
#                 page.wait_for_timeout(3000)
#                 print("⏳ Waiting for Publish button to appear...")

#             # Debug: Check page state after Next button
#             debug_page_state(page, "After Next button (or if no Next button)")

#             # Scroll to bottom again to reveal Publish button
#             page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
#             page.wait_for_timeout(2000)

#             print("🔍 Looking for Publish button...")
#             publish_clicked = False

#             # Try multiple variations of the Publish button
#             publish_variations = [
#                 "Publish",
#                 "Publish listing",
#                 "Post",
#                 "Post listing",
#                 "Confirm",
#                 "Submit"
#             ]

#             for variation in publish_variations:
#                 if publish_clicked:
#                     break

#                 # Try text-based selector
#                 try:
#                     publish_buttons = page.locator(f"text='{variation}'").all()
#                     for btn in publish_buttons:
#                         if btn.is_visible():
#                             btn.scroll_into_view_if_needed()
#                             page.wait_for_timeout(1000)
#                             btn.click()
#                             publish_clicked = True
#                             print(
#                                 f"✅ Clicked Publish button (found as '{variation}')")
#                             break
#                 except Exception:
#                     pass

#                 # Try role-based selector
#                 if not publish_clicked:
#                     try:
#                         publish_btn = page.get_by_role(
#                             "button", name=variation)
#                         if publish_btn.is_visible():
#                             publish_btn.scroll_into_view_if_needed()
#                             page.wait_for_timeout(1000)
#                             publish_btn.click()
#                             publish_clicked = True
#                             print(
#                                 f"✅ Clicked Publish button (role, found as '{variation}')")
#                             break
#                     except Exception:
#                         pass

#             if not publish_clicked:
#                 # Last resort: Take a screenshot and print all buttons for debugging
#                 print("❌ Could not find Publish button!")
#                 page.screenshot(path="publish_button_missing.png")
#                 print("📷 Screenshot saved as publish_button_missing.png")

#                 # Print all visible buttons for debugging
#                 print("\n🔍 DEBUG: All visible buttons on page:")
#                 buttons = page.locator("button").all()
#                 for i, btn in enumerate(buttons):
#                     try:
#                         if btn.is_visible():
#                             text = btn.inner_text()
#                             aria_label = btn.get_attribute("aria-label")
#                             print(
#                                 f"  Button {i}: text='{text}', aria-label='{aria_label}'")
#                     except Exception:
#                         pass

#                 raise Exception(
#                     "Publish button not found after multiple attempts")

#             # Wait for posting to complete
#             page.wait_for_timeout(3000)
#             print("✅ Posted successfully!")

#         except Exception as e:
#             print("❌ Something went wrong while trying to fill the form.")
#             page.screenshot(path="error_screenshot.png")
#             print("📷 Screenshot saved as error_screenshot.png")
#             raise e

#         finally:
#             context.close()
#             browser.close()
