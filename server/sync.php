<?php
// Wendling FX: keeps the server in step with the GitHub repo wendlingfx/content (branch main).
// Reads server/manifest.json ({"repo path": "path under public_html"}) and rewrites any file that changed.
// Never touches config files with keys (they are not in the repo). Backups go to private/backup/.
$root = dirname(__DIR__);
$raw  = 'https://raw.githubusercontent.com/wendlingfx/content/main/';
function get(string $u): ?string {
    $ch = curl_init($u . '?t=' . time());
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_FOLLOWLOCATION => true, CURLOPT_TIMEOUT => 60, CURLOPT_USERAGENT => 'WendlingFX-sync']);
    $b = curl_exec($ch); $c = curl_getinfo($ch, CURLINFO_HTTP_CODE); curl_close($ch);
    return ($b !== false && $c === 200) ? $b : null;
}
$man = json_decode((string) get($raw . 'server/manifest.json'), true);
if (!is_array($man)) { echo "no manifest\n"; exit(1); }
$log = [];
foreach ($man as $src => $dst) {
    $dst = ltrim((string) $dst, '/');
    if (strpos($dst, '..') !== false || preg_match('/(config|buffer|telegram|ctrader)\.php$/', $dst)) continue; // never overwrite key files
    $body = get($raw . $src);
    if ($body === null || strlen($body) < 200) { $log[] = "$src: download failed"; continue; }
    if (substr($dst, -4) === '.php' && strpos($body, '<?php') !== 0) { $log[] = "$src: not php"; continue; }
    $path = $root . '/' . $dst;
    if (is_file($path) && hash_file('sha256', $path) === hash('sha256', $body)) continue;
    if (!is_dir($root . '/private/backup')) mkdir($root . '/private/backup', 0755, true);
    if (is_file($path)) copy($path, $root . '/private/backup/' . str_replace('/', '_', $dst) . '.' . gmdate('YmdHis'));
    file_put_contents($path . '.tmp', $body); rename($path . '.tmp', $path);
    $log[] = "$dst updated";
}
@file_put_contents($root . '/data/sync-status.json', json_encode(['checked' => gmdate('Y-m-d\TH:i\Z'), 'log' => $log]));
echo $log ? implode("\n", $log) . "\n" : "in step\n";
