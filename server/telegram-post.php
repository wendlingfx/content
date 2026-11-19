<?php
// Wendling FX: posts closed trades (in % of the account) and a weekly summary to the Telegram channel.
// Also mirrors the TikTok videos (queue.json) and sends extra posts from telegram.json in the repo.
// Reads ../data/closed-trades.json, ../data/stats.json and ../data/performance.json (written by update-trades.php).
// Config: private/telegram.php returns ['token' => '...', 'chat' => '@wendlingfx'].
// Run by cron a few minutes after update-trades.php.

$cfg       = require __DIR__ . '/telegram.php';
$token     = trim((string) ($cfg['token'] ?? ''));
$chat      = (string) ($cfg['chat'] ?? '@wendlingfx');
$stateFile = __DIR__ . '/telegram-state.json';
$dataDir   = dirname(__DIR__) . '/data/';
$pubFile   = $dataDir . 'telegram-status.json';

function pub(string $f, array $s): void { $s['checked'] = gmdate('Y-m-d\TH:i\Z'); @file_put_contents($f, json_encode($s, JSON_UNESCAPED_SLASHES)); }
function jread(string $f): array { return is_file($f) ? (json_decode((string) file_get_contents($f), true) ?: []) : []; }
function pc(float $x): string { $a = abs($x); $a = $a >= 10 ? (string) round($a) : (string) round($a, 1); return ($x > 0 ? '+' : ($x < 0 ? '-' : '')) . $a . '%'; }

function tg(string $token, string $chat, string $text): array {
    $ch = curl_init('https://api.telegram.org/bot' . $token . '/sendMessage');
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 30, CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => ['chat_id' => $chat, 'text' => $text, 'disable_web_page_preview' => 'true'],
    ]);
    $raw = curl_exec($ch); curl_close($ch);
    $d = json_decode((string) $raw, true);
    return is_array($d) ? $d : ['ok' => false, 'description' => 'no response'];
}

// One-time environment check for a Telegram user client on this server (no secrets): data/env-probe.json
$probeFile = dirname(__DIR__) . '/data/env-probe.json';
if (!is_file($probeFile)) {
    $dis = array_map('trim', explode(',', (string) ini_get('disable_functions')));
    $canExec = function_exists('exec') && !in_array('exec', $dis, true);
    $py = $canExec ? @exec('python3 --version 2>&1') : null;
    $pyPath = $canExec ? @exec('command -v python3 2>&1') : null;
    $pip = $canExec ? @exec('python3 -m pip --version 2>&1') : null;
    $errno = 0; $errstr = '';
    $fp = @fsockopen('149.154.167.51', 443, $errno, $errstr, 10);
    $mt = $fp ? 'ok' : ("$errno $errstr"); if ($fp) fclose($fp);
    $home = getenv('HOME') ?: '';
    @file_put_contents($probeFile, json_encode(['php' => PHP_VERSION, 'exec' => $canExec, 'python' => $py, 'pythonPath' => $pyPath, 'pip' => $pip,
        'mtproto443' => $mt, 'homeAboveWeb' => $home !== '' && is_dir($home) && is_writable($home), 'exts' => ['sockets' => extension_loaded('sockets'), 'gmp' => extension_loaded('gmp'), 'openssl' => extension_loaded('openssl')],
        'at' => gmdate('Y-m-d\TH:i\Z')], JSON_UNESCAPED_SLASHES));
}

if ($token === '') { pub($pubFile, ['ok' => false, 'error' => 'token not set']); exit(0); }

$state  = jread($stateFile) + ['posted' => [], 'seeded' => false, 'lastWeekly' => ''];
$trades = jread($dataDir . 'closed-trades.json')['trades'] ?? [];
$stats  = jread($dataDir . 'stats.json');
$days   = jread($dataDir . 'performance.json')['days'] ?? [];
$since  = !empty($stats['since']) ? date('M j, Y', strtotime($stats['since'])) : '';
$total  = isset($stats['gain']) ? pc((float) $stats['gain']) : '';
$log = []; $sent = 0;

$key = fn($t) => $t['closed'] . '|' . $t['symbol'] . '|' . $t['side'] . '|' . ($t['pct'] ?? $t['result']);

// One time: set the channel photo from the repo (needs "Change channel info" for the bot).
if (empty($state['photoSet'])) {
    $img = @file_get_contents('https://raw.githubusercontent.com/wendlingfx/content/main/brand/channel.png');
    if ($img !== false && strlen($img) > 1000) {
        $tmp = sys_get_temp_dir() . '/wfx-channel.png'; file_put_contents($tmp, $img);
        $ch = curl_init('https://api.telegram.org/bot' . $token . '/setChatPhoto');
        curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 60, CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => ['chat_id' => $chat, 'photo' => new CURLFile($tmp, 'image/png', 'channel.png')]]);
        $r = json_decode((string) curl_exec($ch), true); curl_close($ch); @unlink($tmp);
        if (!empty($r['ok'])) { $state['photoSet'] = true; $log[] = 'photo set'; } else { $log[] = 'photo: ' . ($r['description'] ?? 'failed'); }
    }
}

// First run: say hello once and mark the trades already closed as seen.
if (!$state['seeded']) {
    $msg = "Wendling FX: live account updates.\n\n"
         . "Every trade I close is posted here, in % of the account, plus a short result every day.\n\n"
         . ($total ? "Account so far: $total.\n" : '')
         . "Verified record: wendlingfx.com\n\n"
         . "Trading on margin is high risk. Not financial advice.";
    $r = tg($token, $chat, $msg);
    if (empty($r['ok'])) { pub($pubFile, ['ok' => false, 'error' => $r['description'] ?? 'send failed']); exit(1); }
    foreach ($trades as $t) $state['posted'][] = $key($t);
    $state['seeded'] = true; $log[] = 'welcome sent';
} elseif (false) { // 19/11: one post per trade switched off (the daily close card covers it; it flooded the channel)
    // New closed trades, oldest first, at most 5 per run.
    $new = array_values(array_filter(array_reverse($trades), fn($t) => isset($t['pct']) && !in_array($key($t), $state['posted'], true)));
    foreach (array_slice($new, 0, 5) as $t) {
        $p = (float) $t['pct'];
        $msg = ($p > 0 ? "\u{1F7E2}" : ($p < 0 ? "\u{1F534}" : "\u{26AA}")) . ' ' . $t['symbol'] . ' ' . $t['side'] . " closed\n"
             . pc($p) . " of the account\n"
             . ($total ? "Account total: $total" : '');
        $r = tg($token, $chat, trim($msg));
        if (empty($r['ok'])) { $log[] = 'error: ' . ($r['description'] ?? '?'); break; }
        $state['posted'][] = $key($t); $sent++;
    }
    if ($sent) $log[] = "$sent trades";
}

// Weekly summary: now the Monday weekly video (mirrored from queue.json), no separate text post.

// Media queue: videos from queue.json (same file and time as TikTok) and extra posts from telegram.json.
// telegram.json items: {id, due (UTC ISO), type: photo|document|video|text, file (repo path, not for text), caption, pin?}
function tg_file(string $token, string $method, string $field, string $chat, string $path, string $caption): array {
    $mime = function_exists('mime_content_type') ? (mime_content_type($path) ?: 'application/octet-stream') : 'application/octet-stream';
    $post = ['chat_id' => $chat, $field => new CURLFile($path, $mime, basename($path)), 'caption' => $caption];
    if ($field === 'video') $post['supports_streaming'] = 'true';
    $ch = curl_init('https://api.telegram.org/bot' . $token . '/' . $method);
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 120, CURLOPT_POST => true, CURLOPT_POSTFIELDS => $post]);
    $d = json_decode((string) curl_exec($ch), true); curl_close($ch);
    return is_array($d) ? $d : ['ok' => false, 'description' => 'no response'];
}
function tg_call(string $token, string $method, array $params): array {
    $ch = curl_init('https://api.telegram.org/bot' . $token . '/' . $method);
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 30, CURLOPT_POST => true, CURLOPT_POSTFIELDS => $params]);
    $d = json_decode((string) curl_exec($ch), true); curl_close($ch);
    return is_array($d) ? $d : ['ok' => false, 'description' => 'no response'];
}
$raw = 'https://raw.githubusercontent.com/wendlingfx/content/main/';
$fetchJson = function (string $name) use ($raw): array {
    $j = @file_get_contents($raw . $name . '?t=' . time());
    $d = $j !== false ? json_decode($j, true) : null;
    return is_array($d) ? $d : [];
};
$state += ['media' => [], 'mediaSeeded' => false];
$todo = [];
$vq = $fetchJson('queue.json');
$replaced = [];
foreach ($vq as $v) if (!empty($v['replaces'])) $replaced[$v['replaces']] = true;
foreach ($vq as $v) {
    if (empty($v['id']) || empty($v['file']) || !empty($v['noTelegram']) || isset($replaced[$v['id']])) continue;
    $cap = trim(preg_replace('/\s*#\w+/u', '', (string) ($v['text'] ?? '')));
    $todo[] = ['id' => 'tt:' . $v['id'], 'due' => $v['due'] ?? '', 'type' => 'video', 'local' => dirname(__DIR__) . '/media/' . basename($v['file']),
               'file' => 'media/' . basename($v['file']), 'caption' => $cap . "\n\nFull record: wendlingfx.com"];
}
foreach ($fetchJson('telegram.json') as $m) if (!empty($m['id'])) $todo[] = $m + ['type' => 'text'];
// First run of this block: anything already past due is marked as done, so old posts are not dumped at once.
if (!$state['mediaSeeded']) {
    foreach ($todo as $m) if (($m['due'] ?? '') !== '' && strtotime($m['due']) < time() - 3600) $state['media'][$m['id']] = 'skipped';
    $state['mediaSeeded'] = true;
}
$mediaSent = 0;
foreach ($todo as $m) {
    if (isset($state['media'][$m['id']]) || $mediaSent >= 2) continue;
    if (($m['due'] ?? '') === '' || strtotime($m['due']) > time()) continue;
    $type = $m['type'] ?? 'text'; $cap = (string) ($m['caption'] ?? '');
    if ($type === 'text') {
        $r = tg($token, $chat, $cap);
    } else {
        $path = $m['local'] ?? '';
        if ($path === '' || !is_file($path)) {
            $bin = @file_get_contents($raw . $m['file']);
            if ($bin === false || strlen($bin) < 500) { $log[] = $m['id'] . ': file not found'; continue; }
            $path = sys_get_temp_dir() . '/wfx-' . basename($m['file']); file_put_contents($path, $bin); $tmp = true;
        }
        [$method, $field] = ['photo' => ['sendPhoto', 'photo'], 'document' => ['sendDocument', 'document'], 'video' => ['sendVideo', 'video']][$type] ?? ['sendDocument', 'document'];
        $r = tg_file($token, $method, $field, $chat, $path, mb_substr($cap, 0, 1024));
        if (!empty($tmp)) { @unlink($path); $tmp = false; }
    }
    if (!empty($r['ok'])) {
        $state['media'][$m['id']] = 'sent'; $mediaSent++; $log[] = $m['id'] . ': sent';
        if (!empty($m['pin']) && !empty($r['result']['message_id'])) {
            $p = tg_call($token, 'pinChatMessage', ['chat_id' => $chat, 'message_id' => $r['result']['message_id'], 'disable_notification' => 'true']);
            $log[] = $m['id'] . ': ' . (!empty($p['ok']) ? 'pinned' : 'pin failed (' . ($p['description'] ?? '?') . ')');
        }
    } else { $log[] = $m['id'] . ': ' . ($r['description'] ?? 'error'); }
}

// Weekly reminder of the start guide: Wednesday from 15:00 UTC, once per ISO week, rotating texts.
$wk = gmdate('o-\WW');
if ((int) gmdate('N') === 3 && (int) gmdate('G') >= 15 && ($state['startPromo'] ?? '') !== $wk) {
    $texts = ["How to start copying, step by step\n\nNo cTrader yet, cTrader with Copy, or a broker without Copy: pick your case and follow the screenshots.\n\nhttps://wendlingfx.com/start/",
              "Thinking about copying the account?\n\nThe whole setup is 5 to 7 steps, with screenshots for each one. Your money stays in an account in your name.\n\nhttps://wendlingfx.com/start/",
              "Copy the live account on cTrader Copy\n\nMinimum US$500. 30% fee on new profit only. Stop anytime.\n\nStep by step: https://wendlingfx.com/start/"];
    $r = tg($token, $chat, $texts[((int) gmdate('W')) % 3]);
    if (!empty($r['ok'])) { $state['startPromo'] = $wk; $log[] = 'start guide reminder sent'; }
}

// ---- Health check (every run): alerts go to Lucas in private through the bot, only when something changes ----
// Alert chat id in private/telegram-alert.json {"chat": 123}. Problems are kept in private/health-state.json.
$alertCfg = jread(__DIR__ . '/telegram-alert.json'); $alertChat = $alertCfg['chat'] ?? null;
if ($alertChat) {
    $age = function (string $f, string $k = 'updated') use ($dataDir) { $d = jread($dataDir . $f); return isset($d[$k]) ? time() - strtotime($d[$k]) : 1e9; };
    $prob = [];
    $wd = (int) gmdate('N'); $mktOpen = !($wd === 6 || ($wd === 7 && (int) gmdate('G') < 22) || ($wd === 5 && (int) gmdate('G') >= 22));
    if ($age('stats.json') > 3 * 3600) $prob['stats'] = 'Números do site (Myfxbook) sem atualizar há mais de 3 h';
    $lv = jread($dataDir . 'live.json');
    if (empty($lv['ok'])) $prob['live'] = 'cTrader desconectado: ' . substr((string) ($lv['error'] ?? '?'), 0, 80);
    elseif ($age('live.json') > 15 * 60) $prob['live'] = 'Leitura ao vivo do cTrader parada há mais de 15 min';
    if ($age('market.json') > 3 * 3600) $prob['market'] = 'Dados de mercado (market.json) sem atualizar há mais de 3 h';
    if ($age('sync-status.json', 'checked') > 3 * 3600) $prob['sync'] = 'Atualização automática pelo GitHub não roda há mais de 3 h';
    $ps = jread($dataDir . 'post-status.json');
    if (time() - strtotime($ps['checked'] ?? '2000-01-01') > 3 * 3600) $prob['buffer'] = 'Envio ao TikTok (Buffer) não roda há mais de 3 h';
    foreach (($ps['state'] ?? []) as $id => $st) if (($st['status'] ?? '') === 'error') $prob['buffer-' . $id] = "TikTok recusou o post $id: " . substr((string) ($st['error'] ?? ''), 0, 80);
    foreach ($todo as $m) {
        $due = strtotime($m['due'] ?? '') ?: 0;
        if ($due && $due < time() - 2 * 3600 && $due > time() - 3 * 86400 && !isset($state['media'][$m['id']])) $prob['tg-' . $m['id']] = 'Post do Telegram atrasado: ' . $m['id'];
    }
    foreach ($log as $l) if (strpos($l, 'error') !== false || strpos($l, 'not found') !== false) $prob['tglog-' . md5($l)] = 'Telegram: ' . $l;
    $hs = jread(__DIR__ . '/health-state.json') + ['open' => []];
    $new = array_diff_key($prob, $hs['open']); $gone = array_diff_key($hs['open'], $prob);
    $msg = [];
    foreach ($new as $k => $v) $msg[] = "\u{26A0}\u{FE0F} $v";
    foreach ($gone as $k => $v) $msg[] = "\u{2705} Resolvido: $v";
    if ($msg) {
        $ch = curl_init('https://api.telegram.org/bot' . $token . '/sendMessage');
        curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20, CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => ['chat_id' => $alertChat, 'text' => "Wendling FX\n\n" . implode("\n", $msg)]]);
        $ok = json_decode((string) curl_exec($ch), true); curl_close($ch);
        if (!empty($ok['ok'])) $hs['open'] = $prob;
    } else { $hs['open'] = $prob; }
    $hs['checked'] = gmdate('Y-m-d\TH:i\Z');
    file_put_contents(__DIR__ . '/health-state.json', json_encode($hs, JSON_UNESCAPED_UNICODE));
    @file_put_contents($dataDir . 'health.json', json_encode(['checked' => $hs['checked'], 'ok' => !$prob, 'problems' => count($prob)]));
}

$state['posted'] = array_slice(array_values(array_unique($state['posted'])), -500);
file_put_contents($stateFile, json_encode($state, JSON_UNESCAPED_SLASHES));
pub($pubFile, ['ok' => true, 'log' => $log]);
echo 'ok: ' . ($log ? implode('; ', $log) : 'nothing new') . "\n";
