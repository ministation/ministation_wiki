<?php
/**
 * Router for `php -S` — serves MediaWiki from ../mediawiki.
 *
 * Critical: ResourceLoader CSS/JS come from load.php (not index.php).
 * Without routing .php entry points correctly, skins look unstyled.
 */
$root = dirname( __DIR__ ) . DIRECTORY_SEPARATOR . 'mediawiki';
$uri = urldecode( parse_url( $_SERVER['REQUEST_URI'], PHP_URL_PATH ) ?? '/' );

// Normalize and reject path traversal
$uri = '/' . ltrim( str_replace( '\\', '/', $uri ), '/' );
if ( str_contains( $uri, '..' ) ) {
	http_response_code( 400 );
	echo "Bad request";
	return true;
}

$file = $root . str_replace( '/', DIRECTORY_SEPARATOR, $uri );
$ext = strtolower( pathinfo( $file, PATHINFO_EXTENSION ) );

// MediaWiki PHP entry points (ResourceLoader, API, etc.)
$entryPoints = [
	'index.php',
	'load.php',
	'api.php',
	'rest.php',
	'img_auth.php',
	'opensearch_desc.php',
	'thumb.php',
	'thumb_handler.php',
	'includes/ajax/ajax.js', // legacy no-op if present
];

$base = basename( $uri );
if ( $ext === 'php' ) {
	$target = is_file( $file ) ? $file : null;
	// /w/load.php style with script path prefix
	if ( $target === null && in_array( $base, $entryPoints, true ) ) {
		$candidate = $root . DIRECTORY_SEPARATOR . $base;
		if ( is_file( $candidate ) ) {
			$target = $candidate;
		}
	}
	if ( $target !== null ) {
		chdir( $root );
		// php -S leaves PATH_INFO empty; MediaWiki expects SCRIPT_NAME
		$_SERVER['SCRIPT_FILENAME'] = $target;
		$_SERVER['SCRIPT_NAME'] = '/' . basename( $target );
		require $target;
		return true;
	}
}

// Static assets under mediawiki/ (skins, resources, extensions, …)
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
	'less' => 'text/plain',
	'wasm' => 'application/wasm',
];

if ( $uri !== '/' && is_file( $file ) && isset( $static[$ext] ) ) {
	header( 'Content-Type: ' . $static[$ext] );
	header( 'Content-Length: ' . (string)filesize( $file ) );
	readfile( $file );
	return true;
}

// Pretty URLs / default → index.php (MediaWiki handles title= from QUERY_STRING)
chdir( $root );
$_SERVER['SCRIPT_FILENAME'] = $root . DIRECTORY_SEPARATOR . 'index.php';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require $root . DIRECTORY_SEPARATOR . 'index.php';
return true;
