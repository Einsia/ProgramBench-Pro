<?php
// Bootstrap of a fresh data directory, run once before the web server starts: Kanboard's own schema migrations
// (which create the default administrator admin with the password admin) and the deployment's fixed application
// API token and webhook token in place of the random ones a new installation draws.
if (PHP_SAPI !== 'cli') {
    exit(1);
}
require __DIR__ . '/kanboard/app/common.php';
$container['configModel']->save(array(
    'api_token' => '9c5f44bb170a8f12f4c83369f3e0e68ca40fe1d3fec515cbfe067076cfff',
    'webhook_token' => 'e697933b51bbe13cb78af51a5d83e81060f4d8a8bd1ebbf6f150ebecd78c',
));
touch(DATA_DIR . DIRECTORY_SEPARATOR . 'baseline.ready');
