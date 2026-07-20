import { type WorldItem } from '../state/gameState';

const SYSTEM_OWNER_NAMES = new Set(['system', 'community watcher']);
const PAPER_OBJECT_KINDS = new Set(['book', 'notebook', 'letter', 'envelope', 'note']);

function cleanText(value: unknown): string {
  return String(value ?? '').replace(/\s+/g, ' ').trim();
}

function lowerFirst(value: string): string {
  if (!value) return value;
  return value.charAt(0).toLowerCase() + value.slice(1);
}

function possessiveName(name: string): string {
  return `${name}'s`;
}

function pluralizeTitle(title: string): string {
  const trimmed = cleanText(title);
  if (!trimmed) return 'items';
  const words = trimmed.split(' ');
  const last = words[words.length - 1] ?? '';
  const lowered = last.toLowerCase();
  let plural = `${last}s`;
  if (/(s|x|z|ch|sh)$/i.test(last)) {
    plural = `${last}es`;
  } else if (/[^aeiou]y$/i.test(last)) {
    plural = `${last.slice(0, -1)}ies`;
  } else if (lowered === 'person') {
    plural = 'people';
  } else if (lowered === 'child') {
    plural = 'children';
  }
  return [...words.slice(0, -1), plural].join(' ');
}

function indefiniteArticle(title: string): string {
  return /^[aeiou]/i.test(title.trim()) ? 'an' : 'a';
}

function itemOwnerName(item: WorldItem): string {
  const owner = cleanText(item.createdByName);
  if (!owner || SYSTEM_OWNER_NAMES.has(owner.toLowerCase())) return '';
  return owner;
}

function itemNarrationTitle(item: WorldItem): string {
  const title = cleanText(item.title) || 'item';
  const owner = itemOwnerName(item);
  return owner ? `${possessiveName(owner)} ${title}` : title;
}

function itemNarrationKey(item: WorldItem): string {
  return `${itemOwnerName(item).toLowerCase()}\u0000${cleanText(item.title).toLowerCase()}\u0000${item.type}`;
}

function countLabel(count: number): string {
  return count.toLocaleString('en-US');
}

function paperInteractionVerb(item: WorldItem): string {
  const kind = cleanText(item.params.objectKind).toLowerCase();
  const title = cleanText(item.title).toLowerCase();
  if (kind === 'envelope' || title.includes('envelope')) return 'open and read';
  if (kind === 'letter' || title.includes('letter') || title.includes('note')) return 'read';
  if (kind === 'book' || kind === 'notebook' || title.includes('book') || title.includes('notebook')) return 'read';
  return '';
}

export function formatItemInteractionHint(item: WorldItem): string {
  const explicit = cleanText(item.params.interactionHint);
  if (explicit) return explicit.replace(/[.。]+$/u, '');

  const objectKind = cleanText(item.params.objectKind).toLowerCase();
  const hasReadableText = cleanText(item.params.readableText).length > 0;
  const titlePaperVerb = paperInteractionVerb(item);
  const paperVerb = PAPER_OBJECT_KINDS.has(objectKind) || hasReadableText || titlePaperVerb ? titlePaperVerb || 'read' : '';
  if (paperVerb) return `press Enter to ${paperVerb}`;
  if (objectKind === 'sign') return 'press Enter to read the sign';
  if (objectKind === 'mailbox') return 'press Enter to check it';
  if (objectKind === 'phone') return 'press Enter to inspect it; carry it and press Control P to dial';
  return '';
}

function appendInteractionHint(label: string, item: WorldItem): string {
  const hint = formatItemInteractionHint(item);
  return hint ? `${label}; ${hint}` : label;
}

export function formatItemNarrationLabel(item: WorldItem): string {
  return itemNarrationTitle(item);
}

export function formatItemNarrationSummary(items: WorldItem[]): string {
  const groups = new Map<string, { item: WorldItem; count: number }>();
  for (const item of items) {
    const key = itemNarrationKey(item);
    const group = groups.get(key);
    if (group) {
      group.count += 1;
    } else {
      groups.set(key, { item, count: 1 });
    }
  }
  return Array.from(groups.values())
    .map(({ item, count }) => {
      const title = itemNarrationTitle(item);
      const owner = itemOwnerName(item);
      if (count === 1) {
        const label = owner ? title : `${indefiniteArticle(title)} ${lowerFirst(title)}`;
        return appendInteractionHint(label, item);
      }
      if (owner) {
        const rawTitle = cleanText(item.title) || 'item';
        return `${countLabel(count)} ${possessiveName(owner)} ${lowerFirst(pluralizeTitle(rawTitle))}`;
      }
      return `${countLabel(count)} ${lowerFirst(pluralizeTitle(title))}`;
    })
    .join(', ');
}
