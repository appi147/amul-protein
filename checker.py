import json
import logging
import os
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

PINCODE = os.environ.get("PINCODE", "500084").strip() or "500084"
PRODUCTS = [
    {
        "name": "Amul Chocolate Whey Protein — 60 sachets",
        "url": "https://shop.amul.com/en/product/amul-chocolate-whey-protein-34-g-or-pack-of-60-sachets",
    },
    {
        "name": "Amul Chocolate Whey Protein — 30 sachets",
        "url": "https://shop.amul.com/en/product/amul-chocolate-whey-protein-34-g-or-pack-of-30-sachets",
    },
]

STATE_FILE = Path("state.json")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


def clean_price(text):
    m = re.search(r"(?:₹|INR)\s*[\d,]+(?:\.\d+)?", text)
    return m.group(0) if m else "Price unavailable"


def telegram_notify(message):
    import urllib.request
    import urllib.parse

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    logger.info("Sending Telegram availability notification")

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": "false",
    }).encode()

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"Telegram returned HTTP {response.status}")


def set_pincode(page):
    # Amul currently exposes a delivery-pincode control with this placeholder.
    # We intentionally avoid relying on a CSS class because StoreHippo themes can change.
    candidates = [
        page.get_by_placeholder("Enter Your Pincode"),
        page.locator('input[placeholder*="Pincode" i]'),
        page.locator('input[placeholder*="pincode" i]'),
    ]

    field = None
    for candidate in candidates:
        try:
            if candidate.first.is_visible(timeout=2500):
                field = candidate.first
                break
        except Exception:
            pass

    if field is None:
        raise RuntimeError("Could not find the Amul pincode input")

    logger.info("Entering delivery PIN %s", PINCODE)
    field.fill(PINCODE)
    # Amul shows matching PIN codes in a dropdown shortly after typing. Select
    # the exact PIN instead of relying on Enter, which does not always commit it.
    page.wait_for_timeout(2000)

    pincode_option = page.get_by_text(PINCODE, exact=True)
    try:
        pincode_option.first.wait_for(state="visible", timeout=5000)
        pincode_option.first.click()
        logger.info("Selected PIN %s from the delivery dropdown", PINCODE)
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(f"Could not find PIN {PINCODE} in the dropdown") from exc

    # Selecting the dropdown entry triggers the delivery/serviceability update.
    # Wait for the updated product control rather than judging the previous state.
    try:
        page.locator("a.add-to-cart").first.wait_for(state="visible", timeout=10000)
    except PlaywrightTimeoutError:
        logger.warning("Add to Cart control did not appear within 10 seconds after PIN selection")
    page.wait_for_timeout(2000)


def detect_orderability(page):
    # The product page uses an anchor, not necessarily a button. Its `disabled`
    # attribute is the stock signal: disabled="true" means unavailable.
    add_to_cart = page.locator("a.add-to-cart").first
    try:
        add_to_cart.wait_for(state="visible", timeout=10000)
    except PlaywrightTimeoutError:
        return False, "No visible Add to Cart control"

    disabled = add_to_cart.get_attribute("disabled")
    if disabled is not None and disabled.lower() == "true":
        logger.info("Add to Cart disabled attribute is %r", disabled)
        return False, "Add to Cart has disabled=true"

    logger.info("Add to Cart disabled attribute is %r", disabled)
    return True, "Add to Cart is enabled"


def extract_price(page):
    text = page.locator("body").inner_text(timeout=5000)
    return clean_price(text)


def check_product(browser, product):
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000},
        locale="en-IN",
        timezone_id="Asia/Kolkata",
    )
    page = context.new_page()

    try:
        logger.info("Checking product: %s", product["name"])
        page.goto(product["url"], wait_until="domcontentloaded", timeout=45000)
        logger.info("Product page loaded")
        page.wait_for_timeout(2500)

        # Set PIN before judging availability.
        set_pincode(page)

        # Useful when running locally with headless=False: leave the page open
        # after the delivery check so its result can be inspected in the browser.
        if os.environ.get("PLAYWRIGHT_PAUSE_AFTER_PIN") == "1":
            input("PIN applied. Inspect the browser, then press Enter to continue... ")

        available, reason = detect_orderability(page)
        price = extract_price(page)
        logger.info("Result: available=%s, reason=%s, price=%s", available, reason, price)

        result = {
            "name": product["name"],
            "url": product["url"],
            "available": available,
            "reason": reason,
            "price": price,
        }

        if not available:
            # Save evidence for debugging failed PIN/DOM assumptions.
            Path("debug").mkdir(exist_ok=True)
            safe_name = re.sub(r"[^a-z0-9]+", "-", product["name"].lower()).strip("-")
            page.screenshot(path=f"debug/{safe_name}.png", full_page=True)
            logger.info("Saved debug screenshot for unavailable product")

        return result
    finally:
        context.close()


def main():
    logger.info("Starting Amul stock check for %d products", len(PRODUCTS))
    state = load_state()
    results = []
    headless = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() not in {"0", "false", "no"}

    with sync_playwright() as p:
        logger.info("Launching Chromium (headless=%s)", headless)
        browser = p.chromium.launch(headless=headless)
        for product in PRODUCTS:
            try:
                result = check_product(browser, product)
            except Exception as exc:
                logger.exception("Check failed for %s", product["name"])
                result = {
                    "name": product["name"],
                    "url": product["url"],
                    "available": False,
                    "reason": f"CHECK_ERROR: {exc}",
                    "price": "Unknown",
                }
            results.append(result)
        browser.close()

    changed = False

    for result in results:
        key = result["url"]
        previous = state.get(key, {}).get("available", False)

        # Notify only on a False -> True transition.
        if result["available"] and not previous:
            message = (
                "🚨 AMUL PROTEIN IN STOCK!\n\n"
                f"{result['name']}\n"
                f"PIN: {PINCODE}\n"
                f"Price: {result['price']}\n\n"
                f"{result['url']}\n\n"
                f"Playwright confirmed an enabled Add to Cart after checking PIN {PINCODE}."
            )
            telegram_notify(message)
        elif result["available"]:
            logger.info("Product remains available; no duplicate notification sent")
        else:
            logger.info("Product is unavailable; no notification sent")

        state[key] = {
            "available": result["available"],
            "price": result["price"],
            "reason": result["reason"],
        }
        changed = True

        print(
            f"{result['name']}: "
            f"{'AVAILABLE' if result['available'] else 'UNAVAILABLE'} — "
            f"{result['reason']} — {result['price']}"
        )

    if changed:
        save_state(state)
        logger.info("Saved latest stock state to %s", STATE_FILE)

    # Fail the run on unexpected checker errors, but not on normal out-of-stock.
    if any(r["reason"].startswith("CHECK_ERROR:") for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
