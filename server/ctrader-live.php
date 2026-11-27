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
// A new token pasted into ctrader.php wins over the refreshed copy kept in ctrader-tokens.json.
$cfgHash = sha1(trim((string) ($cfg['access_token'] ?? '')));
if (($tok['cfg'] ?? '') !== $cfgHash) $tok = [];
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

// Find the account id for the login number. private/account.json (synced from the repo, no secrets)
// overrides the login in ctrader.php, so the project can move to another account without touching the keys.
$ovFile = __DIR__ . '/account.json';
$ov = is_file($ovFile) ? (json_decode((string) file_get_contents($ovFile), true) ?: []) : [];
$want = trim((string) ($ov['ctrader_login'] ?? '')) ?: trim((string) ($cfg['account'] ?? ''));
$accId = (int) ($tok['account_id'] ?? 0); $login = (string) ($tok['login'] ?? ''); $switched = false;
if ($accId && $want !== '' && $login !== $want) {
    $switched = $login !== '' || trim((string) ($ov['ctrader_login'] ?? '')) !== trim((string) ($cfg['account'] ?? ''));
    $accId = 0;
}
if (!$accId) {
    $r = call($s, 2149, ['accessToken' => $access], 2150);
    if (isset($r['_error']) && $refresh !== '') {
        $rr = call($s, 2173, ['refreshToken' => $refresh], 2174);
        if (isset($rr['_error'])) fail($outFile, 'refresh: ' . $rr['_error']);
        $access = $rr['accessToken']; $refresh = $rr['refreshToken'] ?? $refresh;
        $r = call($s, 2149, ['accessToken' => $access], 2150);
    }
    if (isset($r['_error'])) fail($outFile, 'account list: ' . $r['_error']);
    $live = []; $all = $r['ctidTraderAccount'] ?? [];
    foreach ($all as $a) {
        if (!empty($a['isLive'])) $live[(int) $a['ctidTraderAccountId']] = (string) ($a['traderLogin'] ?? '');
        if ($want !== '' && (string) ($a['traderLogin'] ?? '') === $want) { $accId = (int) $a['ctidTraderAccountId']; $login = $want; }
    }
    if (!$accId && $want === '' && count($live) === 1) { $accId = array_key_first($live); $login = $live[$accId]; } // the only live account
    if (!$accId) fail($outFile, $want === '' ? count($live) . ' live accounts on this token: fill "account" with the login number'
        : 'account ' . $want . ' not found for this token (' . count($all) . ' accounts authorised): authorise it in the cTrader app');
}

$r = call($s, 2102, ['ctidTraderAccountId' => $accId, 'accessToken' => $access], 2103);
if (isset($r['_error']) && $refresh !== '') {
    $rr = call($s, 2173, ['refreshToken' => $refresh], 2174);
    if (isset($rr['_error'])) fail($outFile, 'refresh: ' . $rr['_error']);
    $access = $rr['accessToken']; $refresh = $rr['refreshToken'] ?? $refresh;
    $r = call($s, 2102, ['ctidTraderAccountId' => $accId, 'accessToken' => $access], 2103);
}
if (isset($r['_error'])) fail($outFile, 'account auth: ' . $r['_error']);

file_put_contents($tokFile, json_encode(['access_token' => $access, 'refresh_token' => $refresh, 'account_id' => $accId, 'login' => $login ?: $want, 'cfg' => $cfgHash]));
if ($switched) { // new account: forget the running posts and symbol ids of the old one
    foreach (['running-posts.json', 'ctrader-symbols.json'] as $f) if (is_file(__DIR__ . '/' . $f)) @rename(__DIR__ . '/' . $f, __DIR__ . '/' . $f . '.old');
}
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

// Telegram "running" posts: a position open for RUN_MIN minutes with RUN_PCT % of the account or more in profit is posted
// once (symbol, side and % only: no entry price, stop or target). When it closes, the result is posted as a reply.
const RUN_MIN = 30; const RUN_PCT = 1.0;
$pauseCfg = is_file(__DIR__ . '/pause.json') ? (json_decode((string) file_get_contents(__DIR__ . '/pause.json'), true) ?: []) : [];
$tgCfgFile = __DIR__ . '/telegram.php';
$runFile = __DIR__ . '/running-posts.json';
if (empty($pauseCfg['paused']) && is_file($tgCfgFile) && $balance > 0) {
    $tgc = require $tgCfgFile; $tgTok = trim((string) ($tgc['token'] ?? '')); $tgChat = (string) ($tgc['chat'] ?? '@wendlingfx');
    $run = is_file($runFile) ? (json_decode((string) file_get_contents($runFile), true) ?: []) : [];
    $symFile = __DIR__ . '/ctrader-symbols.json';
    $symN = is_file($symFile) ? (json_decode((string) file_get_contents($symFile), true) ?: []) : [];
    $pnl = [];
    foreach (($u['positionUnrealizedPnL'] ?? []) as $p) $pnl[(string) $p['positionId']] = (float) ($p['netUnrealizedPnL'] ?? 0) / (10 ** ($ud ?? $md));
    $nice = ['XAUUSD' => 'Gold', 'XAGUSD' => 'Silver', 'BTCUSD' => 'Bitcoin', 'US30' => 'Dow', 'NAS100' => 'Nasdaq', 'GER40' => 'DAX'];
    $tgsend = function (array $f) use ($tgTok) {
        $ch = curl_init('https://api.telegram.org/bot' . $tgTok . '/sendMessage');
        curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20, CURLOPT_POST => true, CURLOPT_POSTFIELDS => $f]);
        $r = json_decode((string) curl_exec($ch), true); curl_close($ch); return is_array($r) ? $r : [];
    };
    $seen = [];
    foreach (($rc['position'] ?? []) as $pos) {
        $pid = (string) $pos['positionId']; $seen[$pid] = true; $td = $pos['tradeData'] ?? [];
        if (isset($run[$pid]) || $tgTok === '') continue;
        $mins = (time() * 1000 - (int) ($td['openTimestamp'] ?? 0)) / 60000;
        $pct = ($pnl[$pid] ?? 0) * 100 / $balance;
        if ($mins < RUN_MIN || $pct < RUN_PCT) continue;
        $sid = (string) ($td['symbolId'] ?? '');
        if (!isset($symN[$sid])) {
            $l = call($s, 2114, ['ctidTraderAccountId' => $accId], 2115);
            foreach (($l['symbol'] ?? []) as $x) $symN[(string) $x['symbolId']] = $x['symbolName'] ?? '';
            file_put_contents($symFile, json_encode($symN));
        }
        $sym = $symN[$sid] ?? 'Trade'; $name = $nice[$sym] ?? $sym;
        $side = ((int) ($td['tradeSide'] ?? 1)) === 2 ? 'sell' : 'buy';
        $h = $mins >= 90 ? round($mins / 60, 1) . ' h' : round($mins) . ' min';
        $txt = "\u{1F7E2} $name $side running: +" . number_format($pct, 1) . "% of the account\nOpen for $h. Live update, not a signal.";
        $r = $tgsend(['chat_id' => $tgChat, 'text' => $txt]);
        $run[$pid] = ['msg' => $r['result']['message_id'] ?? null, 'at' => time(), 'name' => $name, 'side' => $side];
    }
    // Closed since the last run: post the final result as a reply to the running post.
    foreach ($run as $pid => $info) {
        if (isset($seen[$pid]) || !empty($info['closed'])) continue;
        $dl = call($s, 2133, ['ctidTraderAccountId' => $accId, 'fromTimestamp' => ($info['at'] - 3 * 86400) * 1000, 'toTimestamp' => (time() + 60) * 1000], 2134);
        $net = 0.0; $after = null; $found = false;
        foreach (($dl['deal'] ?? []) as $dd) {
            if ((string) ($dd['positionId'] ?? '') !== (string) $pid || empty($dd['closePositionDetail'])) continue;
            $cp = $dd['closePositionDetail']; $dg = (int) ($cp['moneyDigits'] ?? $md); $found = true;
            $net += ((float) ($cp['grossProfit'] ?? 0) + (float) ($cp['swap'] ?? 0) + (float) ($cp['commission'] ?? 0)) / (10 ** $dg);
            $after = (float) ($cp['balance'] ?? 0) / (10 ** $dg);
        }
        if (!$found) { if (time() - $info['at'] > 7 * 86400) $run[$pid]['closed'] = true; continue; }
        $before = $after !== null ? $after - $net : $balance - $net;
        $pc = $before > 0 ? $net * 100 / $before : 0;
        if ($tgTok !== '' && $info['msg']) $tgsend(['chat_id' => $tgChat, 'reply_to_message_id' => $info['msg'], 'text' => ($pc >= 0 ? "\u{2705} " : '') . $info['name'] . ' ' . $info['side'] . ' closed: ' . ($pc >= 0 ? '+' : '') . number_format($pc, 1) . '% of the account']);
        $run[$pid]['closed'] = true;
    }
    foreach ($run as $pid => $info) if (!empty($info['closed']) && time() - $info['at'] > 14 * 86400) unset($run[$pid]);
    file_put_contents($runFile, json_encode($run));
}
// New position alert (Telegram): one short post when a position opens on the live account.
// No symbol, side, price or size (the strategy is what people pay for); the result follows from telegram-post.php when it closes.
$seenFile = __DIR__ . '/open-seen.json';
$seenOpen = is_file($seenFile) ? (json_decode((string) file_get_contents($seenFile), true) ?: null) : null;
$nowIds = [];
foreach (($rc['position'] ?? []) as $pos) $nowIds[(string) $pos['positionId']] = (int) ($pos['tradeData']['openTimestamp'] ?? 0);
if ($seenOpen === null || ($seenOpen['login'] ?? '') !== $want) {
    $seenOpen = ['login' => $want, 'ids' => array_fill_keys(array_keys($nowIds), time())]; // first run on this account: no posts
} else {
    if (empty($pauseCfg['paused']) && is_file($tgCfgFile)) {
        $tgc2 = $tgc ?? (require $tgCfgFile); $tk2 = trim((string) ($tgc2['token'] ?? '')); $ch2 = (string) ($tgc2['chat'] ?? '@wendlingfx');
        foreach ($nowIds as $pid => $ot) {
            if (isset($seenOpen['ids'][$pid])) continue;
            $seenOpen['ids'][$pid] = time();
            if ($tk2 === '' || $ot <= 0 || time() * 1000 - $ot > 15 * 60000) continue; // only fresh opens
            $c = curl_init('https://api.telegram.org/bot' . $tk2 . '/sendMessage');
            curl_setopt_array($c, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20, CURLOPT_POST => true, CURLOPT_POSTFIELDS => [
                'chat_id' => $ch2, 'disable_web_page_preview' => 'true',
                'text' => "\u{1F535} New position just opened on the live account.\nThe result is posted here when it closes, in % of the account.\nCopy it automatically: https://wendlingfx.com/start/"]]);
            curl_exec($c); curl_close($c);
        }
    } else foreach ($nowIds as $pid => $ot) $seenOpen['ids'][$pid] = $seenOpen['ids'][$pid] ?? time();
}
foreach ($seenOpen['ids'] as $pid => $at) if (!isset($nowIds[$pid]) && time() - $at > 30 * 86400) unset($seenOpen['ids'][$pid]);
file_put_contents($seenFile, json_encode($seenOpen));

// Closed trades straight from cTrader (every 10 min): private/ct-trades.json, read by update-trades.php so the
// site does not depend on Myfxbook. Each trade in % of the balance before it; no money values are stored here.
$ctFile = __DIR__ . '/ct-trades.json';
$ctOld = is_file($ctFile) ? (json_decode((string) file_get_contents($ctFile), true) ?: []) : [];
$startIso = trim((string) ($ov['start'] ?? ''));
if ($startIso !== '' && (($ctOld['login'] ?? '') !== $want || time() - (int) ($ctOld['at'] ?? 0) > 540)) {
    $from = strtotime($startIso) ?: (time() - 7 * 86400); $deals = []; $ok = true;
    for ($t0 = $from; $t0 < time() + 60; $t0 += 7 * 86400) {
        $dl = call($s, 2133, ['ctidTraderAccountId' => $accId, 'fromTimestamp' => $t0 * 1000, 'toTimestamp' => min($t0 + 7 * 86400, time() + 60) * 1000], 2134);
        if (isset($dl['_error'])) { $ok = false; break; }
        foreach (($dl['deal'] ?? []) as $dd) $deals[(string) $dd['dealId']] = $dd;
    }
    if ($ok) {
        $symFile2 = __DIR__ . '/ctrader-symbols.json';
        $symN2 = is_file($symFile2) ? (json_decode((string) file_get_contents($symFile2), true) ?: []) : [];
        $byPos = [];
        foreach ($deals as $dd) $byPos[(string) ($dd['positionId'] ?? '')][] = $dd;
        $trades = [];
        foreach ($byPos as $pid => $ds) {
            $comm = 0.0; $gross = 0.0; $after = null; $closeTs = 0; $side = ''; $sid = ''; $dg = $md;
            foreach ($ds as $dd) {
                $cp = $dd['closePositionDetail'] ?? null;
                $dg = (int) ($cp['moneyDigits'] ?? ($dd['moneyDigits'] ?? $md));
                $comm += (float) ($dd['commission'] ?? 0) / (10 ** $dg);
                $sid = (string) ($dd['symbolId'] ?? $sid);
                if ($cp) {
                    $gross += ((float) ($cp['grossProfit'] ?? 0) + (float) ($cp['swap'] ?? 0)) / (10 ** $dg);
                    $ts = (int) ($dd['executionTimestamp'] ?? 0);
                    if ($ts >= $closeTs) { $closeTs = $ts; $after = (float) ($cp['balance'] ?? 0) / (10 ** $dg); }
                    $side = ((int) ($dd['tradeSide'] ?? 1)) === 1 ? 'Sell' : 'Buy'; // closing deal is opposite to the position
                }
            }
            if ($after === null || $closeTs <= 0) continue; // still open
            if (!isset($symN2[$sid])) {
                $l2 = call($s, 2114, ['ctidTraderAccountId' => $accId], 2115);
                foreach (($l2['symbol'] ?? []) as $x) $symN2[(string) $x['symbolId']] = $x['symbolName'] ?? '';
                file_put_contents($symFile2, json_encode($symN2));
            }
            $net = $gross + $comm; $before = $after - $net;
            $pct = $before > 0 ? round($net * 100 / $before, 2) : 0.0;
            $trades[] = ['closed' => gmdate('Y-m-d\TH:i\Z', intdiv($closeTs, 1000)), 'symbol' => $symN2[$sid] ?? '', 'side' => $side, 'result' => $pct, 'pct' => $pct, 'pid' => $pid];
        }
        usort($trades, fn($a, $b) => strcmp($a['closed'], $b['closed']));
        file_put_contents($ctFile . '.tmp', json_encode(['login' => $want, 'at' => time(), 'start' => $startIso, 'trades' => $trades]));
        rename($ctFile . '.tmp', $ctFile);
    }
}

// Once an hour: daily bars of the main markets for the weekly market notes (public prices only): data/market.json
$mf = dirname(__DIR__) . '/data/market.json';
if (!is_file($mf) || time() - filemtime($mf) > 3300) {
    $want = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'US30', 'NAS100', 'GER40', 'BTCUSD', 'XTIUSD'];
    $l = call($s, 2114, ['ctidTraderAccountId' => $accId], 2115); $ids = [];
    foreach (($l['symbol'] ?? []) as $x) if (in_array($x['symbolName'] ?? '', $want, true)) $ids[$x['symbolName']] = (int) $x['symbolId'];
    $mk = [];
    foreach ($ids as $name => $sid) {
        $q = call($s, 2137, ['ctidTraderAccountId' => $accId, 'symbolId' => $sid, 'period' => 12, 'fromTimestamp' => (time() - 40 * 86400) * 1000, 'toTimestamp' => (time() + 86400) * 1000], 2138);
        $bars = [];
        foreach (($q['trendbar'] ?? []) as $b) { $lo = (int) ($b['low'] ?? 0); $bars[] = ['d' => gmdate('Y-m-d', (int) $b['utcTimestampInMinutes'] * 60 + 7200), 'o' => ($lo + (int) ($b['deltaOpen'] ?? 0)) / 1e5, 'h' => ($lo + (int) ($b['deltaHigh'] ?? 0)) / 1e5, 'l' => $lo / 1e5, 'c' => ($lo + (int) ($b['deltaClose'] ?? 0)) / 1e5]; }
        if ($bars) $mk[$name] = array_slice($bars, -30);
    }
    if ($mk) { file_put_contents($mf . '.tmp', json_encode(['updated' => gmdate('Y-m-d\TH:i\Z'), 'daily' => $mk])); rename($mf . '.tmp', $mf); }
    $h1 = [];
    foreach (['XAUUSD', 'EURUSD', 'BTCUSD'] as $name) {
        if (empty($ids[$name])) continue;
        $q = call($s, 2137, ['ctidTraderAccountId' => $accId, 'symbolId' => $ids[$name], 'period' => 9, 'fromTimestamp' => (time() - 16 * 86400) * 1000, 'toTimestamp' => time() * 1000], 2138);
        $bars = [];
        foreach (($q['trendbar'] ?? []) as $b) { $lo = (int) ($b['low'] ?? 0); $bars[] = [(int) $b['utcTimestampInMinutes'], ($lo + (int) ($b['deltaOpen'] ?? 0)) / 1e5, ($lo + (int) ($b['deltaHigh'] ?? 0)) / 1e5, $lo / 1e5, ($lo + (int) ($b['deltaClose'] ?? 0)) / 1e5]; }
        if ($bars) $h1[$name] = $bars;
    }
    if ($h1) { $hf = dirname(__DIR__) . '/data/market-h1.json'; file_put_contents($hf . '.tmp', json_encode(['updated' => gmdate('Y-m-d\TH:i\Z'), 'h1' => $h1])); rename($hf . '.tmp', $hf); }
}
fclose($s);

// Copy watch (private, read by telegram-post.php): balance, open positions and when the account last moved.
$cwFile = __DIR__ . '/copy-state.json';
$cw = is_file($cwFile) ? (json_decode((string) file_get_contents($cwFile), true) ?: []) : [];
$oldest = 0;
foreach (($rc['position'] ?? []) as $p) { $ot = (int) ($p['tradeData']['openTimestamp'] ?? 0); if ($ot > 0) $oldest = max($oldest, (int) round((time() * 1000 - $ot) / 60000)); }
if ($open > 0 || (isset($cw['balance']) && abs((float) $cw['balance'] - $balance) > 0.005)) $cw['activityAt'] = time();
if (($cw['day'] ?? '') !== gmdate('Y-m-d')) { $cw['day'] = gmdate('Y-m-d'); $cw['dayStart'] = $balance; }
$cw = ['login' => $want, 'balance' => $balance, 'equity' => $balance + $float, 'open' => $open, 'oldestMin' => $oldest, 'updated' => time()] + $cw;
$cw['balance'] = $balance; $cw['equity'] = $balance + $float; $cw['open'] = $open; $cw['oldestMin'] = $oldest; $cw['updated'] = time(); $cw['login'] = $want;
file_put_contents($cwFile, json_encode($cw));

out($outFile, ['ok' => true, 'open' => $open, 'floatingPct' => $balance > 0 ? round($float * 100 / $balance, 2) : 0]);
echo "ok: $open open\n";
