/**
 * Makes product and command names predictable for speech output while leaving
 * the visible text branded and copyable.
 */
export function spokenAnnouncementText(value: string): string {
  return String(value)
    .replace(/\/ecr\*/gi, 'slash ee crypto star')
    .replace(/\/ecrypto\b/gi, 'slash ee crypto')
    .replace(/\/ecripto\b/gi, 'slash ee crypto')
    .replace(/\/ecr\b/gi, 'slash ee crypto')
    .replace(/\becrypto-test\b/gi, 'ee crypto test')
    .replace(/\beCrypto\b/gi, 'ee crypto')
    .replace(/\beCripto\b/gi, 'ee crypto')
    .replace(/\bTEST-ECR\b/gi, 'test ee cee are');
}
