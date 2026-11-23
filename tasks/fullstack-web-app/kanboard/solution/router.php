<?php
// Router of PHP's built-in web server in place of the official Docker image's nginx rules: only the front
// controllers run PHP, source code and private data are never served, other files are served as they are, and
// every other path goes to the front controller (URL rewriting). The deployment does not hand out or replace its
// database file: the About page's database download, upload and optimization are not available.
$root = __DIR__ . '/kanboard';
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$path = is_string($path) ? rawurldecode($path) : '/';
$script = '/index.php';
$database = strcasecmp((string) ($_GET['controller'] ?? ''), 'ConfigController') === 0
    && in_array(strtolower((string) ($_GET['action'] ?? '')), ['downloaddb', 'uploaddb', 'saveuploadeddb', 'optimizedb'], true);
if (preg_match('#^/(index|jsonrpc|healthcheck)\.php(/|$)#', $path, $match) && !$database) {
    $script = '/' . $match[1] . '.php';
} elseif ($database || preg_match('#^/(app|libs|vendor|data)/#', $path) || $path === '/cli' || preg_match('#\.php$#', $path)
    || preg_match('#\.(log|sqlite)$#i', $path) || str_contains($path, '/.')) {
    http_response_code(404);
    header('Content-Type: text/html');
    echo "<html>\r\n<head><title>404 Not Found</title></head>\r\n<body>\r\n<center><h1>404 Not Found</h1></center>\r\n</body>\r\n</html>\r\n";
    return true;
} elseif ($path !== '/') {
    $file = realpath($root . $path);
    if ($file !== false && str_starts_with($file, $root . '/') && is_file($file)) {
        return false;
    }
}
$_SERVER['SCRIPT_NAME'] = $_SERVER['PHP_SELF'] = $script;
$_SERVER['SCRIPT_FILENAME'] = $root . $script;
chdir($root);
require $root . $script;
