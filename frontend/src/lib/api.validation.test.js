import { beforeEach, describe, expect, it } from 'vitest';
import i18n from '../i18n';
import { extractApiError } from './api';

describe('extractApiError validation details', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
  });

  it('renders FastAPI validation detail arrays with field paths', () => {
    const error = {
      response: {
        status: 422,
        data: {
          detail: [
            {
              loc: ['body', 'name'],
              msg: 'Field required',
              type: 'missing',
            },
            {
              loc: ['body', 'age'],
              msg: 'Input should be a valid integer',
              type: 'int_parsing',
            },
          ],
        },
      },
    };

    expect(extractApiError(error, 'fallback-message')).toBe(
      'body.name: Field required | body.age: Input should be a valid integer',
    );
  });
});
