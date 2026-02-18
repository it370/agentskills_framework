import { ReactNode, useId } from "react";

export default function Tooltip({
  content,
  children,
}: {
  content: ReactNode;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <span className="relative inline-flex group">
      <span aria-describedby={id}>{children}</span>
      <span
        id={id}
        role="tooltip"
        className="pointer-events-none absolute right-[-10px] top-0 -translate-y-5 mr-2 z-50 hidden group-hover:block group-focus-within:block"
      >
        <span className="block whitespace-nowrap rounded-md bg-gray-900 px-2 py-1 text-xs text-white shadow-lg">
          {content}
        </span>
      </span>
    </span>
  );
}

