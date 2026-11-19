<?php
// Wendling FX: reads the open positions from the cTrader Open API (read only) and writes
// ../data/live.json = {updated, open, floatingPct, ok}. No symbols, prices or sizes are published.
// Config: private/ctrader.php returns ['client_id','client_secret','access_token','refresh_token','account'].
// Refreshed tokens are kept in private/ctrader-tokens.json. Run by cron every minute.

$cfg     = require __DIR__ . '/ctrader.php';
$tokFile = __DIR__ . '/ctrader-tokens.json';
$outFile = dirname(__DIR__) . '/data/live.json';
$host    = 'live.ctraderapi.com';

function out(string $f, array $d): void {
    $d['updated'] = gmdate('Y-m-d\TH:i:s\Z');
    file_put_contents($f . '.tmp', json_encode($d)); rename($f . '.tmp', $f);
}
function fail(string $f, string $why): void { out($f, ['ok' => false, 'error' => $why]); fwrite(STDERR, $why . "\n"); exit(1); }

$missing = [];
foreach (['client_id', 'client_secret', 'access_token'] as $k)
    if (trim((string) ($cfg[$k] ?? '')) === '') $missing[] = $k;

$tok = is_file($tokFile) ? (json_decode((string) file_get_contents($tokFile), true) ?: []) : [];
$access  = $tok['access_token']  ?? trim($cfg['access_token']);
$refresh = $tok['refresh_token'] ?? trim((string) ($cfg['refresh_token'] ?? ''));

// ---- minimal WebSocket client (TLS, text frames) ----
function ws_open(string $host) {
    $ctx = stream_context_create(['ssl' => ['verify_peer' => true, 'verify_peer_name' => true, 'SNI_enabled' => true]]);
    $s = @stream_socket_client("ssl://$host:5036", $en, $es, 20, STREAM_CLIENT_CONNECT, $ctx);
    if (!$s) return null;
    stream_set_timeout($s, 20);
    $key = base64_encode(random_bytes(16));
    fwrite($s, "GET / HTTP/1.1\r\nHost: $host:5036\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: $key\r\nSec-WebSocket-Version: 13\r\n\r\n");
    $head = '';
    while (!feof($s) && strpos($head, "\r\n\r\n") === false) { $c = fgets($s); if ($c === false) break; $head .= $c; }
    return strpos($head, ' 101 ') !== false ? $s : null;
}
function ws_send($s, string $txt): void {
    $len = strlen($txt); $mask = random_bytes(4);
    $h = chr(0x81);
    if ($len < 126) $h .= chr(0x80 | $len);
    elseif ($len < 65536) $h .= chr(0x80 | 126) . pack('n', $len);
    else $h .= chr(0x80 | 127) . pack('J', $len);
    $m = ''; for ($i = 0; $i < $len; $i++) $m .= $txt[$i] ^ $mask[$i % 4];
    fwrite($s, $h . $mask . $m);
}
function ws_read_exact($s, int $n): ?string {
    $b = ''; while (strlen($b) < $n) { $c = fread($s, $n - strlen($b)); if ($c === false || $c === '') { if (feof($s) || stream_get_meta_data($s)['timed_out']) return null; continue; } $b .= $c; } return $b;
}
function ws_recv($s): ?string {
    $msg = '';
    while (true) {
        $h = ws_read_exact($s, 2); if ($h === null) return null;
        $fin = ord($h[0]) & 0x80; $op = ord($h[0]) & 0x0f; $len = ord($h[1]) & 0x7f;
        if ($len === 126) $len = unpack('n', ws_read_exact($s, 2))[1];
        elseif ($len === 127) $len = unpack('J', ws_read_exact($s, 8))[1];
        if (ord($h[1]) & 0x80) ws_read_exact($s, 4);
        $p = $len ? ws_read_exact($s, $len) : '';
        if ($p === null) return null;
        if ($op === 9) continue;            // ping
        if ($op === 8) return null;         // close
        $msg .= $p;
        if ($fin) return $msg;
    }
}
// Send a request and wait for the given response type (skips heartbeats and events).
function call($s, int $type, array $payload, int $want): array {
    static $n = 0; $id = 'w' . (++$n);
    ws_send($s, json_encode(['clientMsgId' => $id, 'payloadType' => $type, 'payload' => (object) $payload]));
    for ($i = 0; $i < 50; $i++) {
        $raw = ws_recv($s); if ($raw === null) return ['_error' => 'connection closed'];
        $m = json_decode($raw, true); if (!is_array($m)) continue;
        $pt = (int) ($m['payloadType'] ?? 0);
        if ($pt === $want) return $m['payload'] ?? [];
        if ($pt === 2142 || $pt === 50) return ['_error' => ($m['payload']['errorCode'] ?? 'error') . ': ' . ($m['payload']['description'] ?? '')];
    }
    return ['_error' => 'no answer'];
}

$s = ws_open($host);
if (!$s) fail($outFile, 'cannot connect to cTrader');
if ($missing) { // not configured yet: check the app keys if they are there, then stop
    $hasApp = !in_array('client_id', $missing, true) && !in_array('client_secret', $missing, true);
    $r = $hasApp ? call($s, 2100, ['clientId' => trim($cfg['client_id']), 'clientSecret' => trim($cfg['client_secret'])], 2101)
                 : call($s, 2100, ['clientId' => 'probe', 'clientSecret' => 'probe'], 2101);
    fail($outFile, 'config missing: ' . implode(', ', $missing) . ' | app keys: ' . ($hasApp ? (isset($r['_error']) ? 'REJECTED ' . $r['_error'] : 'OK') : 'not set'));
}

$r = call($s, 2100, ['clientId' => trim($cfg['client_id']), 'clientSecret' => trim($cfg['client_secret'])], 2101);
if (isset($r['_error'])) fail($outFile, 'app auth: ' . $r['_error']);

// Find the account id for the login number.
$accId = (int) ($tok['account_id'] ?? 0);
if (!$accId) {
    $r = call($s, 2149, ['accessToken' => $access], 2150);
    if (isset($r['_error']) && $refresh !== '') {
        $rr = call($s, 2173, ['refreshToken' => $refresh], 2174);
        if (isset($rr['_error'])) fail($outFile, 'refresh: ' . $rr['_error']);
        $access = $rr['accessToken']; $refresh = $rr['refreshToken'] ?? $refresh;
        $r = call($s, 2149, ['accessToken' => $access], 2150);
    }
    if (isset($r['_error'])) fail($outFile, 'account list: ' . $r['_error']);
    $want = trim((string) ($cfg['account'] ?? '')); $live = [];
    foreach (($r['ctidTraderAccount'] ?? []) as $a) {
        if (!empty($a['isLive'])) $live[] = (int) $a['ctidTraderAccountId'];
        if ($want !== '' && (string) ($a['traderLogin'] ?? '') === $want) $accId = (int) $a['ctidTraderAccountId'];
    }
    if (!$accId && $want === '' && count($live) === 1) $accId = $live[0]; // account left empty: the only live account
    if (!$accId) fail($outFile, $want === '' ? count($live) . ' live accounts on this token: fill "account" with the login number' : 'account not found for this token');
}

$r = call($s, 2102, ['ctidTraderAccountId' => $accId, 'accessToken' => $access], 2103);
if (isset($r['_error']) && $refresh !== '') {
    $rr = call($s, 2173, ['refreshToken' => $refresh], 2174);
    if (isset($rr['_error'])) fail($outFile, 'refresh: ' . $rr['_error']);
    $access = $rr['accessToken']; $refresh = $rr['refreshToken'] ?? $refresh;
    $r = call($s, 2102, ['ctidTraderAccountId' => $accId, 'accessToken' => $access], 2103);
}
if (isset($r['_error'])) fail($outFile, 'account auth: ' . $r['_error']);

file_put_contents($tokFile, json_encode(['access_token' => $access, 'refresh_token' => $refresh, 'account_id' => $accId]));
@chmod($tokFile, 0600);

$tr = call($s, 2121, ['ctidTraderAccountId' => $accId], 2122);
if (isset($tr['_error'])) fail($outFile, 'trader: ' . $tr['_error']);
$md = (int) ($tr['trader']['moneyDigits'] ?? 2);
$balance = (float) ($tr['trader']['balance'] ?? 0) / (10 ** $md);

$rc = call($s, 2124, ['ctidTraderAccountId' => $accId], 2125);
if (isset($rc['_error'])) fail($outFile, 'reconcile: ' . $rc['_error']);
$open = count($rc['position'] ?? []);

$float = 0.0;
if ($open > 0) {
    $u = call($s, 2187, ['ctidTraderAccountId' => $accId], 2188);
    if (isset($u['_error'])) fail($outFile, 'pnl: ' . $u['_error']);
    $ud = (int) ($u['moneyDigits'] ?? $md);
    foreach (($u['positionUnrealizedPnL'] ?? []) as $p) $float += (float) ($p['netUnrealizedPnL'] ?? 0) / (10 ** $ud);
}
fclose($s);

out($outFile, ['ok' => true, 'open' => $open, 'floatingPct' => $balance > 0 ? round($float * 100 / $balance, 2) : 0]);
echo "ok: $open open\n";
