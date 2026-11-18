<?php
// Wendling FX: posts closed trades (in % of the account) and a weekly summary to the Telegram channel.
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
         . "Every trade I close is posted here, in % of the account, losses included. Plus a short result every Sunday.\n\n"
         . ($total ? "Account so far: $total" . ($since ? " since $since" : '') . ".\n" : '')
         . "Verified record: wendlingfx.com\n\n"
         . "Trading on margin is high risk. Not financial advice.";
    $r = tg($token, $chat, $msg);
    if (empty($r['ok'])) { pub($pubFile, ['ok' => false, 'error' => $r['description'] ?? 'send failed']); exit(1); }
    foreach ($trades as $t) $state['posted'][] = $key($t);
    $state['seeded'] = true; $log[] = 'welcome sent';
} else {
    // New closed trades, oldest first, at most 5 per run.
    $new = array_values(array_filter(array_reverse($trades), fn($t) => isset($t['pct']) && !in_array($key($t), $state['posted'], true)));
    foreach (array_slice($new, 0, 5) as $t) {
        $p = (float) $t['pct'];
        $msg = ($p > 0 ? "\u{1F7E2}" : ($p < 0 ? "\u{1F534}" : "\u{26AA}")) . ' ' . $t['symbol'] . ' ' . $t['side'] . " closed\n"
             . pc($p) . " of the account\n"
             . ($total ? "Total" . ($since ? " since $since" : '') . ": $total" : '');
        $r = tg($token, $chat, trim($msg));
        if (empty($r['ok'])) { $log[] = 'error: ' . ($r['description'] ?? '?'); break; }
        $state['posted'][] = $key($t); $sent++;
    }
    if ($sent) $log[] = "$sent trades";
}

// Weekly summary: Sunday from 20:00 UTC, once per ISO week.
$week = gmdate('o-\WW');
if ((int) gmdate('N') === 7 && (int) gmdate('G') >= 20 && $state['lastWeekly'] !== $week && count($days) >= 2) {
    $mon = strtotime('monday this week', time());
    $start = null; $end = end($days);
    foreach ($days as $d) if (strtotime($d['d']) < $mon) $start = $d;
    $g0 = $start ? (float) $start['g'] : 0.0; $g1 = (float) $end['g'];
    $wk = ((1 + $g1 / 100) / (1 + $g0 / 100) - 1) * 100;
    $msg = "Week of " . gmdate('M j', $mon) . ": " . pc($wk) . " on the account.\n"
         . ($total ? "Total" . ($since ? " since $since" : '') . ": $total\n" : '')
         . "Full record: wendlingfx.com";
    $r = tg($token, $chat, $msg);
    if (!empty($r['ok'])) { $state['lastWeekly'] = $week; $log[] = 'weekly sent'; } else { $log[] = 'weekly error: ' . ($r['description'] ?? '?'); }
}

$state['posted'] = array_slice(array_values(array_unique($state['posted'])), -500);
file_put_contents($stateFile, json_encode($state, JSON_UNESCAPED_SLASHES));
pub($pubFile, ['ok' => true, 'log' => $log]);
echo 'ok: ' . ($log ? implode('; ', $log) : 'nothing new') . "\n";
