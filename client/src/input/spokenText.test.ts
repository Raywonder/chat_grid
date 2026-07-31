import { describe, expect, it } from 'vitest';
import { spokenAnnouncementText } from './spokenText';

describe('spokenAnnouncementText', () => {
  it('spells eCrypto and its command aliases in a speech-friendly way', () => {
    expect(spokenAnnouncementText('eCrypto help: /ecrypto balance or /ecr* wallets.')).toBe(
      'ee crypto help: slash ee crypto balance or slash ee crypto star wallets.',
    );
    expect(spokenAnnouncementText('/ecripto /ecr ecrypto-test TEST-ECR')).toBe(
      'slash ee crypto slash ee crypto ee crypto test test ee cee are',
    );
  });
});
