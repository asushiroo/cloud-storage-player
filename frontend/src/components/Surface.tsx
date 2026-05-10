import type { PropsWithChildren } from "react";

export function Surface({ children }: PropsWithChildren) {
  return <section className="surface">{children}</section>;
}
