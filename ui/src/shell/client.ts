/** Which backend the shell talks to. Dev server: mock unless VITE_TREEHOUSE_API=http. Build: HTTP unless =mock. */
import type { Narrator, TreehouseClient } from './contract.ts';
import { httpClient } from './http.ts';
import { mockClient, mockNarrator } from './mock.ts';

const env = import.meta.env.VITE_TREEHOUSE_API;
export const usingMock = import.meta.env.DEV ? env !== 'http' : env === 'mock';
export const client: TreehouseClient & {replay?(id: string): void} = usingMock ? mockClient : httpClient;
export const narrator: Narrator = mockNarrator;   // shortcut: template captions; swap for the Bedrock + Polly narrator when the backend has it
