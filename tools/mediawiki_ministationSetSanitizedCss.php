<?php
/**
 * Save stdin as sanitized-css for a TemplateStyles page.
 * Usage: php maintenance/run.php ministationSetSanitizedCss.php "Шаблон:Foo/styles.css" < file.css
 */

use MediaWiki\CommentStore\CommentStoreComment;
use MediaWiki\Maintenance\Maintenance;
use MediaWiki\MediaWikiServices;
use MediaWiki\Revision\SlotRecord;
use MediaWiki\Title\Title;
use MediaWiki\User\User;

require_once __DIR__ . '/Maintenance.php';

class MinistationSetSanitizedCss extends Maintenance {
	public function __construct() {
		parent::__construct();
		$this->addDescription( 'Save stdin as sanitized-css' );
		$this->addArg( 'title', 'Page title' );
	}

	public function execute() {
		$titleText = $this->getArg( 0 );
		$title = Title::newFromText( $titleText );
		if ( !$title ) {
			$this->fatalError( "Bad title: $titleText" );
		}

		$css = stream_get_contents( STDIN );
		if ( $css === false || trim( $css ) === '' ) {
			$this->fatalError( 'Empty CSS on stdin' );
		}

		$services = MediaWikiServices::getInstance();

		// Prefer wiki Admin account (has edit rights)
		$userName = getenv( 'MW_ADMIN' ) ?: 'Admin';
		$user = User::newFromName( $userName );
		if ( !$user || !$user->isRegistered() ) {
			$user = User::newSystemUser( 'Maintenance script', [ 'steal' => true ] );
		}
		if ( !$user ) {
			$this->fatalError( 'No user for edit' );
		}

		$authority = $user;
		$contentHandler = $services->getContentHandlerFactory()
			->getContentHandler( 'sanitized-css' );
		$content = $contentHandler->unserializeContent( $css );
		if ( !$content ) {
			$this->fatalError( 'unserializeContent failed' );
		}

		$page = $services->getWikiPageFactory()->newFromTitle( $title );
		$updater = $page->newPageUpdater( $authority );
		$updater->setContent( SlotRecord::MAIN, $content );
		$rev = $updater->saveRevision(
			CommentStoreComment::newUnsavedComment( 'import TemplateStyles CSS' ),
			EDIT_FORCE_BOT | EDIT_SUPPRESS_RC
		);

		if ( !$rev ) {
			$status = $updater->getStatus();
			$msg = method_exists( $status, 'getWikiText' )
				? $status->getWikiText( false, false, 'en' )
				: $status->__toString();
			$this->fatalError( "saveRevision failed: $msg" );
		}

		// Reload title id
		$title = Title::newFromText( $titleText );
		$this->output(
			'OK ' . $title->getPrefixedText()
			. ' id=' . $title->getId()
			. ' model=' . $title->getContentModel()
			. ' bytes=' . strlen( $css ) . "\n"
		);
	}
}

$maintClass = MinistationSetSanitizedCss::class;
require_once RUN_MAINTENANCE_IF_MAIN;
