<?php
// Wendling FX Telegram bot: answers /start (and any message) with the step-by-step to copy WFX Prime.
// Webhook endpoint: https://wendlingfx.com/bot-hook.php
// One-time setup: open https://wendlingfx.com/bot-hook.php?setup=1 (sets the webhook to this URL and writes data/bot.json with the bot username).
// Token comes from private/telegram.php (never in the repo). The webhook secret is derived from the token, so it is not in the repo either.
// Users who start the bot are kept in private/bot-users.json (chat id, first seen, source) for later follow-up.

$cfg = @include __DIR__ . '/private/telegram.php';
$token = is_array($cfg) ? ($cfg['token'] ?? '') : '';
if ($token === '') { http_response_code(503); exit('not configured'); }
$secret = substr(hash('sha256', $token . '|wfx-bot-hook'), 0, 40);

function tg($token, $method, $payload) {
    $ch = curl_init('https://api.telegram.org/bot' . $token . '/' . $method);
    curl_setopt_array($ch, [CURLOPT_POST => true, CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20,
        CURLOPT_HTTPHEADER => ['Content-Type: application/json'], CURLOPT_POSTFIELDS => json_encode($payload)]);
    $r = curl_exec($ch); curl_close($ch);
    return json_decode((string)$r, true);
}

if (isset($_GET['setup'])) {
    $me = tg($token, 'getMe', new stdClass());
    $wh = tg($token, 'setWebhook', ['url' => 'https://wendlingfx.com/bot-hook.php', 'secret_token' => $secret,
        'allowed_updates' => ['message'], 'drop_pending_updates' => true]);
    $out = ['username' => $me['result']['username'] ?? null, 'webhook' => (bool)($wh['ok'] ?? false),
            'error' => $wh['description'] ?? null, 'at' => gmdate('Y-m-d\TH:i\Z')];
    @file_put_contents(__DIR__ . '/data/bot.json', json_encode($out));
    header('Content-Type: application/json'); echo json_encode($out); exit;
}

if (($_SERVER['HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN'] ?? '') !== $secret) { http_response_code(403); exit; }
$u = json_decode(file_get_contents('php://input'), true);
$msg = $u['message'] ?? null;
if (!$msg || ($msg['chat']['type'] ?? '') !== 'private') { echo 'ok'; exit; }
$chat = $msg['chat']['id'];
$text = trim($msg['text'] ?? '');

// keep a small list of who started the bot
$src = 'direct';
if (preg_match('~^/start(?:\s+([A-Za-z0-9_-]{1,32}))?~', $text, $m)) $src = $m[1] ?? 'direct';
$file = __DIR__ . '/private/bot-users.json';
$users = json_decode((string)@file_get_contents($file), true) ?: [];
$key = (string)$chat;
if (!isset($users[$key])) {
    $users[$key] = ['first' => gmdate('Y-m-d\TH:i\Z'), 'source' => $src, 'lang' => $msg['from']['language_code'] ?? null];
    if (count($users) <= 50000) @file_put_contents($file, json_encode($users), LOCK_EX);
}

$steps = "Copy WFX Prime on cTrader in 7 steps:\n\n"
    . "1. Create your Fusion Markets login (button below).\n"
    . "2. Open a live account: type Zero, platform cTrader, currency USD.\n"
    . "3. Verify your identity (photo ID and proof of address).\n"
    . "4. Fund it with at least US\$500.\n"
    . "5. Open the WFX Prime strategy and press Start copying.\n"
    . "6. Choose the amount and confirm. The fee is 30% of new profit only.\n"
    . "7. Set your equity stop loss: the lowest amount you accept.\n\n"
    . "Your money stays in an account in your name. You can stop copying at any time.\n\n"
    . "Full guide with screenshots: wendlingfx.com/start\n\n"
    . "Trading on margin is high risk. Not financial advice.";
$kb = ['inline_keyboard' => [
    [['text' => '1. Open a Fusion Markets account', 'url' => 'https://fusionmarkets.com/?refcode=125918']],
    [['text' => '5. Open the WFX Prime strategy', 'url' => 'https://app.fusionmarkets.com/copy/strategy/125209']],
    [['text' => 'Guide with screenshots', 'url' => 'https://wendlingfx.com/start/']],
    [['text' => 'Daily updates (free channel)', 'url' => 'https://t.me/wendlingfx']],
]];

if (strpos($text, '/start') === 0) {
    tg($token, 'sendMessage', ['chat_id' => $chat, 'text' => "Hi! Welcome to Wendling FX."]);
}
tg($token, 'sendMessage', ['chat_id' => $chat, 'text' => $steps, 'reply_markup' => $kb, 'disable_web_page_preview' => true]);
echo 'ok';
