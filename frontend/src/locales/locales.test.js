import { describe, expect, it } from 'vitest';

import en from './en';
import zhCN from './zh-CN';

const describeType = (value) => {
  if (Array.isArray(value)) {
    return 'array';
  }
  if (value === null) {
    return 'null';
  }
  return typeof value;
};

const isPlainObject = (value) =>
  value !== null && typeof value === 'object' && !Array.isArray(value);

const extractInterpolations = (value) =>
  typeof value === 'string'
    ? [...value.matchAll(/\{\{\s*([\w.-]+)\s*\}\}/g)]
        .map((match) => match[1])
        .sort()
    : [];

const compareLocaleTrees = (left, right, path = 'translation') => {
  const differences = [];
  const leftType = describeType(left);
  const rightType = describeType(right);

  if (leftType !== rightType) {
    differences.push(
      `${path}: type mismatch (${leftType} vs ${rightType})`
    );
    return differences;
  }

  if (Array.isArray(left) && Array.isArray(right)) {
    if (left.length !== right.length) {
      differences.push(
        `${path}: array length mismatch (${left.length} vs ${right.length})`
      );
    }

    const length = Math.min(left.length, right.length);
    for (let index = 0; index < length; index += 1) {
      differences.push(
        ...compareLocaleTrees(left[index], right[index], `${path}[${index}]`)
      );
    }
    return differences;
  }

  if (!isPlainObject(left) || !isPlainObject(right)) {
    if (typeof left === 'string' && left.trim() === '') {
      differences.push(`${path}: en locale must not be empty`);
    }
    if (typeof right === 'string' && right.trim() === '') {
      differences.push(`${path}: zh-CN locale must not be empty`);
    }
    if (typeof left === 'string' && typeof right === 'string') {
      const leftInterpolations = extractInterpolations(left);
      const rightInterpolations = extractInterpolations(right);
      if (
        JSON.stringify(leftInterpolations) !== JSON.stringify(rightInterpolations)
      ) {
        differences.push(
          `${path}: interpolation mismatch (${leftInterpolations.join(', ')} vs ${rightInterpolations.join(', ')})`
        );
      }
    }
    return differences;
  }

  const leftKeys = Object.keys(left);
  const rightKeys = Object.keys(right);

  for (const key of leftKeys) {
    if (!(key in right)) {
      differences.push(`${path}.${key}: missing in zh-CN locale`);
    }
  }

  for (const key of rightKeys) {
    if (!(key in left)) {
      differences.push(`${path}.${key}: missing in en locale`);
    }
  }

  for (const key of leftKeys) {
    if (key in right) {
      differences.push(
        ...compareLocaleTrees(left[key], right[key], `${path}.${key}`)
      );
    }
  }

  return differences;
};

describe('locale dictionaries', () => {
  it('keeps english and chinese locale trees structurally identical', () => {
    const differences = compareLocaleTrees(en, zhCN);
    expect(differences).toEqual([]);
  });
});
