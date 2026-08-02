<?php

namespace MediaWiki\Extension\SS14Sprites;

use MediaWiki\Parser\Parser;

class Hooks {
	public static function onParserFirstCallInit( Parser $parser ): void {
		$parser->setFunctionHook( 'sprite', [ self::class, 'renderSprite' ] );
	}

	/**
	 * {{#sprite:Objects/Weapons/Melee/knife.rsi/icon|scale=3|frame=0|dir=0}}
	 *
	 * @param Parser $parser
	 * @param string ...$args
	 * @return array
	 */
	public static function renderSprite( Parser $parser, ...$args ): array {
		$parser->getOutput()->updateCacheExpiry( 3600 );

		$parts = array_map( 'trim', $args );
		$parts = array_values( array_filter( $parts, static fn ( $p ) => $p !== '' ) );
		if ( !$parts ) {
			return [ '<span class="error">SS14Sprites: empty path</span>', 'noparse' => true, 'isHTML' => true ];
		}

		$target = array_shift( $parts );
		$opts = [ 'scale' => null, 'frame' => null, 'dir' => null, 'alt' => null, 'pixel' => '1' ];
		foreach ( $parts as $part ) {
			if ( str_contains( $part, '=' ) ) {
				[ $k, $v ] = array_map( 'trim', explode( '=', $part, 2 ) );
				$opts[ strtolower( $k ) ] = $v;
			}
		}

		$qs = [];
		if ( $opts['frame'] !== null && $opts['frame'] !== '' ) {
			$qs[] = 'frame=' . rawurlencode( $opts['frame'] );
		}
		if ( $opts['dir'] !== null && $opts['dir'] !== '' ) {
			$qs[] = 'dir=' . rawurlencode( $opts['dir'] );
		}
		if ( $opts['scale'] !== null && $opts['scale'] !== '' ) {
			$qs[] = 'scale=' . rawurlencode( $opts['scale'] );
		}

		global $wgSS14SpriteServiceUrl;
		$base = rtrim( (string)$wgSS14SpriteServiceUrl, '/' );
		// Encode path segments but keep slashes
		$encoded = implode( '/', array_map( 'rawurlencode', explode( '/', $target ) ) );
		$src = $base . '/sprite/' . $encoded;
		if ( $qs ) {
			$src .= '?' . implode( '&', $qs );
		}

		$alt = htmlspecialchars( $opts['alt'] ?: basename( $target ), ENT_QUOTES );
		$cls = 'wiki-sprite';
		if ( ( $opts['pixel'] ?? '1' ) !== '0' ) {
			$cls .= ' wiki-sprite--pixel';
		}

		$html = '<img class="' . $cls . '" src="' . htmlspecialchars( $src, ENT_QUOTES )
			. '" alt="' . $alt . '" loading="lazy" decoding="async" />';

		return [ $html, 'noparse' => true, 'isHTML' => true ];
	}
}
