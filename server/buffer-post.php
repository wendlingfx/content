<?php
// Wendling FX: sends queued videos to TikTok through the Buffer API.
// Queues: private/post-queue.json (local, keeps its own status) and queue.json in the
// GitHub repo wendlingfx/content (remote; status kept in private/post-state.json).
// Remote videos are copied from the repo's media/ into public_html/media/ before sending.
// Run by cron: php /home/<user>/domains/wendlingfx.com/public_html/private/buffer-post.php

$key        = (string) ((require __DIR__ . '/buffer.php')['key'] ?? '');
$queueFile  = __DIR__ . '/post-queue.json';
$statusFile = __DIR__ . '/buffer-status.json';
$chanFile   = __DIR__ . '/.buffer-channel';
$mediaBase  = 'https://wendlingfx.com/media/';
$mediaDir   = dirname(__DIR__) . '/media/';
$stateFile  = __DIR__ . '/post-state.json';
$repoRaw    = 'https://raw.githubusercontent.com/wendlingfx/content/main/';

function http_get(string $url, int $timeout = 120): ?string {
    $ch = curl_init($url);
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_FOLLOWLOCATION => true, CURLOPT_TIMEOUT => $timeout, CURLOPT_USERAGENT => 'WendlingFX/1.0']);
    $raw = curl_exec($ch); $code = curl_getinfo($ch, CURLINFO_HTTP_CODE); curl_close($ch);
    return ($raw !== false && $code === 200) ? $raw : null;
}

function status_write(string $f, array $s): void {
    $s['checked'] = gmdate('Y-m-d\TH:i\Z');
    file_put_contents($f, json_encode($s, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
}

function gql(string $key, string $query): ?array {
    $ch = curl_init('https://api.buffer.com');
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 60,
        CURLOPT_POST           => true,
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json', 'Authorization: Bearer ' . $key],
        CURLOPT_POSTFIELDS     => json_encode(['query' => $query]),
    ]);
    $raw  = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($raw === false) return ['_error' => 'no response'];
    $d = json_decode($raw, true);
    if (!is_array($d)) return ['_error' => 'http ' . $code . ': ' . substr($raw, 0, 300)];
    if ($code >= 400 && empty($d['errors'])) $d['_error'] = 'http ' . $code;
    return $d;
}

function s(string $v): string { return json_encode($v, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE); }

if ($key === '') { status_write($statusFile, ['ok' => false, 'error' => 'buffer.php has no key']); exit(1); }

// 1. Find the TikTok channel (cached).
$channelId = is_file($chanFile) ? trim((string) file_get_contents($chanFile)) : '';
if ($channelId === '') {
    $o = gql($key, '{ account { organizations { id name } } }');
    $orgs = $o['data']['account']['organizations'] ?? [];
    $found = [];
    foreach ($orgs as $org) {
        $c = gql($key, '{ channels(input: { organizationId: ' . s((string) $org['id']) . ' }) { id name displayName service isQueuePaused } }');
        foreach (($c['data']['channels'] ?? []) as $ch) {
            $found[] = ['service' => $ch['service'], 'name' => $ch['displayName'] ?: $ch['name'], 'paused' => $ch['isQueuePaused']];
            if (strtolower((string) $ch['service']) === 'tiktok' && $channelId === '') $channelId = (string) $ch['id'];
        }
    }
    if ($channelId === '') {
        status_write($statusFile, ['ok' => false, 'error' => 'no TikTok channel found', 'api' => $o['errors'][0]['message'] ?? ($o['_error'] ?? null), 'channels' => $found]);
        exit(1);
    }
    file_put_contents($chanFile, $channelId);
    status_write($statusFile, ['ok' => true, 'channels' => $found]);
}

// 2. Build the list: local queue plus the GitHub queue.
$queue = is_file($queueFile) ? (json_decode((string) file_get_contents($queueFile), true) ?: []) : [];
$state = is_file($stateFile) ? (json_decode((string) file_get_contents($stateFile), true) ?: []) : [];
$localIds = array_column($queue, 'id');
$remoteRaw = http_get($repoRaw . 'queue.json?t=' . time(), 30);
$remote = $remoteRaw !== null ? (json_decode($remoteRaw, true) ?: []) : [];
$items = [];
foreach ($queue as $i => $item) $items[] = ['src' => 'local', 'i' => $i, 'item' => $item, 'status' => $item['status'] ?? ''];
foreach ($remote as $item) {
    if (empty($item['id']) || empty($item['file']) || in_array($item['id'], $localIds, true)) continue;
    $items[] = ['src' => 'remote', 'item' => $item, 'status' => $state[$item['id']]['status'] ?? 'pending'];
}

// 3. Send pending items.
$changed = false; $stateChanged = false; $log = [];
foreach ($items as $it) {
    $item = $it['item'];
    if ($it['status'] !== 'pending') continue;
    $file = basename((string) $item['file']);
    if ($it['src'] === 'remote' && !is_file($mediaDir . $file)) {
        $bin = http_get($repoRaw . 'media/' . rawurlencode($file), 300);
        if ($bin === null || strlen($bin) < 50000 || strpos(substr($bin, 0, 16), 'ftyp') === false) { $log[] = $item['id'] . ': video not downloaded'; continue; }
        if (!is_dir($mediaDir)) mkdir($mediaDir, 0755, true);
        file_put_contents($mediaDir . $file . '.tmp', $bin);
        rename($mediaDir . $file . '.tmp', $mediaDir . $file);
    }
    if (!is_file($mediaDir . $file)) { $log[] = $item['id'] . ': file missing'; continue; }
    $due = isset($item['due']) ? strtotime($item['due']) : 0;
    if ($it['src'] === 'remote' && $due && $due > time() + 7 * 86400) { $log[] = $item['id'] . ': later'; continue; }
    $sched = ($due && $due > time() + 600)
        ? 'mode: customScheduled, dueAt: ' . s(gmdate('Y-m-d\TH:i:s.000\Z', $due))
        : 'mode: addToQueue';
    $q = 'mutation { createPost(input: { text: ' . s((string) $item['text']) . ', channelId: ' . s($channelId)
       . ', schedulingType: automatic, ' . $sched
       . ', assets: [{ video: { url: ' . s($mediaBase . rawurlencode($file)) . ', metadata: { thumbnailOffset: 1000 } } }] })'
       . ' { ... on PostActionSuccess { post { id } } ... on MutationError { message } } }';
    $r = gql($key, $q);
    $res = $r['data']['createPost'] ?? null;
    $ok = !empty($res['post']['id']);
    $rec = $ok ? ['status' => 'sent', 'bufferId' => $res['post']['id'], 'sentAt' => gmdate('Y-m-d\TH:i\Z')]
               : ['status' => 'error', 'error' => $res['message'] ?? ($r['errors'][0]['message'] ?? ($r['_error'] ?? 'unknown'))];
    if ($it['src'] === 'local') { $queue[$it['i']] = array_merge($queue[$it['i']], $rec); $changed = true; }
    else { $state[$item['id']] = $rec; $stateChanged = true; }
    $log[] = $item['id'] . ': ' . $rec['status'];
}
if ($changed) file_put_contents($queueFile, json_encode($queue, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));
if ($stateChanged) file_put_contents($stateFile, json_encode($state, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
// Public status for checking from outside (no secrets): data/post-status.json
$pub = ['checked' => gmdate('Y-m-d\TH:i\Z'), 'remoteQueue' => $remoteRaw !== null, 'log' => $log, 'state' => $state];
@file_put_contents(dirname(__DIR__) . '/data/post-status.json', json_encode($pub, JSON_UNESCAPED_SLASHES));
echo 'ok: channel set, ' . ($log ? implode('; ', $log) : 'nothing pending') . "\n";
