import {Button} from '@astryxdesign/core/Button';

export type CitationMarkerProps = {
  index: number;
  label: string;
  onOpen?: () => void;
};

export function CitationMarker({index, label, onOpen}: CitationMarkerProps) {
  return (
    <Button
      label={`引用 ${index}: ${label}`}
      variant="ghost"
      size="sm"
      onClick={onOpen}>
      [{index}] {label}
    </Button>
  );
}
