# Amul Chocolate Whey Stock Notifier

Checks the official Amul Shop every 5 minutes using Playwright, enters PIN `500084`,
and alerts via Telegram only when either Chocolate Whey Protein pack becomes
actually orderable with an enabled **Add to Cart** control.

Products monitored:

- 60 sachets: https://shop.amul.com/en/product/amul-chocolate-whey-protein-34-g-or-pack-of-60-sachets
- 30 sachets: https://shop.amul.com/en/product/amul-chocolate-whey-protein-34-g-or-pack-of-30-sachets

## 1. Create a GitHub repository

Create a new repository, preferably private, and upload these files.

The workflow is already configured for GitHub Actions every 5 minutes.

GitHub's documented minimum schedule interval is 5 minutes.

## 2. Create a Telegram bot

In Telegram:

1. Open `@BotFather`.
2. Send `/newbot`.
3. Follow the prompts.
4. Copy the bot token.
5. Send any message to your new bot.
6. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`.
7. Find your chat's `chat.id`.

## 3. Add GitHub secrets and variables

Repository → Settings → Secrets and variables → Actions → New repository secret.

Add:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Do not put either value in the source code.

Also add the repository Actions variable `PINCODE` with the delivery PIN to check.
If it is not set, the monitor uses `500084`.

## 4. Run it once manually

Repository → Actions → **Amul Chocolate Whey Stock Monitor** → Run workflow.

Check the log.

If Amul changes its page structure, a screenshot is uploaded as the `amul-debug-screenshots`
artifact so the selector can be updated without guessing.

## Local visual debugging

GitHub Actions runs Chromium without a visible window. To watch the same check locally,
activate your virtual environment and run:

```powershell
$env:PLAYWRIGHT_HEADLESS = "false"
$env:PLAYWRIGHT_PAUSE_AFTER_PIN = "1"
python checker.py
```

After the PIN is selected, the terminal waits until you press Enter. Leave both variables
unset in GitHub Actions; Chromium runs headlessly there. The Actions log records page loading,
PIN selection, the `disabled` value of Add to Cart, and the final result for each product.

## Important behavior

The notifier does NOT alert merely because the page contains generic "In Stock" text.

It requires:

- PIN `500084` to be entered;
- a visible **Add to Cart** control;
- Add to Cart not disabled;
- no main-product `Sold Out` / `Notify Me` state.

It also remembers the last state in `state.json`, so it sends an alert on an
unavailable → available transition rather than every five minutes while the item
remains available.

## GitHub Actions timing

GitHub schedules are not guaranteed to start at the exact second/minute requested;
a 5-minute cron is the minimum supported interval and runs on GitHub-hosted runners.
