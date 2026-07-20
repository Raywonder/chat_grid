import { describe, expect, it } from 'vitest';
import { formatItemInteractionHint, formatItemNarrationSummary } from './itemNarration';
import { type WorldItem } from '../state/gameState';

function item(overrides: Partial<WorldItem>): WorldItem {
  return {
    id: overrides.id ?? Math.random().toString(36),
    type: overrides.type ?? 'house_object',
    title: overrides.title ?? 'Item',
    x: overrides.x ?? 0,
    y: overrides.y ?? 0,
    createdBy: overrides.createdBy ?? 'system',
    createdByName: overrides.createdByName,
    updatedBy: overrides.updatedBy ?? 'system',
    updatedByName: overrides.updatedByName,
    createdAt: overrides.createdAt ?? 0,
    updatedAt: overrides.updatedAt ?? 0,
    version: overrides.version ?? 1,
    capabilities: overrides.capabilities ?? [],
    params: overrides.params ?? {},
  };
}

describe('item narration summaries', () => {
  it('groups repeated unowned items by amount', () => {
    expect(
      formatItemNarrationSummary([
        item({ title: 'Universal radio remote', type: 'radio_remote' }),
        item({ title: 'Universal radio remote', type: 'radio_remote' }),
        item({ title: 'Chair', type: 'furniture' }),
      ]),
    ).toBe('2 universal radio remotes, a chair');
  });

  it('keeps owned items possessive before the item name', () => {
    expect(
      formatItemNarrationSummary([
        item({ title: 'Diary', createdBy: 'u1', createdByName: 'Claudia' }),
        item({ title: 'Bed', type: 'furniture', createdByName: 'system' }),
        item({ title: 'Couch', type: 'furniture' }),
      ]),
    ).toBe("Claudia's Diary, a bed, a couch");
  });

  it('groups repeated owned items under the owner name', () => {
    expect(
      formatItemNarrationSummary([
        item({ title: 'Notebook', createdBy: 'u1', createdByName: 'Jess' }),
        item({ title: 'Notebook', createdBy: 'u1', createdByName: 'Jess' }),
      ]),
    ).toBe("2 Jess's notebooks");
  });

  it('adds brief interaction hints for readable paper items', () => {
    const note = item({
      title: 'sealed note for Dom',
      params: { objectKind: 'book', readableText: 'A tiny hello.' },
    });

    expect(formatItemInteractionHint(note)).toBe('press Enter to read');
    expect(formatItemNarrationSummary([note])).toBe('a sealed note for Dom; press Enter to read');
  });

  it('uses explicit interaction hints when provided', () => {
    const mailbox = item({
      title: 'Raywonder mailbox',
      params: { objectKind: 'mailbox', interactionHint: 'press Enter to check mail.' },
    });

    expect(formatItemInteractionHint(mailbox)).toBe('press Enter to check mail');
  });
});
