import { Button } from "../common/Button";

export function QueueControlButtons({ onNext, onToggle, paused }: { onNext: () => void; onToggle: () => void; paused: boolean }) {
  return <div className="flex flex-wrap gap-3"><Button onClick={onNext}>Next</Button><Button variant="secondary" onClick={onToggle}>{paused ? "Resume queue" : "Pause queue"}</Button></div>;
}
