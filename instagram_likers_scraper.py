from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException,
    ElementClickInterceptedException
)
import time

def main():
    ig_username = input("Enter your Instagram username: ")
    ig_password = input("Enter your Instagram password: ")
    post_url = input("Enter the Instagram post URL: ")

    print("Initializing WebDriver...")
    driver = webdriver.Chrome()

    try:
        # 1. Log in to Instagram
        login_to_instagram(driver, ig_username, ig_password)

        # 2. Navigate to the Instagram post
        print("Navigating to the Instagram post...")
        driver.get(post_url)
        time.sleep(5)

        # 3. Dismiss possible cookie banner and post-login popups
        dismiss_overlays(driver)
        dismiss_post_login_popups(driver)

        # 4. Debug: JavaScript injection to fetch like-related elements
        fetch_like_elements_js(driver)

        # 5. Finally, attempt to open the likers dialog and scrape
        scrape_likers(driver)

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        driver.quit()

def login_to_instagram(driver, username, password):
    """
    Logs in to Instagram with the provided credentials.
    """
    print("Opening Instagram login page...")
    driver.get("https://www.instagram.com/")
    
    # Wait for login fields to appear
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.NAME, "username"))
    )

    print("Filling in username and password...")
    username_input = driver.find_element(By.NAME, "username")
    password_input = driver.find_element(By.NAME, "password")
    username_input.send_keys(username)
    password_input.send_keys(password)
    password_input.send_keys(Keys.RETURN)

    # Wait for the main page or user feed to load after login
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, '//nav'))
        )
        print("Login successful.")
    except TimeoutException:
        print("Login might have failed or took too long.")

def dismiss_overlays(driver):
    """
    Dismisses potential overlays or cookie banners (e.g. 'Accept All').
    """
    print("Checking for overlays (cookie banners, etc.)...")
    try:
        accept_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//button[text()="Accept All"]'))
        )
        accept_button.click()
        print("Cookie banner dismissed.")
    except TimeoutException:
        print("No cookie banner or timed out waiting for overlay.")
    except Exception as e:
        print(f"Overlay dismissal error: {e}")

def dismiss_post_login_popups(driver):
    """
    After login, Instagram may show various pop-ups like:
    - “Save Your Login Info?” -> [Not Now] or [Save Info]
    - “Turn on Notifications?” -> [Not Now] or [Allow]
    - “Stay Logged In?” -> [Not Now] or [Cancel]
    This function attempts to dismiss them by clicking recognized buttons.
    """
    # Common button texts on these popups
    popup_button_texts = ["Not Now", "Cancel", "No Thanks", "Turn Off", "Later", "Close"]
    # More can be added if Instagram changes text.

    print("Checking for post-login popups...")
    for text_option in popup_button_texts:
        try:
            # Searching for a button with the exact text
            popup_button = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, f'//button[text()="{text_option}"]'))
            )
            popup_button.click()
            print(f"Clicked the '{text_option}' button to dismiss a popup.")
            time.sleep(2)
        except TimeoutException:
            # If we don't see it within 3 seconds, move on
            pass
        except ElementClickInterceptedException:
            # Another overlay might be blocking it; scroll or try another approach
            driver.execute_script("arguments[0].scrollIntoView(true);", popup_button)
            time.sleep(1)
            popup_button.click()
            time.sleep(2)
        except Exception:
            pass

def fetch_like_elements_js(driver):
    """
    Injects and executes JavaScript to find elements containing 'likes'.
    This can help confirm that the DOM has loaded or that likes text is present.
    """
    print("Injecting JavaScript to find like-related elements...")
    js_script = """
    const likeElements = Array.from(document.querySelectorAll('*')).filter(el => {
        if (!el.textContent) return false;
        return el.textContent.includes('like') && el.textContent.match(/\\d+/);
    });
    return likeElements.map(el => el.textContent).join('; ');
    """
    try:
        like_elements = driver.execute_script(js_script)
        if like_elements:
            print(f"Found these like-related elements: {like_elements}")
        else:
            print("No elements containing 'like' and numbers found. Post may have 0 likes or different text.")
    except Exception as e:
        print(f"JavaScript injection failed: {e}")

def scrape_likers(driver):
    """
    Locates and clicks the likers link, scrolls through, and saves usernames to likers.txt.
    """
    print("Attempting to open the list of users who liked the post...")

    # Try standard XPATH for link to 'liked_by'
    # But watch out for popups or intercepting overlays
    try:
        likers_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//a[contains(@href, "/liked_by/")]'))
        )
        # Possibly wait for overlays to vanish:
        wait_for_overlays_to_disappear(driver)
        # Now click
        likers_link.click()
        print("Likers dialog opened.")
    except (TimeoutException, ElementClickInterceptedException) as e:
        print(f"Could not click the standard 'liked_by' link (Timeout or Interception). Error: {e}")
        # Attempt an alternative approach or XPATH if needed
        # (Instagram sometimes changes its UI to a button or a different anchor)
        # If we fail here, we'll exit
        return

    # Wait for the likers dialog
    print("Waiting for the likers dialog...")
    try:
        scroll_box = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, '//div[@role="dialog"]//div[contains(@class, "_aano")]'))
        )
        print("Dialog loaded. Scrolling to load all likers...")
    except TimeoutException:
        print("Timed out waiting for likers dialog to appear.")
        return

    usernames = set()  # Collect unique usernames
    start_time = time.time()
    timeout = 90
    last_height = -1

    while True:
        try:
            current_height = driver.execute_script("return arguments[0].scrollTop", scroll_box)
            scroll_height = driver.execute_script("return arguments[0].scrollHeight", scroll_box)
            # Scroll down a bit
            driver.execute_script("arguments[0].scrollTop += 600", scroll_box)
            time.sleep(2)  # Let new users load

            # Gather any new usernames in view
            new_usernames = get_likers_in_view(scroll_box)
            usernames.update(new_usernames)
            print(f"Loaded {len(usernames)} usernames so far...")

            # Break if no change in scroll or we exceed time limit
            if current_height == scroll_height or (time.time() - start_time) > timeout:
                break
            if current_height == last_height:
                print("No new content. Possibly at the bottom of the list.")
                break

            last_height = current_height
        except StaleElementReferenceException:
            # If the scroll box disappears or re-renders, re-acquire it
            print("Encountered StaleElementReference. Trying to re-locate dialog.")
            try:
                scroll_box = driver.find_element(By.XPATH, '//div[@role="dialog"]//div[contains(@class, "_aano")]')
            except NoSuchElementException:
                print("Dialog no longer present.")
                break

    # Save the usernames to a file
    if usernames:
        print("Saving usernames to 'likers.txt'...")
        with open("likers.txt", "w", encoding="utf-8") as file:
            for username in usernames:
                file.write(username + "\n")
        print(f"Usernames saved successfully! Total: {len(usernames)}")
    else:
        print("No likers found or no usernames extracted.")

def get_likers_in_view(scroll_box):
    """
    Returns a list of usernames currently in the scrollable dialog.
    """
    anchors = scroll_box.find_elements(By.TAG_NAME, 'a')
    # Typically Instagram usernames are in <a> tags; filter out empty text
    return [a.text.strip() for a in anchors if a.text.strip()]

def wait_for_overlays_to_disappear(driver):
    """
    Optional helper to wait for any full-screen overlay to go away
    before clicking (avoids ElementClickInterceptedException).
    If Instagram is blocking clicks with a modal, adjust accordingly.
    """
    # Example: Wait for an overlay with certain classes to become invisible
    # This may or may not match your scenario exactly.
    try:
        WebDriverWait(driver, 5).until(
            EC.invisibility_of_element((By.XPATH, '//div[@role="dialog" and contains(@class, "overlay-class")]'))
        )
        print("Overlay is gone; safe to click.")
    except TimeoutException:
        pass
    except Exception as e:
        print(f"Could not verify overlay disappearance: {e}")

if __name__ == "__main__":
    main()
