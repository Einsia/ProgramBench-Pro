<?php
// Router of PHP's built-in web server, in place of the URL rewriting of a regular web server: an existing file under
// public/ is served as it is, every other path goes to Grocy's front controller.
$public = __DIR__ . '/grocy/public';
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$file = is_string($path) && $path !== '/' ? realpath($public . $path) : false;
if ($file !== false && str_starts_with($file, $public . '/') && is_file($file))
{
	return false;
}
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SCRIPT_FILENAME'] = $public . '/index.php';
require $public . '/index.php';
