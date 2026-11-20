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
// Content pause (private/pause.json): only ids starting with an allowed prefix are posted.
$PAUSE = jread(__DIR__ . '/pause.json');
function allowed(array $P, string $id): bool { if (empty($P['paused'])) return true; foreach ((array) ($P['allow'] ?? []) as $a) if ($a !== '' && strpos(preg_replace('/^tt:/', '', $id), $a) === 0) return true; return false; }
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
// One-time channel purge (pause.json purge: {id, upTo}): deletes messages 1..upTo and unpins all, before any new post.
$pg = $PAUSE['purge'] ?? null;
if (is_array($pg) && !empty($pg['id']) && ($state['purged'] ?? '') !== $pg['id']) {
    $upTo = min(1000, (int) ($pg['upTo'] ?? 0)); $okN = 0; $errs = [];
    tg_call($token, 'unpinAllChatMessages', ['chat_id' => $chat]);
    for ($a = 1; $a <= $upTo; $a += 100) {
        $ids = range($a, min($upTo, $a + 99));
        $r = tg_call($token, 'deleteMessages', ['chat_id' => $chat, 'message_ids' => json_encode($ids)]);
        if (!empty($r['ok'])) $okN++; else $errs[] = $r['description'] ?? '?';
        // Fallback one by one (older Bot API or partial rights)
        if (empty($r['ok'])) foreach ($ids as $i) tg_call($token, 'deleteMessage', ['chat_id' => $chat, 'message_id' => $i]);
    }
    $state['purged'] = $pg['id'];
    $log[] = 'purge ' . $pg['id'] . ': ' . ($errs ? 'bulk failed (' . implode('; ', $errs) . '), single deletes tried' : 'done up to ' . $upTo);
}
$mediaSent = 0;
foreach ($todo as $m) {
    if (isset($state['media'][$m['id']]) || $mediaSent >= 2 || !allowed($PAUSE, (string) $m['id'])) continue;
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
if (empty($PAUSE['paused']) && (int) gmdate('N') === 3 && (int) gmdate('G') >= 15 && ($state['startPromo'] ?? '') !== $wk) {
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
        if (allowed($PAUSE, (string) $m['id']) && $due && $due < time() - 2 * 3600 && $due > time() - 3 * 86400 && !isset($state['media'][$m['id']])) $prob['tg-' . $m['id']] = 'Post do Telegram atrasado: ' . $m['id'];
    }
    foreach ($log as $l) if (strpos($l, 'error') !== false || strpos($l, 'not found') !== false) $prob['tglog-' . md5($l)] = 'Telegram: ' . $l;
    // ---- Copy chain watch (private/copy-watch.json, no secrets): signal page -> MT5 -> copier -> cTrader ----
    $cwc = jread(__DIR__ . '/copy-watch.json');
    if (!empty($cwc['enabled'])) {
        $cs = jread(__DIR__ . '/copy-state.json'); $ws = jread(__DIR__ . '/copy-watch-state.json');
        $nm = (string) ($cwc['name'] ?? 'sinal');
        // 1. Provider's public trade count, read at most every 30 min. A failed read is ignored (the site rate-limits).
        if ($mktOpen && time() - (int) ($ws['fetchedAt'] ?? 0) >= 1700 && !empty($cwc['signal_url'])) {
            $ch = curl_init((string) $cwc['signal_url']);
            curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 25, CURLOPT_FOLLOWLOCATION => true, CURLOPT_HTTPHEADER => ['Accept-Language: en'],
                CURLOPT_USERAGENT => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36']);
            $html = (string) curl_exec($ch); curl_close($ch);
            $ws['fetchedAt'] = time();
            if (preg_match('~Trades:\s*</div>[^<]*<[^>]+>\s*([\d\s\x{a0}]+)<~u', $html, $mm)) {
                $n = (int) preg_replace('/\D/', '', $mm[1]);
                if (isset($ws['trades']) && $n > (int) $ws['trades']) $ws['pending'] = time();
                $ws['trades'] = $n; $ws['okAt'] = time();
            }
        }
        // 2. Provider closed a trade: our account must have moved (position seen or balance changed) in the hours before.
        $act = (int) ($cs['activityAt'] ?? 0);
        if (!empty($ws['pending']) && $act >= (int) $ws['pending'] - 6 * 3600) unset($ws['pending']);
        if (!empty($ws['pending']) && time() - (int) $ws['pending'] > 20 * 60) $prob['copy-miss'] = "CÓPIA: $nm fechou trade e a conta cTrader não teve movimento. Conferir assinatura, VPS e Duplikium";
        if ($mktOpen && isset($ws['okAt']) && time() - (int) $ws['okAt'] > 26 * 3600) $prob['copy-src'] = "CÓPIA: não consigo ler a página do $nm há mais de 1 dia";
        // 3. Position open far longer than the provider's usual holding time.
        if ((int) ($cs['open'] ?? 0) > 0 && (int) ($cs['oldestMin'] ?? 0) > (int) ($cwc['max_open_min'] ?? 360)) $prob['copy-stuck'] = 'CÓPIA: posição aberta na cTrader há ' . round($cs['oldestMin'] / 60, 1) . ' h (pode ter ficado órfã)';
        // 4. Equity drop in the day.
        $ds = (float) ($cs['dayStart'] ?? 0); $eq = (float) ($cs['equity'] ?? 0);
        if ($ds > 0 && $eq < $ds * (1 - (float) ($cwc['max_day_drop_pct'] ?? 20) / 100)) $prob['copy-drop'] = 'CÓPIA: conta cTrader caiu ' . round((1 - $eq / $ds) * 100) . '% hoje';
        if ($eq > (float) ($cwc['cap_equity'] ?? 1e12)) $prob['copy-cap'] = 'CÓPIA: conta passou de US$ ' . (int) $cwc['cap_equity'] . ', subir o teto de lote no Duplikium';
        // 5. Renewals.
        foreach ((array) ($cwc['expiries'] ?? []) as $e) {
            $left = (strtotime(($e['date'] ?? '') . ' 23:59 UTC') - time()) / 86400;
            if ($left < (float) ($e['warn_days'] ?? 3)) $prob['copy-exp-' . md5(($e['name'] ?? '') . ($e['date'] ?? ''))] = ($left < 0 ? 'VENCEU: ' : 'Vence em ' . max(0, (int) ceil($left)) . ' dia(s): ') . ($e['name'] ?? '?') . ' (' . ($e['date'] ?? '') . ')';
        }
        file_put_contents(__DIR__ . '/copy-watch-state.json', json_encode($ws));
        @file_put_contents($dataDir . 'copy-watch.json', json_encode(['checked' => gmdate('Y-m-d\TH:i\Z'), 'providerTrades' => $ws['trades'] ?? null, 'providerReadAt' => isset($ws['okAt']) ? gmdate('Y-m-d\TH:i\Z', (int) $ws['okAt']) : null, 'pending' => !empty($ws['pending']), 'open' => (int) ($cs['open'] ?? 0)]));
    }
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
