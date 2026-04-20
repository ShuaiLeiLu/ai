import type { PropsWithChildren } from 'react';

import { WorkstationShell } from '@/features/shell/components/workstation-shell';

export default function WorkstationLayout({ children }: PropsWithChildren) {
  return <WorkstationShell>{children}</WorkstationShell>;
}
