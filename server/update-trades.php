<?php
// Wendling FX: pulls the latest closed trades from Myfxbook and writes
// ../data/closed-trades.json for the "Latest closed trades" section.
// Run by an hourly cron job: php /home/<user>/domains/wendlingfx.com/public_html/private/update-trades.php

$cfg      = require __DIR__ . '/config.php';
// private/account.json (synced from the repo, no secrets) can point the stats at another Myfxbook account.
$ov = is_file(__DIR__ . '/account.json') ? (json_decode((string) file_get_contents(__DIR__ . '/account.json'), true) ?: []) : [];
if ((int) ($ov['myfxbook_id'] ?? 0) > 0) $cfg['account_id'] = (int) $ov['myfxbook_id'];
$outFile  = dirname(__DIR__) . '/data/closed-trades.json';
$sessFile = __DIR__ . '/.session';

function mfx_api(string $method, array $params): ?array {
    $url = 'https://www.myfxbook.com/api/' . $method . '?' . http_build_query($params);
    $ch  = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 30,
        CURLOPT_USERAGENT      => 'WendlingFX/1.0',
    ]);
    $raw = curl_exec($ch);
    curl_close($ch);
    if ($raw === false) return null;
    $data = json_decode($raw, true);
    return is_array($data) ? $data : null;
}

function mfx_login(array $cfg, string $sessFile): ?string {
    if ($cfg['email'] === '' || $cfg['password'] === '') {
        fwrite(STDERR, "config.php: e-mail or password is empty\n");
        return null;
    }
    $r = mfx_api('login.json', ['email' => $cfg['email'], 'password' => $cfg['password']]);
    if (!$r || !empty($r['error']) || empty($r['session'])) {
        fwrite(STDERR, 'login failed: ' . ($r['message'] ?? 'no response') . "\n");
        return null;
    }
    $session = urldecode($r['session']);
    file_put_contents($sessFile, $session);
    @chmod($sessFile, 0600);
    return $session;
}

function mfx_history(string $session, int $id): ?array {
    $r = mfx_api('get-history.json', ['session' => $session, 'id' => $id]);
    if (!$r || !empty($r['error']) || !isset($r['history'])) return null;
    return $r['history'];
}

// Sessions last about a month and only work from this server's IP: reuse, re-login when needed.
$session = is_file($sessFile) ? trim((string) file_get_contents($sessFile)) : '';
$history = $session !== '' ? mfx_history($session, (int) $cfg['account_id']) : null;
if ($history === null) {
    $session = mfx_login($cfg, $sessFile);
    if ($session === null) exit(1);
    $history = mfx_history($session, (int) $cfg['account_id']);
}
if ($history === null) {
    fwrite(STDERR, "could not read history\n");
    exit(1);
}

// Account data first: the current balance lets us size every trade in % of the account.
$acc = null;
$ra = mfx_api('get-my-accounts.json', ['session' => $session]);
if ($ra && empty($ra['error']) && !empty($ra['accounts'])) {
    foreach ($ra['accounts'] as $a) if ((int) ($a['id'] ?? 0) === (int) $cfg['account_id']) $acc = $a;
}

// Every balance event (trades, deposits, withdrawals), oldest first.
$events = []; $actions = [];
foreach ($history as $t) {
    $action = strtolower(trim($t['action'] ?? ''));
    $actions[$action] = ($actions[$action] ?? 0) + 1;
    $closed = DateTime::createFromFormat('m/d/Y H:i', $t['closeTime'] ?? ($t['openTime'] ?? ''), new DateTimeZone('UTC'));
    if (!$closed) $closed = DateTime::createFromFormat('m/d/Y H:i', $t['openTime'] ?? '', new DateTimeZone('UTC'));
    if (!$closed) continue;
    $gross = (float) ($t['profit'] ?? 0);
    $net = $gross + (float) ($t['interest'] ?? 0) + (float) ($t['commission'] ?? 0);
    $isTrade = ($action === 'buy' || $action === 'sell');
    $isCash  = !$isTrade && $net != 0.0; // deposits, withdrawals, balance and credit operations
    if (!$isTrade && !$isCash) continue; // pending orders and the like
    $events[] = [
        'closed' => $closed->format('Y-m-d\TH:i\Z'),
        'key'    => implode('|', [$t['openTime'] ?? '', $t['closeTime'] ?? '', $t['symbol'] ?? '', $action, (string) ($t['sizing']['value'] ?? ''), (string) $net]),
        'trade'  => $isTrade,
        'symbol' => (string) ($t['symbol'] ?? ''),
        'side'   => ucfirst($action),
        'net'    => $net,
        'gross'  => $gross,
    ];
}
usort($events, fn($a, $b) => strcmp($a['closed'], $b['closed']));

// Myfxbook's per-trade "profit" may already include interest and commission. Walking back from today's
// balance must end at about zero before the first deposit: pick the reading that does, so costs are not counted twice.
$bal0 = $acc ? (float) ($acc['balance'] ?? 0) : 0.0;
$resid = function (string $f) use ($events, $bal0) { $b = $bal0; foreach ($events as $e) $b -= $e[$f]; return $b; };
$rNet = $resid('net'); $rGross = $resid('gross');
$field = abs($rGross) < abs($rNet) ? 'gross' : 'net';
foreach ($events as $i => $e) $events[$i]['net'] = $e[$field];
$check = ['mode' => $field, 'residualPct' => $bal0 > 0 ? round(min(abs($rNet), abs($rGross)) * 100 / $bal0, 2) : null];
$bal = $bal0;
for ($i = count($events) - 1; $i >= 0; $i--) {
    $before = $bal - $events[$i]['net'];
    $events[$i]['pct'] = ($events[$i]['trade'] && $before > 0) ? round($events[$i]['net'] * 100 / $before, 2) : null;
    $bal = $before;
}

// Keep every trade ever seen (Myfxbook only returns the most recent ones).
// One store per account: after a switch (account.json) the old account's trades stay out of the new stats.
$storeFile = __DIR__ . ((int) ($ov['myfxbook_id'] ?? 0) > 0 ? '/trades-store-' . (int) $ov['myfxbook_id'] . '.json' : '/trades-store.json');
$store = is_file($storeFile) ? (json_decode((string) file_get_contents($storeFile), true) ?: []) : [];
foreach ($events as $e) {
    if (!$e['trade'] || $e['pct'] === null) continue;
    $store[$e['key']] = ['closed' => $e['closed'], 'symbol' => $e['symbol'], 'side' => $e['side'], 'result' => (int) round($e['net']), 'pct' => $e['pct']];
}
uasort($store, fn($a, $b) => strcmp($a['closed'], $b['closed']));
file_put_contents($storeFile . '.tmp', json_encode($store, JSON_UNESCAPED_SLASHES));
rename($storeFile . '.tmp', $storeFile);
$all = array_values($store);

$trades = array_reverse($all);
$allCount = count($trades);
$wins = count(array_filter($trades, fn($t) => $t['result'] > 0));
$latest = array_slice($trades, 0, (int) ($cfg['keep'] ?? 10));

$payload = json_encode([
    'updated' => gmdate('Y-m-d\TH:i\Z'),
    'trades'  => $latest,
], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);

if (!is_dir(dirname($outFile))) mkdir(dirname($outFile), 0755, true);
$tmp = $outFile . '.tmp';
file_put_contents($tmp, $payload);
rename($tmp, $outFile);
echo 'ok: ' . count($latest) . " trades\n";

// Growth curve, one point per closed trade: data/curve.json
$g = 1.0; $curve = [];
foreach ($all as $t) { $g *= 1 + $t['pct'] / 100; $curve[] = ['t' => $t['closed'], 'g' => round(($g - 1) * 100, 2)]; }
$cf = dirname(__DIR__) . '/data/curve.json';
file_put_contents($cf . '.tmp', json_encode(['updated' => gmdate('Y-m-d\TH:i\Z'), 'actions' => $actions, 'points' => $curve], JSON_UNESCAPED_SLASHES));
rename($cf . '.tmp', $cf);
echo 'ok: curve ' . count($curve) . " points\n";

// Headline and detail stats: data/stats.json
if ($acc) {
    $winP  = array_values(array_filter(array_column($all, 'pct'), fn($p) => $p > 0));
    $lossP = array_values(array_filter(array_column($all, 'pct'), fn($p) => $p < 0));
    $first = $all ? substr($all[0]['closed'], 0, 10) : gmdate('Y-m-d');
    $daysRun = max(1, (int) floor((time() - strtotime($first)) / 86400) + 1);
    $stats = [
        'updated'      => gmdate('Y-m-d\TH:i\Z'),
        'gain'         => (float) ($acc['gain'] ?? 0),
        'profitFactor' => (float) ($acc['profitFactor'] ?? 0),
        'drawdown'     => (float) ($acc['drawdown'] ?? 0),
        'openPct'      => ((float) ($acc['balance'] ?? 0)) > 0 ? round((((float) ($acc['equity'] ?? 0)) - (float) $acc['balance']) * 100 / (float) $acc['balance'], 2) : 0,
        'winRate'      => $allCount ? round($wins * 100 / $allCount, 1) : 0,
        'trades'       => $allCount,
        'avgWin'       => $winP ? round(array_sum($winP) / count($winP), 2) : 0,
        'avgLoss'      => $lossP ? round(array_sum($lossP) / count($lossP), 2) : 0,
        'bestTrade'    => $winP ? max($winP) : 0,
        'since'        => $first,
        'days'         => $daysRun,
        'perDay'       => round($allCount / $daysRun, 1),
        'check'        => $check,
    ];
    $sf = dirname(__DIR__) . '/data/stats.json';
    file_put_contents($sf . '.tmp', json_encode($stats));
    rename($sf . '.tmp', $sf);
    echo "ok: stats\n";
}

// Daily cumulative gain for the period calculator: data/performance.json
$perfFile = dirname(__DIR__) . '/data/performance.json';
$r = mfx_api('get-daily-gain.json', [
    'session' => $session,
    'id'      => (int) $cfg['account_id'],
    'start'   => gmdate('Y-m-d', strtotime('-3 years')),
    'end'     => gmdate('Y-m-d'),
]);
if (!$r || !empty($r['error']) || !isset($r['dailyGain'])) {
    fwrite(STDERR, "could not read daily gain\n");
    exit(1);
}
$days = [];
foreach ($r['dailyGain'] as $item) {
    $rows = isset($item['date']) ? [$item] : (array) $item; // API wraps each day in an array
    foreach ($rows as $d) {
        $dt = DateTime::createFromFormat('m/d/Y', $d['date'] ?? '', new DateTimeZone('UTC'));
        if (!$dt) continue;
        $days[$dt->format('Y-m-d')] = round((float) ($d['value'] ?? 0), 2);
    }
}
ksort($days);
$out = [];
foreach ($days as $d => $g) $out[] = ['d' => $d, 'g' => $g];
$tmp = $perfFile . '.tmp';
file_put_contents($tmp, json_encode(['updated' => gmdate('Y-m-d\TH:i\Z'), 'days' => $out], JSON_UNESCAPED_SLASHES));
rename($tmp, $perfFile);
echo 'ok: ' . count($out) . " days\n";
