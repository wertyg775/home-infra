<?php
$CONFIG = [
    'dbhost' => 'db:3306',
    'datadirectory' => '/var/www/html/data',
    'apps_paths' => [
        [
            'path' => '/var/www/html/apps',
            'url' => '/apps',
            'writable' => false,
        ],
        [
            'path' => '/var/www/html/custom_apps',
            'url' => '/custom_apps',
            'writable' => true,
        ],
    ],
    'memcache.local' => '\\OC\\Memcache\\APCu',
    'memcache.distributed' => '\\OC\\Memcache\\Redis',
    'memcache.locking' => '\\OC\\Memcache\\Redis',
    'redis' => [
        'host' => 'redis',
        'port' => 6379,
    ],
    'trusted_proxies' => ['172.30.0.1'],
    'overwritehost' => 'cloud.home.arpa',
    'overwriteprotocol' => 'https',
    'overwrite.cli.url' => 'https://cloud.home.arpa',
];
