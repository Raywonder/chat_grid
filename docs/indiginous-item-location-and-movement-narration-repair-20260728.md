# Indiginous item-location and movement narration repair

Date: 2026-07-28

## Symptoms

- Item actions frequently reported that an item was not on the user's square while moving through different locations.
- Movement narration interrupted too often during ordinary walking.

## Cause

The client item-position lookup compared only X/Y coordinates and omitted the current location ID. Items in other rooms that happened to share coordinates were therefore presented as local action targets; the server correctly rejected those stale targets.

## Repair

- Require `item.locationId === currentLocationId` for current-square items, nearby seat discovery, and item beacons.
- Coalesce repeated movement narration for 1.2 seconds while retaining meaningful people/item arrivals and required alerts.

## Verification

- Client tests: 28 passed.
- Production build: passed.
- Live client: `https://blind.software/indiginous/` returned HTTP 200.
- Live assets: `index-CDMhDh_Q.js` and `index-D4XdF8kv.css` returned HTTP 200.
- Live metadata: R537 / 0.4.14.
- `chat-grid.service` and `chat-grid-companion.service`: active.
- Fresh authenticated server connections accepted after publication.

## Recovery

Before publication, live files were backed up under:

- `/home/blindsoft/public_html/indiginous/index.html.bak-20260728-1748-item-location`
- `/home/blindsoft/public_html/indiginous/version.js.bak-20260728-1748-item-location`
- `/home/blindsoft/public_html/indiginous/assets/index-C7wqfFdf.js.bak-20260728-1748-item-location`

Published bundle SHA-256: `8eca91e5752902afa941a390a7256b3fcb52d209fd34daebdb8e16d1b3e02273`
