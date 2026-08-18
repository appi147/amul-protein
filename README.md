# Amul Chocolate Whey Stock Notifier

Checks the official Amul Shop every 5 minutes using Playwright, enters PIN `500084`,
and alerts via Telegram only when either Chocolate Whey Protein pack becomes
actually orderable with an enabled **Add to Cart** control.

Products monitored:

- 60 sachets: https://shop.amul.com/en/product/amul-chocolate-whey-protein-34-g-or-pack-of-60-sachets
- 30 sachets: https://shop.amul.com/en/product/amul-chocolate-whey-protein-34-g-or-pack-of-30-sachets

## 1. Create a GitHub repository

Create a new repository, preferably private, and upload these files.

The included Cloudflare Worker triggers the GitHub Actions workflow every five minutes.

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

## Cloudflare scheduling (recommended)

GitHub's built-in scheduler can delay runs. The included Cloudflare Worker calls this
workflow's `workflow_dispatch` API every five minutes instead.

1. In GitHub, create a **fine-grained personal access token** restricted to this
   repository with **Actions: Read and write** and **Contents: Read** permissions.
2. Install Wrangler and sign in to Cloudflare:

   ```powershell
   npm install -g wrangler
   wrangler login
   ```

3. From the repository root, store the token as a Worker secret and deploy:

   ```powershell
   cd cloudflare-dispatcher
   wrangler secret put GITHUB_TOKEN
   wrangler deploy
   ```

   Paste the GitHub token only when Wrangler prompts for it. Never add it to
   `wrangler.toml`, the workflow file, or a GitHub repository secret.

4. Confirm the worker has the `*/5 * * * *` Cron Trigger in Cloudflare Dashboard
   → Workers & Pages → `amul-github-dispatcher` → Settings → Triggers.

Deploy the Worker before pushing the workflow change that removes GitHub's own
`schedule` trigger. The workflow retains `workflow_dispatch` for Cloudflare and
manual runs from the GitHub Actions page.
