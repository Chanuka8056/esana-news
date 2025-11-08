from playwright.sync_api import sync_playwright
import time
import hashlib
import requests
import io
import re
import os

# Telegram Bot credentials
TELEGRAM_TOKEN = "Your_Telegram_API"
CHAT_ID = "Your_Telegram ID"

# Helakuru Esana link eka
URL = "https://www.helakuru.lk/esana"

# Keep track of sent news to avoid duplicates- ekiyanne news wla ekak ekaparai aye yawapu redda yawanne na
sent_hashes = set()

def send_to_telegram(message, image_url=None):
    """Send text + image to Telegram."""
    try:
        # Truncate message if too long for Telegram caption
        if len(message) > 900:
            message = message[:900] + "..."
            
        if image_url and image_url.startswith("http"):
            print(f"🖼️ Sending image: {image_url}")
            
            try:
                # Download the image first - me ara photo pojja down karana redda
                image_response = requests.get(image_url, timeout=10)
                if image_response.status_code == 200:
                    # Send photo with file upload -caption with
                    response = requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                        data={
                            "chat_id": CHAT_ID,
                            "caption": message,
                            "parse_mode": "HTML"
                        },
                        files={
                            "photo": ("image.jpg", image_response.content, "image/jpeg")
                        }
                    )
                else:
                    print("❌ Failed to download image, sending text only")
                    response = requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                        json={
                            "chat_id": CHAT_ID,
                            "text": message,
                            "parse_mode": "HTML"
                        }
                    )
            except Exception as img_error:
                print(f"❌ Image download error: {img_error}, sending text only")
                response = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={
                        "chat_id": CHAT_ID,
                        "text": message,
                        "parse_mode": "HTML"
                    }
                )
        else:
            # Send text only - meka me photo redda hoyaganan bari unama 
            print("📤 Sending text only message")
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": CHAT_ID,
                    "text": message,
                    "parse_mode": "HTML"
                }
            )
        
        print(f"📤 Telegram response: {response.status_code}")
        if response.status_code == 200:
            print("✅ Message sent successfully!")
            return True
        else:
            print(f"❌ Failed to send: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Telegram send exception: {e}")
        return False

def load_sent_hashes():
    """Load previously sent news hashes from file."""
    try:
        if os.path.exists("sent_hashes.txt"):
            with open("sent_hashes.txt", "r", encoding="utf-8") as f:
                hashes = set(line.strip() for line in f if line.strip())
            print(f"📚 Loaded {len(hashes)} previously sent news items")
            return hashes
        else:
            print("📚 No previous sent news found, starting fresh")
            return set()
    except Exception as e:
        print(f"❌ Error loading sent hashes: {e}")
        return set()

def save_sent_hash(news_hash):
    """Save a new sent hash to file."""
    try:
        with open("sent_hashes.txt", "a", encoding="utf-8") as f:
            f.write(f"{news_hash}\n")
    except Exception as e:
        print(f"❌ Error saving sent hash: {e}")

def get_news_content(page):
    ''' me html redde full x path pojjawal '''
    """Extract news content from the page."""
    try:
        # Wait for the main content to load
        page.wait_for_selector("xpath=/html/body/div[3]/div/div/div/div[2]/div/div/div[2]/div/div[1]/div[3]/div/div[1]", timeout=10000)
        
        # Get title content
        title_elem = page.query_selector(
            "xpath=/html/body/div[3]/div/div/div/div[2]/div/div/div[2]/div/div[1]/div[3]/div/div[1]/div[1]/div[2]/h2"
        )
        
        # Get main text content
        text_elem = page.query_selector(
            "xpath=/html/body/div[3]/div/div/div/div[2]/div/div/div[2]/div/div[1]/div[3]/div/div[1]/div[2]"
        )
        
        # Get image content
        img_elem = page.query_selector(
            "xpath=/html/body/div[3]/div/div/div/div[2]/div/div/div[2]/div/div[1]/div[3]/div/div[1]/div[1]/div[1]/div/div/img"
        )
        
        if not text_elem:
            print("⚠️ Text element not found")
            return None, None
        
        # Get the main text content
        main_text = text_elem.inner_text().strip()
        
        # Remove any "Read more" text from the content but keep the main content
        cleaned_text = re.sub(r'Read more.*|වැඩිදුර කියවන්න.*|▶.*|🔗.*', '', main_text, flags=re.IGNORECASE)
        cleaned_text = cleaned_text.strip()
        
        if not cleaned_text or len(cleaned_text) < 10:
            print("⚠️ No meaningful text content found")
            return None, None
        
        # Title eka extrak kirima
        title = ""
        if title_elem:
            title = title_elem.inner_text().strip()
            print(f"📌 Title found: {title}")
        
        # Get the current page URL as the main link
        current_url = page.url
        
        # Create the final message with "Read More" button
        if title:
            formatted_message = f"<b>{title}</b>\n\n{cleaned_text}\n\n<a href='{current_url}'>📖 Read More</a>"
        else:
            formatted_message = f"{cleaned_text}\n\n<a href='{current_url}'>📖 Read More</a>"
            
        image_url = None
        if img_elem:
            image_url = img_elem.get_attribute("src")
            if image_url and image_url.startswith("//"):
                image_url = "https:" + image_url
            elif image_url and image_url.startswith("/"):
                image_url = "https://www.helakuru.lk" + image_url
        
        print(f"📝 Extracted text length: {len(cleaned_text)}")
        print(f"🔗 Using main page URL: {current_url}")
        
        return formatted_message, image_url, cleaned_text
        
    except Exception as e:
        print(f"❌ Error extracting news content: {e}")
        return None, None, None

def main():
    print("📢 Helakuru Esana → Telegram Forwarder Started")
    print(f"🔧 Target URL: {URL}")
    print(f"🤖 Telegram Chat ID: {CHAT_ID}")

    # Load previously sent hashes
    sent_hashes.update(load_sent_hashes())

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            ]
        )
        
        # Create context with viewport
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        
        page = context.new_page()
        page.set_default_timeout(30000)

        # Counter for monitoring
        check_count = 0
        
        while True:
            try:
                check_count += 1
                print(f"\n🔍 Check #{check_count} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                print("🔄 Navigating to page...")
                page.goto(URL, wait_until="networkidle")
                time.sleep(5)
                
                # Take screenshot for debugging first time
                if check_count == 1:
                    page.screenshot(path="first_load.png")
                    print("📸 Initial screenshot saved as first_load.png")
                
                print("📖 Extracting news content...")
                formatted_message, image_url, cleaned_text = get_news_content(page)
                
                if not formatted_message:
                    print("❌ No news content found")
                    time.sleep(60)
                    continue
                
                print(f"📝 Formatted message preview: {formatted_message[:150]}...")
                print(f"🖼️ Image URL: {image_url}")
                
                # Create hash for duplicate detection (using only the cleaned text without formatting)
                news_hash = hashlib.md5(cleaned_text.encode()).hexdigest()
                print(f"🔑 News hash: {news_hash}")
                
                if news_hash not in sent_hashes:
                    print("🆕 New news detected! Sending to Telegram...")
                    
                    success = send_to_telegram(formatted_message, image_url)
                    
                    if success:
                        sent_hashes.add(news_hash)
                        save_sent_hash(news_hash)
                        print("✅ Successfully sent and stored news hash")
                    else:
                        print("❌ Failed to send news, will retry next time")
                else:
                    print("⚠️ Duplicate news - already sent")
                    
                print(f"📊 Total unique news sent: {len(sent_hashes)}")

            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                try:
                    page.screenshot(path=f"error_{int(time.time())}.png")
                    print("📸 Error screenshot saved")
                except:
                    pass

            print("⏳ Waiting 60 seconds for next check...")
            time.sleep(60)

if __name__ == "__main__":
    main()

# iwarai iwarai aye balanna deyak nakamathi widiyata hadaganilla