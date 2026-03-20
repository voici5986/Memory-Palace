import { beforeEach, describe, expect, it } from 'vitest';
import i18n from './i18n';

describe('review stillReachable pluralization', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
  });

  it('resolves pluralized English review labels', () => {
    expect(i18n.t('review.stillReachable', { count: 1 })).toBe(
      'This memory is still reachable via 1 other path:',
    );
    expect(i18n.t('review.stillReachable', { count: 2 })).toBe(
      'This memory is still reachable via 2 other paths:',
    );
  });

  it('resolves zh-CN review labels without falling back to raw keys', async () => {
    await i18n.changeLanguage('zh-CN');
    expect(i18n.t('review.stillReachable', { count: 2 })).toBe(
      '这条记忆仍可通过另外 2 条路径访问：',
    );
  });
});
