/** The demo modes the presenter can choose between. To strip one before the presentation, delete its file
 *  and its line here (and, for "live", the server module src/treehouse/ui/pitch_live.py; see docs/PITCH.md). */
import type { ComponentType } from 'react';
import { EmbeddedDemo } from './embedded.tsx';
import { LiveDemo } from './live.tsx';
import { RecordedDemo } from './recorded.tsx';

export type DemoProps = {stage: number; stages: number};
export type DemoMode = {
  id: string; label: string; hint: string;
  /** >1: the section becomes a scroll-driven sequence of this many stages (one screen each). */
  stages: number;
  Component: ComponentType<DemoProps>;
};

export const DEMO_MODES: DemoMode[] = [
  {id: 'recorded', label: 'Recorded run', hint: 'A real Bedrock run, replayed from its recording. Works offline.', stages: 3, Component: RecordedDemo},
  {id: 'embedded', label: 'Treehouse app', hint: 'The real app, embedded. Needs `treehouse ui serve`.', stages: 1, Component: EmbeddedDemo},
  {id: 'live', label: 'Live on Bedrock', hint: 'Start a new agent run on AWS now. Needs TREEHOUSE_PITCH_LIVE=1.', stages: 1, Component: LiveDemo},
];
