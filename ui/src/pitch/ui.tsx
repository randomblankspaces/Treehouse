/** Shared pitch building blocks: the slide list, the <Slide> screen with scroll reveal, and the stagger helper. */
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';

export const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

export const SLIDES = [
  {id: 'problem', label: 'Problem'},
  {id: 'context', label: 'Why it is real'},
  {id: 'backwards', label: 'Working backwards'},
  {id: 'solution', label: 'How we fix it'},
  {id: 'architecture', label: 'Architecture'},
  {id: 'demo', label: 'Demo'},
  {id: 'numbers', label: 'By the numbers'},
  {id: 'impact', label: 'Impact'},
  {id: 'future', label: 'Future & scale'},
] as const;
export type SlideId = typeof SLIDES[number]['id'];

/** One screen. `data-in` flips on when a third of it is visible; CSS reveals `.r` children in order. */
export function Slide({id, className = '', children, tall = false}: {id: SlideId; className?: string; children: ReactNode; tall?: boolean}) {
  const ref = useRef<HTMLElement>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) setInView(true); }, {threshold: tall ? 0.05 : 0.3});
    io.observe(el);
    return () => io.disconnect();
  }, [tall]);
  const label = SLIDES.find(s => s.id === id)?.label;
  return <section id={id} ref={ref} className={`slide ${tall ? 'tall' : ''} ${className}`} data-in={inView ? '1' : '0'} aria-label={label}>
    {children}
  </section>;
}

/** Stagger helper: <div className="r" style={d(2)}> reveals as the second item. */
export const d = (n: number): CSSProperties => ({['--d' as string]: `${n * 110}ms`});
