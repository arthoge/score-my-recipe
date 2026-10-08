/** Both French locale variants must translate the entire improvement dialog. */
import { expect, it } from 'vitest';
import english from './messages/en-US.json';
import french from './messages/fr.json';
import frenchFrance from './messages/fr-FR.json';

it.each([french, frenchFrance])(
	'provides French dialog strings with intact placeholders',
	(messages) => {
		expect(Object.keys(messages.improvements).sort()).toEqual(
			Object.keys(english.improvements).sort()
		);
		for (const key of Object.keys(english.improvements) as (keyof typeof english.improvements)[]) {
			if (key !== 'off') expect(messages.improvements[key]).not.toBe(english.improvements[key]);
			expect(messages.improvements[key].match(/\{[^}]+\}/g) ?? []).toEqual(
				english.improvements[key].match(/\{[^}]+\}/g) ?? []
			);
		}
	}
);
