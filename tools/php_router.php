<?php
/**
 * Router for `php -S` — serves MediaWiki from ../mediawiki.
 */
$root = dirname( __DIR__ ) . DIRECTORY_SEPARATOR . 'mediawiki';
$uri = urldecode( parse_url( $_SERVER['REQUEST_URI'], PHP_URL_PATH ) ?? '/' );

$file = $root . str_replace( '/', DIRECTORY_SEPARATOR, $uri );
$ext = strtolower( pathinfo( $file, PATHINFO_EXTENSION ) );

// Serve static assets only (never execute via readfile)
$static = [
	'css' => 'text/css',
	'js' => 'application/javascript',
	'png' => 'image/png',
	'jpg' => 'image/jpeg',
	'jpeg' => 'image/jpeg',
	'gif' => 'image/gif',
	'svg' => 'image/svg+xml',
	'ico' => 'image/x-icon',
	'woff' => 'font/woff',
	'woff2' => 'font/woff2',
	'map' => 'application/json',
	'json' => 'application/json',
	'txt' => 'text/plain',
];

if ( $uri !== '/' && is_file( $file ) && isset( $static[$ext] ) ) {
	header( 'Content-Type: ' . $static[$ext] );
	readfile( $file );
	return true;
}

chdir( $root );
require $root . DIRECTORY_SEPARATOR . 'index.php';
